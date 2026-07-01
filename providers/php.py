import shutil
from pathlib import Path
from typing import Optional, Callable

import requests

from core.base_manager import BaseManager, VersionInfo
from storage.config import Config
from utils.downloader import download_file, extract_archive
from utils.shell import create_shim, remove_shim
from utils.platform_utils import is_windows, is_mac, get_arch


# PHP version → Visual C++ runtime used in Windows builds
_VC_MAP = {
    "8.3": "vs17", "8.2": "vs16", "8.1": "vs16",
    "8.0": "vs16", "7.4": "vc15", "7.3": "vc15",
}

WINDOWS_BASE = "https://windows.php.net/downloads/releases"
EOL_API      = "https://endoflife.date/api/php.json"


class PHPManager(BaseManager):
    name = "php"
    display_name = "PHP"

    def __init__(self, config: Config):
        super().__init__(config.versions_dir)
        self.config = config
        self.shims_dir = config.shims_dir
        self._cache: list[VersionInfo] | None = None

    def list_remote(self) -> list[VersionInfo]:
        if self._cache:
            return self._cache
        try:
            r = requests.get(EOL_API, timeout=10)
            r.raise_for_status()
            data = r.json()
            versions = []
            for entry in data:
                ver = entry.get("latest", "")
                if not ver:
                    continue
                parts = ver.split(".")
                if len(parts) < 2:
                    continue
                major, minor = int(parts[0]), int(parts[1])
                if major < 7 or (major == 7 and minor < 4):
                    continue
                versions.append(VersionInfo(
                    version=ver,
                    installed=self.is_installed(ver),
                    active=self.current() == ver,
                    release_date=entry.get("latestReleaseDate"),
                ))
            versions.sort(key=lambda v: [int(x) for x in v.version.split(".")], reverse=True)
            self._cache = versions
            return versions
        except Exception:
            return self.list_installed()

    def list_installed(self) -> list[VersionInfo]:
        current = self.current()
        result = []
        if self.versions_root.exists():
            for d in sorted(self.versions_root.iterdir(), reverse=True):
                if d.is_dir():
                    result.append(VersionInfo(
                        version=d.name, installed=True,
                        active=d.name == current, install_path=d,
                    ))
        return result

    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool:
        if self.is_installed(version):
            return True
        if is_windows():
            return self._install_windows(version, progress_callback)
        if is_mac():
            return self._install_mac(version)
        raise RuntimeError("Linux PHP install not yet supported")

    def _install_windows(self, version: str, cb=None) -> bool:
        parts = version.split(".")
        vc = _VC_MAP.get(f"{parts[0]}.{parts[1]}", "vs16")
        arch = get_arch()
        filename = f"php-{version}-nts-Win32-{vc}-{arch}.zip"
        url = f"{WINDOWS_BASE}/{filename}"
        tmp = self.versions_root / f"_{version}.zip"
        try:
            download_file(url, tmp, cb)
            dest = self.install_path(version)
            extract_archive(tmp, dest, strip_root=False)
            ini_src = dest / "php.ini-development"
            if ini_src.exists():
                shutil.copy2(ini_src, dest / "php.ini")
            return True
        finally:
            tmp.unlink(missing_ok=True)

    def _install_mac(self, version: str) -> bool:
        brew = shutil.which("brew")
        if not brew:
            raise RuntimeError("Homebrew required on macOS. Install: https://brew.sh")
        import subprocess
        major_minor = ".".join(version.split(".")[:2])
        r = subprocess.run([brew, "install", f"php@{major_minor}"], capture_output=True)
        return r.returncode == 0

    def uninstall(self, version: str) -> bool:
        path = self.install_path(version)
        if path.exists():
            shutil.rmtree(path)
        if self.current() == version:
            self.config.set_active("php", None)
            remove_shim(self.shims_dir, "php")
        if self._cache:
            self._cache = None
        return True

    def use(self, version: str) -> bool:
        if not self.is_installed(version):
            return False
        binary = self.get_binary_path(version)
        if not binary:
            return False
        self.config.set_active("php", version)
        create_shim(self.shims_dir, "php", binary)
        return True

    def current(self) -> Optional[str]:
        return self.config.get_active("php")

    def get_binary_path(self, version: str) -> Optional[Path]:
        base = self.install_path(version)
        for name in ["php.exe", "bin/php", "php"]:
            p = base / name
            if p.exists():
                return p
        return None
