"""Traefik reverse proxy — system detection + VC-managed installs from GitHub."""
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

_SYS_SERVICES = ["traefik", "Traefik"]

_EXE_CANDIDATES = [
    r"C:\traefik\traefik.exe",
    r"C:\Program Files\Traefik\traefik.exe",
    r"C:\tools\traefik\traefik.exe",
]

_CONF_CANDIDATES = [
    r"C:\traefik\traefik.yml",
    r"C:\traefik\traefik.yaml",
    r"C:\traefik\traefik.toml",
    r"C:\Program Files\Traefik\traefik.yml",
]

_REMOTE = [
    ("3.1.0",  "2024-07-15"),
    ("3.0.4",  "2024-07-10"),
    ("3.0.3",  "2024-06-12"),
    ("2.11.5", "2024-07-15"),
    ("2.11.4", "2024-06-12"),
]

_DEFAULT_CONFIG = """\
# Traefik static configuration (managed by VC)
# Port 8080 used by default — no admin required.
# Change to :80 via the Port button (requires admin or netsh urlacl grant).
api:
  dashboard: true
  insecure: true

log:
  level: INFO

entryPoints:
  web:
    address: ":8080"
  traefik:
    address: ":8090"

providers:
  file:
    directory: ./dynamic
    watch: true
"""


def _dl_url(version: str) -> str:
    return (
        f"https://github.com/traefik/traefik/releases/download/"
        f"v{version}/traefik_v{version}_windows_amd64.zip"
    )


def _find_sys_exe() -> str | None:
    exe = shutil.which("traefik")
    if exe:
        return exe
    for p in _EXE_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _find_sys_conf() -> str | None:
    exe = _find_sys_exe()
    if exe:
        base = Path(exe).parent
        for name in ("traefik.yml", "traefik.yaml", "traefik.toml"):
            c = base / name
            if c.exists():
                return str(c)
    for p in _CONF_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _read_port(conf_path: str) -> int:
    try:
        text = Path(conf_path).read_text(encoding="utf-8", errors="replace")
        m = re.search(r'address\s*:\s*["\']?:(\d+)', text, re.MULTILINE)
        if not m:
            m = re.search(r'address\s*=\s*["\']:(\d+)', text, re.MULTILINE)
        return int(m.group(1)) if m else 80
    except Exception:
        return 80


def _write_port(conf_path: str, port: int) -> bool:
    try:
        text = Path(conf_path).read_text(encoding="utf-8", errors="replace")
        # Replace the web entrypoint port specifically (first match)
        new, n = re.subn(r'(address\s*:\s*["\']?):(\d+)', rf'\g<1>:{port}',
                         text, count=1, flags=re.MULTILINE)
        if n == 0:
            new, n = re.subn(r'(address\s*=\s*["\']?):(\d+)', rf'\g<1>:{port}',
                             text, count=1, flags=re.MULTILINE)
        if n == 0:
            return False
        Path(conf_path).write_text(new, encoding="utf-8")
        return True
    except Exception:
        return False


def _get_sys_version() -> str | None:
    exe = _find_sys_exe()
    if not exe:
        return None
    r = run_cmd([exe, "version"], timeout=5)
    if not r:
        return None
    m = re.search(r"Version\s*:\s*v?(\d+\.\d+\.\d+)", r.stdout + r.stderr, re.IGNORECASE)
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


def _extract_flat(zip_path: Path, dest: Path):
    """Traefik release zip is flat — just traefik.exe + LICENSE."""
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if member.filename.endswith("/"):
                continue
            target = dest / Path(member.filename).name
            target.write_bytes(zf.read(member.filename))


class TraefikService(BaseService):
    name = "traefik"
    display_name = "Traefik"
    icon = "🔀"
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
        return f"VC-Traefik-{version}"

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
        zip_path = dest / f"traefik-{version}.zip"
        try:
            _download(url, zip_path, progress_callback)
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Download failed: {e}")

        try:
            _extract_flat(zip_path, dest)
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Extraction failed: {e}")
        finally:
            zip_path.unlink(missing_ok=True)

        # Write default config
        cfg = dest / "traefik.yml"
        if not cfg.exists():
            cfg.write_text(_DEFAULT_CONFIG, encoding="utf-8")

        # Create dynamic config dir
        (dest / "dynamic").mkdir(exist_ok=True)

        # Mark VC-managed
        (dest / ".vc_managed").write_text(version)

        # Try service registration
        exe = dest / "traefik.exe"
        if exe.exists():
            run_cmd([str(exe), "--configfile", str(cfg),
                     "--providers.file.directory", str(dest / "dynamic"),
                     "install", "--name", self._vc_svc(version)], timeout=20)

        return True

    def uninstall_vc(self, version: str) -> bool:
        self.stop_vc(version)
        dest = self.versions_root / version
        exe = dest / "traefik.exe"
        if exe.exists():
            run_cmd([str(exe), "uninstall", "--name", self._vc_svc(version)], timeout=10)
        shutil.rmtree(dest, ignore_errors=True)
        return True

    def start_vc(self, version: str) -> bool:
        if sc_start(self._vc_svc(version)):
            return True
        dest = self.versions_root / version
        exe = dest / "traefik.exe"
        cfg = dest / "traefik.yml"
        if not exe.exists():
            return False
        args = [str(exe)] + (["--configfile", str(cfg)] if cfg.exists() else [])
        return start_direct(args, dest / ".pid")

    def stop_vc(self, version: str) -> bool:
        dest = self.versions_root / version
        sc_stop(self._vc_svc(version))
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

    def _sys_pid_file(self) -> Path:
        base = Path(self._config.versions_dir) if self._config else Path.home() / ".vc"
        return base / "traefik_sys.pid"

    def info(self) -> ServiceInfo:
        svc, status = find_service(_SYS_SERVICES)
        self._svc_key = svc
        if status is None:
            if pid_running(self._sys_pid_file()):
                status = "running"
            else:
                status = "not_found" if not _find_sys_exe() else "stopped"
        cfg = _find_sys_conf()
        port = _read_port(cfg) if cfg else self.default_port
        ver = _get_sys_version()
        return ServiceInfo(status=status, version=ver, port=port,
                           config_path=cfg, service_key=svc)

    def start(self) -> bool:
        svc = self._ensure_svc()
        if svc and sc_start(svc):
            return True
        exe = _find_sys_exe()
        if not exe:
            return False
        cfg = _find_sys_conf()
        args = [exe] + (["--configfile", cfg] if cfg else [])
        return start_direct(args, self._sys_pid_file())

    def stop(self) -> bool:
        svc = self._ensure_svc()
        sc_stop(svc or "")
        stop_direct(self._sys_pid_file())
        return True

    def get_port(self) -> int:
        cfg = _find_sys_conf()
        return _read_port(cfg) if cfg else self.default_port

    def set_port(self, port: int) -> bool:
        cfg = _find_sys_conf()
        return _write_port(cfg, port) if cfg else False
