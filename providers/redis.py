import json
import re
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from providers.base_service import BaseService, ServiceInfo
from providers._svc_win import run_cmd, find_service, sc_start, sc_stop
from core.base_manager import VersionInfo

_SYS_SERVICES = ["Redis", "Redis-Server", "RedisServer", "redis"]

_CONF_CANDIDATES = [
    r"C:\Program Files\Redis\redis.windows-service.conf",
    r"C:\Program Files\Redis\redis.windows.conf",
    r"C:\Program Files\Redis\redis.conf",
    r"C:\Redis\redis.windows-service.conf",
    r"C:\Redis\redis.conf",
]

# tporadowski/redis Windows port releases
_REMOTE = [
    ("5.0.14.1", "2021-10-22"),
    ("5.0.10",   "2021-01-20"),
    ("5.0.9",    "2020-10-04"),
]

_GH_API = "https://api.github.com/repos/tporadowski/redis/releases"


def _dl_url(version: str) -> str:
    return (
        f"https://github.com/tporadowski/redis/releases/download/"
        f"v{version}/Redis-x64-{version}.zip"
    )


def _find_sys_conf() -> str | None:
    for p in _CONF_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _read_port(conf_path: str) -> int:
    try:
        text = Path(conf_path).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^\s*port\s+(\d+)", text, re.MULTILINE | re.IGNORECASE)
        return int(m.group(1)) if m else 6379
    except Exception:
        return 6379


def _write_port(conf_path: str, port: int) -> bool:
    try:
        text = Path(conf_path).read_text(encoding="utf-8", errors="replace")
        new, n = re.subn(r"(^\s*port\s+)\d+", rf"\g<1>{port}",
                         text, flags=re.MULTILINE | re.IGNORECASE)
        if n == 0:
            new += f"\nport {port}\n"
        Path(conf_path).write_text(new, encoding="utf-8")
        return True
    except Exception:
        return False


def _get_sys_version() -> str | None:
    for exe_name in ("redis-server", "redis-cli"):
        exe = shutil.which(exe_name)
        if not exe:
            continue
        r = run_cmd([exe, "--version"])
        if not r:
            continue
        m = re.search(r"v=(\d+\.\d+[\.\d]*)", r.stdout + r.stderr)
        if not m:
            m = re.search(r"(\d+\.\d+\.\d+)", r.stdout + r.stderr)
        if m:
            return m.group(1)
    return None


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
    """Extract all files from a flat zip (no root folder) into dest."""
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if member.filename.endswith("/"):
                (dest / member.filename).mkdir(parents=True, exist_ok=True)
            else:
                target = dest / member.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(member.filename))


class RedisService(BaseService):
    name = "redis"
    display_name = "Redis"
    icon = "🔴"
    default_port = 6379

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
        return f"VC-Redis-{version}"

    def list_remote(self) -> list[VersionInfo]:
        installed = {d.name for d in self.versions_root.iterdir()
                     if d.is_dir() and (d / ".vc_managed").exists()}
        # Try live fetch
        versions = list(_REMOTE)
        try:
            req = urllib.request.Request(_GH_API,
                headers={"User-Agent": "VC-VersionController/0.1"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                releases = json.loads(resp.read())
            versions = [
                (r["tag_name"].lstrip("v"), r.get("published_at", "")[:10])
                for r in releases
                if not r.get("prerelease") and not r.get("draft")
            ][:10]
        except Exception:
            pass

        result = []
        for ver, date in versions:
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
        zip_path = dest / f"redis-{version}.zip"
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

        # Create service config
        conf = dest / "redis.windows-service.conf"
        if not conf.exists():
            # Find any existing conf to copy
            for name in ("redis.windows.conf", "redis.conf"):
                src = dest / name
                if src.exists():
                    conf.write_bytes(src.read_bytes())
                    break
        if conf.exists():
            text = conf.read_text(encoding="utf-8", errors="replace")
            if "port" not in text.lower():
                conf.write_text(text + f"\nport {self.default_port}\n", encoding="utf-8")

        # Mark VC-managed
        (dest / ".vc_managed").write_text(version)

        # Try service registration
        server = dest / "redis-server.exe"
        if server.exists() and conf.exists():
            run_cmd([str(server), str(conf),
                     "--service-install",
                     "--service-name", self._vc_svc(version)], timeout=30)

        return True

    def uninstall_vc(self, version: str) -> bool:
        dest = self.versions_root / version
        svc = self._vc_svc(version)
        sc_stop(svc)
        server = dest / "redis-server.exe"
        conf = dest / "redis.windows-service.conf"
        if server.exists():
            run_cmd([str(server), str(conf) if conf.exists() else "",
                     "--service-uninstall",
                     "--service-name", svc], timeout=30)
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
