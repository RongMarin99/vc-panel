import shutil
import sys
import urllib.request
import zipfile
import re
from pathlib import Path
from typing import Callable, Optional

from providers.base_service import BaseService, ServiceInfo
from providers._svc_win import (
    run_cmd, find_service, sc_start, sc_stop,
    start_direct, stop_direct, pid_running,
    reg_enum_subkeys, reg_get,
)
from core.base_manager import VersionInfo

_SYS_SERVICES = ["MySQL80", "MySQL57", "MySQL56", "MySQL", "MySQL Server"]

_INI_CANDIDATES = [
    r"C:\ProgramData\MySQL\MySQL Server 8.0\my.ini",
    r"C:\ProgramData\MySQL\MySQL Server 8.1\my.ini",
    r"C:\ProgramData\MySQL\MySQL Server 5.7\my.ini",
    r"C:\Program Files\MySQL\MySQL Server 8.0\my.ini",
    r"C:\Program Files\MySQL\MySQL Server 5.7\my.ini",
    r"C:\xampp\mysql\bin\my.ini",
    r"C:\laragon\bin\mysql\mysql-8.0.30-winx64\my.ini",
]

# (version, release_date)
_REMOTE = [
    ("8.4.0", "2024-04-30"),
    ("8.3.0", "2024-01-16"),
    ("8.2.0", "2023-10-25"),
    ("8.1.0", "2023-07-18"),
    ("8.0.37", "2024-04-30"),
    ("8.0.36", "2024-01-16"),
    ("5.7.44", "2023-10-25"),
]


def _dl_url(version: str) -> str:
    parts = version.split(".")
    major_minor = f"{parts[0]}.{parts[1]}"
    return (
        f"https://cdn.mysql.com/Downloads/MySQL-{major_minor}"
        f"/mysql-{version}-winx64.zip"
    )


def _find_sys_ini() -> str | None:
    for root in [r"SOFTWARE\MySQL AB", r"SOFTWARE\WOW6432Node\MySQL AB"]:
        for sub in reg_enum_subkeys(root):
            if not sub.startswith("MySQL Server"):
                continue
            for key in ("Location", "DataLocation"):
                loc = reg_get(rf"{root}\{sub}", key)
                if loc:
                    for name in ("my.ini", "my.cnf"):
                        p = Path(loc) / name
                        if p.exists():
                            return str(p)
    for p in _INI_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _read_port(ini_path: str) -> int:
    try:
        text = Path(ini_path).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^\s*port\s*=\s*(\d+)", text, re.MULTILINE | re.IGNORECASE)
        return int(m.group(1)) if m else 3306
    except Exception:
        return 3306


def _write_port(ini_path: str, port: int) -> bool:
    try:
        text = Path(ini_path).read_text(encoding="utf-8", errors="replace")
        new, n = re.subn(
            r"(^\s*port\s*=\s*)\d+", rf"\g<1>{port}",
            text, flags=re.MULTILINE | re.IGNORECASE,
        )
        if n == 0:
            new = re.sub(r"(\[mysqld\])", rf"\1\nport={port}", new, count=1)
        Path(ini_path).write_text(new, encoding="utf-8")
        return True
    except Exception:
        return False


def _get_sys_version() -> str | None:
    exe = shutil.which("mysql")
    if not exe:
        return None
    r = run_cmd([exe, "--version"])
    if not r:
        return None
    m = re.search(r"(\d+\.\d+\.\d+)", r.stdout + r.stderr)
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


_PMA_VERSION = "5.2.1"
_PMA_URL = (
    "https://files.phpmyadmin.net/phpMyAdmin/{v}/phpMyAdmin-{v}-english.zip"
)

_PMA_CANDIDATES = [
    Path(r"C:\laragon\etc\apps\phpMyAdmin"),
    Path(r"C:\xampp\phpMyAdmin"),
    Path(r"C:\wamp64\apps\phpmyadmin5.2.1"),
    Path(r"C:\wamp\apps\phpmyadmin5.2.1"),
]


