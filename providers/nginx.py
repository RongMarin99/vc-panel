"""Nginx web server — system detection + VC-managed installs from nginx.org."""
import re
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from providers.base_service import BaseService, ServiceInfo
from providers._svc_win import (
    run_cmd, find_service, sc_start, sc_stop,
    stop_direct, pid_running,
)
from core.base_manager import VersionInfo

_SYS_SERVICES = ["nginx", "NGINXService", "nginx-service"]

_NGINX_CANDIDATES = [
    r"C:\nginx\nginx.exe",
    r"C:\Program Files\nginx\nginx.exe",
    r"C:\Program Files (x86)\nginx\nginx.exe",
]

_CONF_CANDIDATES = [
    r"C:\nginx\conf\nginx.conf",
    r"C:\Program Files\nginx\conf\nginx.conf",
]

_REMOTE = [
    ("1.27.1", "2024-08-13"),
    ("1.26.2", "2024-08-14"),
    ("1.26.1", "2024-05-29"),
    ("1.26.0", "2024-04-23"),
    ("1.24.0", "2023-04-11"),
]


def _dl_url(version: str) -> str:
    return f"https://nginx.org/download/nginx-{version}.zip"


def _find_sys_nginx() -> str | None:
    exe = shutil.which("nginx")
    if exe:
        return exe
    for p in _NGINX_CANDIDATES:
        if Path(p).exists():
            return p
    for base in [Path(r"C:\laragon\bin\nginx"), Path(r"C:\wamp64\bin\nginx")]:
        if base.exists():
            for d in sorted(base.iterdir(), reverse=True):
                h = d / "nginx.exe"
                if h.exists():
                    return str(h)
    return None


def _find_sys_conf() -> str | None:
    exe = _find_sys_nginx()
    if exe:
        root = Path(exe).parent.parent
        conf = root / "conf" / "nginx.conf"
        if conf.exists():
            return str(conf)
    for p in _CONF_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _read_port(conf_path: str) -> int:
    try:
        text = Path(conf_path).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"listen\s+(\d+)\s*;", text, re.MULTILINE | re.IGNORECASE)
        return int(m.group(1)) if m else 80
    except Exception:
        return 80


def _write_port(conf_path: str, port: int) -> bool:
    try:
        text = Path(conf_path).read_text(encoding="utf-8", errors="replace")
        new, n = re.subn(r"(listen\s+)\d+(\s*;)", rf"\g<1>{port}\2",
                         text, flags=re.MULTILINE | re.IGNORECASE)
        if n == 0:
            return False
        Path(conf_path).write_text(new, encoding="utf-8")
        return True
    except Exception:
        return False


def _get_sys_version() -> str | None:
    exe = _find_sys_nginx()
    if not exe:
        return None
    r = run_cmd([exe, "-v"], timeout=5)
    if not r:
        return None
    m = re.search(r"nginx/(\d+\.\d+\.\d+)", r.stdout + r.stderr)
    return m.group(1) if m else None


