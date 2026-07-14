import re
import shutil
from pathlib import Path
from typing import Optional, Callable

import requests

from core.base_manager import BaseManager, VersionInfo
from storage.config import Config
from utils.downloader import download_file, extract_archive
from utils.shell import create_shim, remove_shim
from utils.platform_utils import is_windows, is_mac, get_arch

ADOPTIUM_RELEASES = "https://api.adoptium.net/v3/info/available_releases"
ADOPTIUM_BINARY   = "https://api.adoptium.net/v3/binary/latest/{major}/ga/{os}/{arch}/jdk/hotspot/normal/adoptium"


def _major(version: str) -> str:
    return version.split(".")[0]


def _adoptium_os() -> str:
    if is_windows():
        return "windows"
    elif is_mac():
        return "mac"
    return "linux"


def _adoptium_arch() -> str:
    return "aarch64" if get_arch() == "arm64" else "x64"


class JavaManager(BaseManager):
    name = "java"
    display_name = "Java"

    def __init__(self, config: Config):
        super().__init__(config.versions_dir)
        self.config = config
        self.shims_dir = config.shims_dir
        self._cache: list[VersionInfo] | None = None

    def list_remote(self) -> list[VersionInfo]:
        if self._cache:
            return self._cache
        try:
            resp = requests.get(ADOPTIUM_RELEASES, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            available = data.get("available_releases", [])
            lts_set = set(data.get("available_lts_releases", []))
            versions = []
            for major in available:
                if major < 8:
                    continue
                ver = str(major)
                versions.append(VersionInfo(
                    version=ver,
                    installed=self.is_installed(ver),
                    active=self.current() == ver,
                    release_date="LTS" if major in lts_set else None,
                ))
            versions.sort(key=lambda v: int(v.version), reverse=True)
            self._cache = versions
            return versions
        except Exception:
            return self.list_installed()

    def list_installed(self) -> list[VersionInfo]:
        current = self.current()
        versions = []
        if self.versions_root.exists():
            for d in self.versions_root.iterdir():
                if d.is_dir():
                    versions.append(VersionInfo(
                        version=d.name, installed=True,
                        active=d.name == current, install_path=d,
                    ))
        versions.sort(key=lambda v: v.version, reverse=True)
        return versions

    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool:
        if self.is_installed(version):
            return True

        major = _major(version)
        os_id = _adoptium_os()
        arch = _adoptium_arch()
        url = ADOPTIUM_BINARY.format(major=major, os=os_id, arch=arch)

        ext = ".zip" if is_windows() else ".tar.gz"
        tmp = self.versions_root / f"_dl_{version}{ext}"
        try:
            # Adoptium URL redirects — requests follows automatically
            download_file(url, tmp, progress_callback)
            extract_archive(tmp, self.install_path(version), strip_root=True)
            return True
        finally:
            tmp.unlink(missing_ok=True)

    def uninstall(self, version: str) -> bool:
        path = self.install_path(version)
        if path.exists():
            shutil.rmtree(path)
        if self.current() == version:
            self.config.set_active("java", None)
            for tool in ("java", "javac", "jar"):
                remove_shim(self.shims_dir, tool)
        self._cache = None
        return True

    def use(self, version: str) -> bool:
        binary = self.get_binary_path(version)
        if not binary:
            return False
        self.config.set_active("java", version)
        bin_dir = binary.parent
        for tool in ("java", "javac", "jar"):
            exe = bin_dir / (f"{tool}.exe" if is_windows() else tool)
            if exe.exists():
                create_shim(self.shims_dir, tool, exe)
        self._cache = None
        return True

    def current(self) -> Optional[str]:
        return self.config.get_active("java")

    def get_binary_path(self, version: str) -> Optional[Path]:
        base = self.install_path(version)
        for candidate in ("bin/java.exe", "bin/java"):
            p = base / candidate
            if p.exists():
                return p
        return None