def find_phpmyadmin_dir() -> Optional[Path]:
    """Return best target directory for phpMyAdmin (parent must exist)."""
    for c in _PMA_CANDIDATES:
        if c.parent.exists():
            return c
    return None


def phpmyadmin_installed() -> bool:
    d = find_phpmyadmin_dir()
    return bool(d and (d / "index.php").exists())


def setup_phpmyadmin(version: str, port: int = 3306,
                     progress_callback: Optional[Callable] = None) -> bool:
    """Download, extract, and configure phpMyAdmin."""
    target = find_phpmyadmin_dir()
    if not target:
        raise RuntimeError(
            "No supported web stack found.\n"
            "Install Laragon or XAMPP first, then try again."
        )

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    url = _PMA_URL.format(v=version)
    tmp = target / f"pma-{version}.zip"
    try:
        _download(url, tmp, progress_callback)
    except Exception as e:
        shutil.rmtree(target, ignore_errors=True)
        raise RuntimeError(f"Download failed: {e}")

    try:
        with zipfile.ZipFile(tmp) as zf:
            names = [m.filename for m in zf.infolist()]
            top_dirs = {n.split("/")[0] for n in names if "/" in n}
            strip = (next(iter(top_dirs)) + "/") if len(top_dirs) == 1 else ""
            for member in zf.infolist():
                rel = member.filename
                if strip and rel.startswith(strip):
                    rel = rel[len(strip):]
                if not rel:
                    continue
                t = target / rel
                if member.filename.endswith("/"):
                    t.mkdir(parents=True, exist_ok=True)
                else:
                    t.parent.mkdir(parents=True, exist_ok=True)
                    t.write_bytes(zf.read(member.filename))
    except Exception as e:
        shutil.rmtree(target, ignore_errors=True)
        raise RuntimeError(f"Extraction failed: {e}")
    finally:
        tmp.unlink(missing_ok=True)

    # Write config.inc.php tuned for VC-managed MySQL
    (target / "config.inc.php").write_text(
        "<?php\n"
        "$cfg['blowfish_secret'] = 'vc-pma-key-change-in-production-env';\n"
        "$i = 0;\n"
        "$i++;\n"
        "$cfg['Servers'][$i]['auth_type'] = 'cookie';\n"
        f"$cfg['Servers'][$i]['host'] = '127.0.0.1';\n"
        f"$cfg['Servers'][$i]['port'] = '{port}';\n"
        "$cfg['Servers'][$i]['connect_type'] = 'tcp';\n"
        "$cfg['Servers'][$i]['compress'] = false;\n"
        "$cfg['Servers'][$i]['AllowNoPassword'] = true;\n"
        "$cfg['UploadDir'] = '';\n"
        "$cfg['SaveDir'] = '';\n",
        encoding="utf-8",
    )
    return True


