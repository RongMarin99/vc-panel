"""Apache HTTP Server — system detection + VC-managed installs via ApacheLounge."""
import re
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from providers.base_service import BaseService, ServiceInfo
from providers._svc_win import (
    run_cmd, find_service, sc_start, sc_stop,
    start_direct, stop_direct, pid_running,
)
from core.base_manager import VersionInfo

_SYS_SERVICES = ["Apache2.4", "Apache24", "Apache2", "httpd", "Apache"]

_HTTPD_CANDIDATES = [
    r"C:\xampp\apache\bin\httpd.exe",
    r"C:\laragon\bin\apache\Apache24\bin\httpd.exe",
    r"C:\Apache24\bin\httpd.exe",
    r"C:\Program Files\Apache Software Foundation\Apache2.4\bin\httpd.exe",
]

_CONF_CANDIDATES = [
    r"C:\xampp\apache\conf\httpd.conf",
    r"C:\laragon\bin\apache\Apache24\conf\httpd.conf",
    r"C:\Apache24\conf\httpd.conf",
    r"C:\Program Files\Apache Software Foundation\Apache2.4\conf\httpd.conf",
]

# ApacheLounge VS17 binaries
_REMOTE = [
    ("2.4.62", "2024-07-03"),
    ("2.4.61", "2024-05-23"),
    ("2.4.59", "2024-04-04"),
    ("2.4.58", "2023-10-19"),
]


def _dl_url(version: str) -> str:
    return (
        f"https://www.apachelounge.com/download/VS17/binaries/"
        f"httpd-{version}-win64-VS17.zip"
    )


def _find_sys_httpd() -> str | None:
    exe = shutil.which("httpd") or shutil.which("apache2")
    if exe:
        return exe
    for p in _HTTPD_CANDIDATES:
        if Path(p).exists():
            return p
    base = Path(r"C:\wamp64\bin\apache")
    if base.exists():
        for d in sorted(base.iterdir(), reverse=True):
            h = d / "bin" / "httpd.exe"
            if h.exists():
                return str(h)
    return None


def _find_sys_conf() -> str | None:
    httpd = _find_sys_httpd()
    if httpd:
        r = run_cmd([httpd, "-V"], timeout=5)
        if r:
            m = re.search(r'ServerRoot:\s*"([^"]+)"', r.stdout + r.stderr)
            if m:
                conf = Path(m.group(1)) / "conf" / "httpd.conf"
                if conf.exists():
                    return str(conf)
    for p in _CONF_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _read_port(conf_path: str) -> int:
    try:
        text = Path(conf_path).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^\s*Listen\s+(\d+)", text, re.MULTILINE | re.IGNORECASE)
        return int(m.group(1)) if m else 80
    except Exception:
        return 80


def _write_port(conf_path: str, port: int) -> bool:
    try:
        text = Path(conf_path).read_text(encoding="utf-8", errors="replace")
        new, n = re.subn(r"(^\s*Listen\s+)\d+", rf"\g<1>{port}",
                         text, flags=re.MULTILINE | re.IGNORECASE)
        if n == 0:
            new = text + f"\nListen {port}\n"
        Path(conf_path).write_text(new, encoding="utf-8")
        return True
    except Exception:
        return False


def _get_sys_version() -> str | None:
    httpd = _find_sys_httpd()
    if not httpd:
        return None
    r = run_cmd([httpd, "-v"], timeout=5)
    if not r:
        return None
    m = re.search(r"Apache/(\d+\.\d+\.\d+)", r.stdout + r.stderr)
    return m.group(1) if m else None


def _download(url: str, dest: Path, progress_cb: Optional[Callable] = None,
              referer: str = ""):
    # ApacheLounge and other sites block generic user-agents — use browser headers
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/zip, application/octet-stream, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        # Reject HTML responses (bot-detection pages)
        ct = resp.headers.get("Content-Type", "")
        if "text/html" in ct:
            raise RuntimeError(
                "Server returned an HTML page instead of a ZIP file.\n"
                "ApacheLounge may be blocking automated downloads.\n"
                "Download manually from: https://www.apachelounge.com/download/"
            )
        total = int(resp.headers.get("Content-Length") or 0)
        downloaded = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total > 0:
                    progress_cb(downloaded, total)


def _extract_auto(zip_path: Path, dest: Path):
    """Extract zip, auto-detecting and stripping a single common root prefix."""
    if not zipfile.is_zipfile(zip_path):
        raise RuntimeError(
            "Downloaded file is not a valid ZIP.\n"
            "The server may have returned an error page.\n"
            "Try downloading manually from: https://www.apachelounge.com/download/"
        )
    with zipfile.ZipFile(zip_path) as zf:
        names = [m.filename for m in zf.infolist()]
        # Detect single root dir (e.g. Apache24/)
        top_dirs = {n.split("/")[0] for n in names if "/" in n}
        strip = ""
        if len(top_dirs) == 1:
            candidate = next(iter(top_dirs)) + "/"
            if all(n.startswith(candidate) or "/" not in n for n in names):
                strip = candidate

        for member in zf.infolist():
            rel = member.filename
            if strip and rel.startswith(strip):
                rel = rel[len(strip):]
            if not rel:
                continue
            target = dest / rel
            if member.filename.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(member.filename))