def _download(url: str, dest: Path, progress_cb: Optional[Callable] = None):
    req = urllib.request.Request(url, headers={"User-Agent": "VC-VersionController/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
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


def _extract_strip_root(zip_path: Path, dest: Path):
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            parts = member.filename.split("/", 1)
            if len(parts) < 2 or not parts[1]:
                continue
            target = dest / parts[1]
            if member.filename.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(member.filename))


def _nginx_pid_file(dest: Path) -> Path:
    """Nginx writes its own PID to logs/nginx.pid. Use that for status checks."""
    return dest / "logs" / "nginx.pid"


class NginxService(BaseService):
    name = "nginx"
    display_name = "Nginx"
    icon = "🔷"
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
        return f"VC-Nginx-{version}"

    def _sys_pid_file(self) -> Path:
        base = Path(self._config.versions_dir) if self._config else Path.home() / ".vc"
        return base / "nginx_sys.pid"

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
        zip_path = dest / f"nginx-{version}.zip"
        try:
            _download(url, zip_path, progress_callback)
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Download failed: {e}")

        try:
            _extract_strip_root(zip_path, dest)
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Extraction failed: {e}")
        finally:
            zip_path.unlink(missing_ok=True)

        # Ensure logs dir exists (nginx needs it)
        (dest / "logs").mkdir(exist_ok=True)

        # Use port 8080 so VC-managed nginx starts without admin (port 80 needs admin)
        conf = dest / "conf" / "nginx.conf"
        if conf.exists():
            text = conf.read_text(encoding="utf-8", errors="replace")
            text = re.sub(r'(listen\s+)80(\s*;)', r'\g<1>8080\2',
                          text, flags=re.MULTILINE | re.IGNORECASE)
            conf.write_text(text, encoding="utf-8")

        # Mark VC-managed
        (dest / ".vc_managed").write_text(version)
        return True

    def uninstall_vc(self, version: str) -> bool:
        self.stop_vc(version)
        shutil.rmtree(self.versions_root / version, ignore_errors=True)
        return True

    def start_vc(self, version: str) -> bool:
        dest = self.versions_root / version
        nginx = dest / "nginx.exe"
        if not nginx.exists():
            return False
        # nginx does NOT daemonize on Windows — must use DETACHED_PROCESS
        from providers._svc_win import start_direct
        return start_direct([str(nginx), "-p", str(dest)], dest / ".pid")

    def stop_vc(self, version: str) -> bool:
        dest = self.versions_root / version
        nginx = dest / "nginx.exe"
        if nginx.exists():
            # Graceful quit via nginx signal (uses logs/nginx.pid internally)
            run_cmd([str(nginx), "-p", str(dest), "-s", "quit"], timeout=10)
        stop_direct(dest / ".pid")
        return True

    def is_vc_running(self, version: str) -> bool:
        return pid_running(self.versions_root / version / ".pid")

    # ── System service management ─────────────────────────────────────────────

    def _ensure_svc(self) -> str | None:
        if not self._svc_key:
            svc, _ = find_service(_SYS_SERVICES)
            self._svc_key = svc
        return self._svc_key

    def _sys_pid_file(self) -> Path:
        base = Path(self._config.versions_dir) if self._config else Path.home() / ".vc"
        return base / "nginx_sys.pid"

    def info(self) -> ServiceInfo:
        svc, status = find_service(_SYS_SERVICES)
        self._svc_key = svc
        if status is None:
            exe = _find_sys_nginx()
            if not exe:
                status = "not_found"
            elif pid_running(self._sys_pid_file()):
                status = "running"
            else:
                # Also check nginx's own logs/nginx.pid (system-managed)
                root = Path(exe).parent.parent
                status = "running" if pid_running(root / "logs" / "nginx.pid") else "stopped"
        cfg = _find_sys_conf()
        port = _read_port(cfg) if cfg else self.default_port
        ver = _get_sys_version()
        return ServiceInfo(status=status, version=ver, port=port,
                           config_path=cfg, service_key=svc)

    def start(self) -> bool:
        svc = self._ensure_svc()
        if svc and sc_start(svc):
            return True
        exe = _find_sys_nginx()
        if not exe:
            return False
        root = Path(exe).parent.parent
        from providers._svc_win import start_direct
        return start_direct([exe, "-p", str(root)], self._sys_pid_file())

    def stop(self) -> bool:
        svc = self._ensure_svc()
        sc_stop(svc or "")
        exe = _find_sys_nginx()
        if exe:
            root = Path(exe).parent.parent
            run_cmd([exe, "-p", str(root), "-s", "quit"], timeout=10)
        stop_direct(self._sys_pid_file())
        return True

    def get_port(self) -> int:
        cfg = _find_sys_conf()
        return _read_port(cfg) if cfg else self.default_port

    def set_port(self, port: int) -> bool:
        cfg = _find_sys_conf()
        return _write_port(cfg, port) if cfg else False
