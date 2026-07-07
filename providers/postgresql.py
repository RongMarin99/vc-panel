import shutil
import re
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from providers.base_service import BaseService, ServiceInfo
from providers._svc_win import run_cmd, find_service, sc_start, sc_stop, reg_enum_subkeys, reg_get
from core.base_manager import VersionInfo

_SYS_SERVICES = [
    "postgresql-x64-16", "postgresql-x64-15", "postgresql-x64-14",
    "postgresql-x64-13", "postgresql-x64-12", "postgresql", "PostgreSQL",
]

_CONF_CANDIDATES = [
    r"C:\Program Files\PostgreSQL\16\data\postgresql.conf",
    r"C:\Program Files\PostgreSQL\15\data\postgresql.conf",
    r"C:\Program Files\PostgreSQL\14\data\postgresql.conf",
    r"C:\Program Files\PostgreSQL\13\data\postgresql.conf",
]

_REMOTE = [
    ("16.3", "2024-05-09"),
    ("16.2", "2024-02-08"),
    ("15.7", "2024-05-09"),
    ("15.6", "2024-02-08"),
    ("14.12", "2024-05-09"),
    ("14.11", "2024-02-08"),
    ("13.15", "2024-05-09"),
    ("13.14", "2024-02-08"),
]


def _dl_url(version: str) -> str:
    return (
        f"https://get.enterprisedb.com/postgresql/"
        f"postgresql-{version}-1-windows-x64-binaries.zip"
    )


def _find_sys_conf() -> str | None:
    for sub in reg_enum_subkeys(r"SOFTWARE\PostgreSQL\Installations"):
        data = reg_get(rf"SOFTWARE\PostgreSQL\Installations\{sub}", "Data Directory")
        if data:
            conf = Path(data) / "postgresql.conf"
            if conf.exists():
                return str(conf)
    for p in _CONF_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _read_port(conf_path: str) -> int:
    try:
        text = Path(conf_path).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^\s*port\s*=\s*(\d+)", text, re.MULTILINE)
        return int(m.group(1)) if m else 5432
    except Exception:
        return 5432


def _write_port(conf_path: str, port: int) -> bool:
    try:
        text = Path(conf_path).read_text(encoding="utf-8", errors="replace")
        new, n = re.subn(r"^#?\s*(port\s*=\s*)\d+", rf"\g<1>{port}",
                         text, flags=re.MULTILINE)
        if n == 0:
            new += f"\nport = {port}\n"
        Path(conf_path).write_text(new, encoding="utf-8")
        return True
    except Exception:
        return False


def _get_sys_version() -> str | None:
    exe = shutil.which("psql")
    if not exe:
        return None
    r = run_cmd([exe, "--version"])
    if not r:
        return None
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", r.stdout + r.stderr)
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


class PostgreSQLService(BaseService):
    name = "postgresql"
    display_name = "PostgreSQL"
    icon = "🐘"
    default_port = 5432

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
        return f"VC-PostgreSQL-{version}"

    def list_remote(self) -> list[VersionInfo]:
        installed = {d.name for d in self.versions_root.iterdir()
                     if d.is_dir() and (d / ".vc_managed").exists()}
        result = []
        for ver, date in _REMOTE:
            inst = ver in installed
            active = False
            if inst:
                from providers._svc_win import sc_query
                active = sc_query(self._vc_svc(ver)) == "running"
            result.append(VersionInfo(version=ver, installed=inst, active=active,
                                       release_date=date,
                                       install_path=self.versions_root / ver if inst else None))
        return result

    def list_installed_vc(self) -> list[VersionInfo]:
        result = []
        for d in sorted(self.versions_root.iterdir(), reverse=True):
            if not (d.is_dir() and (d / ".vc_managed").exists()):
                continue
            from providers._svc_win import sc_query
            active = sc_query(self._vc_svc(d.name)) == "running"
            result.append(VersionInfo(version=d.name, installed=True, active=active,
                                       install_path=d))
        return result

    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool:
        dest = self.versions_root / version
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        url = _dl_url(version)
        zip_path = dest / f"postgresql-{version}.zip"
        try:
            _download(url, zip_path, progress_callback)
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Download failed: {e}")

        try:
            # EnterpriseDB zip has a pgsql/ root directory
            _extract_strip_root(zip_path, dest)
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Extraction failed: {e}")
        finally:
            zip_path.unlink(missing_ok=True)

        # Initialize data directory
        data_dir = dest / "data"
        initdb = dest / "bin" / "initdb.exe"
        if initdb.exists():
            run_cmd([str(initdb), "-D", str(data_dir), "-U", "postgres",
                     "--no-locale", "--encoding=UTF8"], timeout=120)

        # Mark VC-managed
        (dest / ".vc_managed").write_text(version)

        # Try service registration
        pg_ctl = dest / "bin" / "pg_ctl.exe"
        if pg_ctl.exists() and data_dir.exists():
            run_cmd([str(pg_ctl), "register",
                     "-N", self._vc_svc(version),
                     "-D", str(data_dir)], timeout=30)

        return True

    def uninstall_vc(self, version: str) -> bool:
        dest = self.versions_root / version
        svc = self._vc_svc(version)
        sc_stop(svc)
        pg_ctl = dest / "bin" / "pg_ctl.exe"
        if pg_ctl.exists():
            run_cmd([str(pg_ctl), "unregister", "-N", svc], timeout=30)
        shutil.rmtree(dest, ignore_errors=True)
        return True

    def start_vc(self, version: str) -> bool:
        return sc_start(self._vc_svc(version))

    def stop_vc(self, version: str) -> bool:
        return sc_stop(self._vc_svc(version))

    def _ensure_svc(self) -> str | None:
        if not self._svc_key:
            svc, _ = find_service(_SYS_SERVICES)
            self._svc_key = svc
        return self._svc_key

    def info(self) -> ServiceInfo:
        svc, status = find_service(_SYS_SERVICES)
        self._svc_key = svc
        cfg = _find_sys_conf()
        port = _read_port(cfg) if cfg else self.default_port
        ver = _get_sys_version()
        return ServiceInfo(status=status or "not_found", version=ver,
                           port=port, config_path=cfg, service_key=svc)

    def start(self) -> bool:
        svc = self._ensure_svc()
        return sc_start(svc) if svc else False

    def stop(self) -> bool:
        svc = self._ensure_svc()
        return sc_stop(svc) if svc else False

    def get_port(self) -> int:
        cfg = _find_sys_conf()
        return _read_port(cfg) if cfg else self.default_port

    def set_port(self, port: int) -> bool:
        cfg = _find_sys_conf()
        return _write_port(cfg, port) if cfg else False