class ApacheService(BaseService):
    name = "apache"
    display_name = "Apache"
    icon = "🌐"
    default_port = 80

    def __init__(self, config=None):
        self._config = config
        self._svc_key: str | None = None

    @property
    def versions_root(self) -> Path:
        base = Path(self._config.versions_dir) if self._config else Path.home() / ".vc" / "versions"
        root = base / self.name
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _vc_svc(self, version: str) -> str:
        return f"VC-Apache-{version}"

    def _pid_file(self) -> Path:
        base = Path(self._config.versions_dir) if self._config else Path.home() / ".vc"
        return base / "apache_sys.pid"

    # ── VC-managed version management ─────────────────────────────────────────

    def list_remote(self) -> list[VersionInfo]:
        installed = {d.name for d in self.versions_root.iterdir()
                     if d.is_dir() and (d / ".vc_managed").exists()}
        result = []
        for ver, date in _REMOTE:
            inst = ver in installed
            active = self.is_vc_running(ver) if inst else False
            result.append(VersionInfo(version=ver, installed=inst, active=active,
                                       release_date=date,
                                       install_path=self.versions_root / ver if inst else None))
        return result

    def list_installed_vc(self) -> list[VersionInfo]:
        result = []
        for d in sorted(self.versions_root.iterdir(), reverse=True):
            if not (d.is_dir() and (d / ".vc_managed").exists()):
                continue
            result.append(VersionInfo(version=d.name, installed=True,
                                       active=self.is_vc_running(d.name), install_path=d))
        return result

    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool:
        dest = self.versions_root / version
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        url = _dl_url(version)
        zip_path = dest / f"apache-{version}.zip"
        try:
            _download(url, zip_path, progress_callback,
                      referer="https://www.apachelounge.com/download/")
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Download failed: {e}")

        try:
            _extract_auto(zip_path, dest)
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Extraction failed: {e}")
        finally:
            zip_path.unlink(missing_ok=True)

        # Apache requires logs/ dir to exist
        (dest / "logs").mkdir(exist_ok=True)

        # Update ServerRoot / SRVROOT in httpd.conf to actual path
        conf = dest / "conf" / "httpd.conf"
        if conf.exists():
            text = conf.read_text(encoding="utf-8", errors="replace")
            srvroot = dest.as_posix()
            text = re.sub(r'Define SRVROOT "[^"]*"', f'Define SRVROOT "{srvroot}"', text)
            text = re.sub(r'^(ServerRoot\s+)"[^"]*"',
                          rf'\g<1>"{srvroot}"', text, flags=re.MULTILINE)
            # Use port 8080 so VC-managed Apache starts without admin (port 80 needs admin)
            text = re.sub(r'^\s*Listen\s+80\b', 'Listen 8080', text, flags=re.MULTILINE)
            conf.write_text(text, encoding="utf-8")

        # Mark VC-managed
        (dest / ".vc_managed").write_text(version)

        # Try service registration
        httpd = dest / "bin" / "httpd.exe"
        if httpd.exists() and conf.exists():
            run_cmd([str(httpd), "-k", "install",
                     "-n", self._vc_svc(version),
                     "-f", str(conf)], timeout=30)

        return True

    def uninstall_vc(self, version: str) -> bool:
        dest = self.versions_root / version
        self.stop_vc(version)
        httpd = dest / "bin" / "httpd.exe"
        if httpd.exists():
            run_cmd([str(httpd), "-k", "uninstall", "-n", self._vc_svc(version)], timeout=20)
        shutil.rmtree(dest, ignore_errors=True)
        return True

    def start_vc(self, version: str) -> bool:
        if sc_start(self._vc_svc(version)):
            return True
        dest = self.versions_root / version
        httpd = dest / "bin" / "httpd.exe"
        conf = dest / "conf" / "httpd.conf"
        if not httpd.exists():
            return False
        args = [str(httpd)] + (["-f", str(conf)] if conf.exists() else [])
        return start_direct(args, dest / ".pid")

    def stop_vc(self, version: str) -> bool:
        dest = self.versions_root / version
        sc_stop(self._vc_svc(version))
        httpd = dest / "bin" / "httpd.exe"
        if httpd.exists():
            run_cmd([str(httpd), "-k", "stop",
                     "-n", self._vc_svc(version)], timeout=10)
        stop_direct(dest / ".pid")
        return True

    def is_vc_running(self, version: str) -> bool:
        from providers._svc_win import sc_query
        if sc_query(self._vc_svc(version)) == "running":
            return True
        return pid_running(self.versions_root / version / ".pid")

    # ── System service management ─────────────────────────────────────────────

    def _ensure_svc(self) -> str | None:
        if not self._svc_key:
            svc, _ = find_service(_SYS_SERVICES)
            self._svc_key = svc
        return self._svc_key

    def info(self) -> ServiceInfo:
        svc, status = find_service(_SYS_SERVICES)
        self._svc_key = svc
        if status is None:
            if pid_running(self._pid_file()):
                status = "running"
            else:
                status = "not_found" if not _find_sys_httpd() else "stopped"
        cfg = _find_sys_conf()
        port = _read_port(cfg) if cfg else self.default_port
        ver = _get_sys_version()
        return ServiceInfo(status=status, version=ver, port=port,
                           config_path=cfg, service_key=svc)

    def start(self) -> bool:
        svc = self._ensure_svc()
        if svc and sc_start(svc):
            return True
        httpd = _find_sys_httpd()
        if not httpd:
            return False
        return start_direct([httpd, "-k", "start"], self._pid_file())

    def stop(self) -> bool:
        svc = self._ensure_svc()
        sc_stop(svc or "")
        httpd = _find_sys_httpd()
        if httpd:
            run_cmd([httpd, "-k", "stop"], timeout=10)
        stop_direct(self._pid_file())
        return True

    def get_port(self) -> int:
        cfg = _find_sys_conf()
        return _read_port(cfg) if cfg else self.default_port

    def set_port(self, port: int) -> bool:
        cfg = _find_sys_conf()
        return _write_port(cfg, port) if cfg else False