class MySQLService(BaseService):
    name = "mysql"
    display_name = "MySQL"
    icon = "🐬"
    default_port = 3306

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
        return f"VC-MySQL-{version}"

    # ── version management ────────────────────────────────────────────────────

    def list_remote(self) -> list[VersionInfo]:
        installed = {d.name for d in self.versions_root.iterdir()
                     if d.is_dir() and (d / ".vc_managed").exists()}
        result = []
        for ver, date in _REMOTE:
            inst = ver in installed
            active = self.is_vc_running(ver) if inst else False
            result.append(VersionInfo(
                version=ver, installed=inst, active=active,
                release_date=date,
                install_path=self.versions_root / ver if inst else None,
            ))
        return result

    def list_installed_vc(self) -> list[VersionInfo]:
        result = []
        for d in sorted(self.versions_root.iterdir(), reverse=True):
            if not (d.is_dir() and (d / ".vc_managed").exists()):
                continue
            result.append(VersionInfo(version=d.name, installed=True, active=self.is_vc_running(d.name),
                                       install_path=d))
        return result

    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool:
        dest = self.versions_root / version
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        url = _dl_url(version)
        zip_path = dest / f"mysql-{version}.zip"
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

        # Create my.ini
        data_dir = dest / "data"
        data_dir.mkdir(exist_ok=True)
        ini = dest / "my.ini"
        ini.write_text(
            f"[mysqld]\n"
            f"basedir={dest.as_posix()}\n"
            f"datadir={data_dir.as_posix()}\n"
            f"port={self.default_port}\n"
            f"[client]\n"
            f"port={self.default_port}\n",
            encoding="utf-8",
        )

        # Initialize data directory (may require admin, ignore error)
        mysqld = dest / "bin" / "mysqld.exe"
        if mysqld.exists():
            run_cmd([str(mysqld), "--initialize-insecure",
                     f"--basedir={dest}", f"--datadir={data_dir}"], timeout=120)

        # Mark VC-managed
        (dest / ".vc_managed").write_text(version)

        # Try service registration (requires admin)
        if mysqld.exists():
            run_cmd([str(mysqld), "--install", self._vc_svc(version),
                     f"--defaults-file={ini}"], timeout=30)

        return True

    def uninstall_vc(self, version: str) -> bool:
        dest = self.versions_root / version
        self.stop_vc(version)
        svc = self._vc_svc(version)
        mysqld = dest / "bin" / "mysqld.exe"
        if mysqld.exists():
            run_cmd([str(mysqld), "--remove", svc], timeout=30)
        shutil.rmtree(dest, ignore_errors=True)
        return True

    def start_vc(self, version: str) -> bool:
        # Try registered service first; fall back to direct binary (no admin needed)
        if sc_start(self._vc_svc(version)):
            return True
        dest = self.versions_root / version
        mysqld = dest / "bin" / "mysqld.exe"
        ini = dest / "my.ini"
        if not mysqld.exists():
            return False
        args = [str(mysqld), f"--defaults-file={ini}"]
        return start_direct(args, dest / ".pid")

    def stop_vc(self, version: str) -> bool:
        dest = self.versions_root / version
        sc_stop(self._vc_svc(version))

        # Graceful shutdown first — must run BEFORE killing the process
        ini = dest / "my.ini"
        admin = dest / "bin" / "mysqladmin.exe"
        if admin.exists() and ini.exists():
            run_cmd([str(admin), f"--defaults-file={ini}",
                     "-uroot", "--host=127.0.0.1", "shutdown"], timeout=15)

        # Force-kill tracked PID as fallback
        stop_direct(dest / ".pid")

        # Kill orphaned mysqld processes from this version dir
        # MySQL on Windows spawns a second process not captured in .pid
        if sys.platform == "win32":
            mysqld_path = str(dest / "bin" / "mysqld.exe")
            run_cmd([
                "powershell", "-NoProfile", "-Command",
                f"Get-Process mysqld -ErrorAction SilentlyContinue "
                f"| Where-Object {{ $_.Path -eq '{mysqld_path}' }} "
                f"| Stop-Process -Force",
            ], timeout=10)
        return True

    def is_vc_running(self, version: str) -> bool:
        from providers._svc_win import sc_query
        if sc_query(self._vc_svc(version)) == "running":
            return True
        return pid_running(self.versions_root / version / ".pid")

    # ── service management (system-installed) ─────────────────────────────────

    def _ensure_svc(self) -> str | None:
        if not self._svc_key:
            svc, _ = find_service(_SYS_SERVICES)
            self._svc_key = svc
        return self._svc_key

    def info(self) -> ServiceInfo:
        svc, status = find_service(_SYS_SERVICES)
        self._svc_key = svc
        cfg = _find_sys_ini()
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
        cfg = _find_sys_ini()
        return _read_port(cfg) if cfg else self.default_port

    def set_port(self, port: int) -> bool:
        cfg = _find_sys_ini()
        return _write_port(cfg, port) if cfg else False
