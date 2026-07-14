import json
import re
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from providers.base_service import BaseService, ServiceInfo
from providers._svc_win import run_cmd, find_service, sc_start, sc_stop, start_direct, stop_direct, pid_running
from core.base_manager import VersionInfo

_SYS_SERVICES = ["MongoDB", "mongodb", "mongod"]

_CONF_CANDIDATES = [
    r"C:\Program Files\MongoDB\Server\7.0\bin\mongod.cfg",
    r"C:\Program Files\MongoDB\Server\6.0\bin\mongod.cfg",
    r"C:\Program Files\MongoDB\Server\5.0\bin\mongod.cfg",
    r"C:\Program Files\MongoDB\Server\4.4\bin\mongod.cfg",
    r"C:\mongodb\mongod.cfg",
]

_REMOTE = [
    ("7.0.9",  "2024-04-17"),
    ("7.0.8",  "2024-03-27"),
    ("6.0.15", "2024-04-17"),
    ("6.0.14", "2024-03-27"),
    ("5.0.26", "2024-03-27"),
    ("5.0.25", "2024-01-18"),
]


def _dl_url(version: str) -> str:
    return (
        f"https://fastdl.mongodb.org/windows/"
        f"mongodb-windows-x86_64-{version}.zip"
    )


def _find_sys_conf() -> str | None:
    base = Path(r"C:\Program Files\MongoDB\Server")
    if base.exists():
        for d in sorted(base.iterdir(), reverse=True):
            cfg = d / "bin" / "mongod.cfg"
            if cfg.exists():
                return str(cfg)
    for p in _CONF_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _read_port(conf_path: str) -> int:
    try:
        text = Path(conf_path).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^\s*port\s*:\s*(\d+)", text, re.MULTILINE)
        if not m:
            m = re.search(r"^\s*port\s*=\s*(\d+)", text, re.MULTILINE)
        return int(m.group(1)) if m else 27017
    except Exception:
        return 27017


def _write_port(conf_path: str, port: int) -> bool:
    try:
        text = Path(conf_path).read_text(encoding="utf-8", errors="replace")
        new, n = re.subn(r"(^\s*port\s*:\s*)\d+", rf"\g<1>{port}",
                         text, flags=re.MULTILINE)
        if n == 0:
            new, n = re.subn(r"(^\s*port\s*=\s*)\d+", rf"\g<1>{port}",
                             text, flags=re.MULTILINE)
        if n == 0:
            if re.search(r"^net\s*:", text, re.MULTILINE):
                new = re.sub(r"(^net\s*:\s*\n)", rf"\1  port: {port}\n",
                             text, count=1, flags=re.MULTILINE)
            else:
                new = text + f"\nnet:\n  port: {port}\n"
        Path(conf_path).write_text(new, encoding="utf-8")
        return True
    except Exception:
        return False


def _get_sys_version() -> str | None:
    for name in ("mongod", "mongo", "mongosh"):
        exe = shutil.which(name)
        if not exe:
            continue
        r = run_cmd([exe, "--version"])
        if not r:
            continue
        m = re.search(r"db version v?(\d+\.\d+\.\d+)", r.stdout + r.stderr, re.IGNORECASE)
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


class MongoDBService(BaseService):
    name = "mongodb"
    display_name = "MongoDB"
    icon = "🍃"
    default_port = 27017

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
        return f"VC-MongoDB-{version}"

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
            result.append(VersionInfo(version=d.name, installed=True, active=self.is_vc_running(d.name),
                                       install_path=d))
        return result

    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool:
        dest = self.versions_root / version
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        url = _dl_url(version)
        zip_path = dest / f"mongodb-{version}.zip"
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

        # Create data directory and config
        data_dir = dest / "data" / "db"
        data_dir.mkdir(parents=True, exist_ok=True)
        log_dir = dest / "data" / "log"
        log_dir.mkdir(parents=True, exist_ok=True)

        cfg = dest / "mongod.cfg"
        cfg.write_text(
            f"systemLog:\n"
            f"  destination: file\n"
            f"  path: {(log_dir / 'mongod.log').as_posix()}\n"
            f"storage:\n"
            f"  dbPath: {data_dir.as_posix()}\n"
            f"net:\n"
            f"  port: {self.default_port}\n",
            encoding="utf-8",
        )

        # Mark VC-managed
        (dest / ".vc_managed").write_text(version)

        # Try service registration
        mongod = dest / "bin" / "mongod.exe"
        if mongod.exists():
            run_cmd([str(mongod), "--config", str(cfg),
                     "--install", "--serviceName", self._vc_svc(version)], timeout=30)

        return True

    def uninstall_vc(self, version: str) -> bool:
        dest = self.versions_root / version
        self.stop_vc(version)
        svc = self._vc_svc(version)
        mongod = dest / "bin" / "mongod.exe"
        if mongod.exists():
            run_cmd([str(mongod), "--remove", "--serviceName", svc], timeout=30)
        shutil.rmtree(dest, ignore_errors=True)
        return True

    def start_vc(self, version: str) -> bool:
        if sc_start(self._vc_svc(version)):
            return True
        dest = self.versions_root / version
        mongod = dest / "bin" / "mongod.exe"
        cfg = dest / "mongod.cfg"
        if not mongod.exists():
            return False
        args = [str(mongod)] + (["--config", str(cfg)] if cfg.exists() else [])
        return start_direct(args, dest / ".pid")

    def stop_vc(self, version: str) -> bool:
        dest = self.versions_root / version
        sc_stop(self._vc_svc(version))
        # Graceful shutdown via mongod --shutdown
        mongod = dest / "bin" / "mongod.exe"
        cfg = dest / "mongod.cfg"
        data_dir = dest / "data" / "db"
        if mongod.exists():
            run_cmd([str(mongod), "--shutdown",
                     "--dbpath", str(data_dir)], timeout=15)
        stop_direct(dest / ".pid")
        return True

    def is_vc_running(self, version: str) -> bool:
        from providers._svc_win import sc_query
        if sc_query(self._vc_svc(version)) == "running":
            return True
        return pid_running(self.versions_root / version / ".pid")

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
