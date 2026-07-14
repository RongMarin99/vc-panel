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

EOL_API  = "https://endoflife.date/api/dotnet.json"
CDN_BASE = "https://dotnetcli.azureedge.net/dotnet/Sdk"


def _dl_filename(version: str) -> str:
    arch = "arm64" if get_arch() == "arm64" else "x64"
    if is_windows():
        return f"dotnet-sdk-{version}-win-{arch}.zip"
    elif is_mac():
        return f"dotnet-sdk-{version}-osx-{arch}.tar.gz"
    return f"dotnet-sdk-{version}-linux-{arch}.tar.gz"


class DotnetManager(BaseManager):
    name = "dotnet"
    display_name = ".NET"

    def __init__(self, config: Config):
        super().__init__(config.versions_dir)
        self.config = config
        self.shims_dir = config.shims_dir
        self._cache: list[VersionInfo] | None = None

    def list_remote(self) -> list[VersionInfo]:
        if self._cache:
            return self._cache
        try:
            resp = requests.get(EOL_API, timeout=10)
            resp.raise_for_status()
            versions = []
            for entry in resp.json():
                ver = entry.get("latest", "")
                if not ver:
                    continue
                versions.append(VersionInfo(
                    version=ver,
                    installed=self.is_installed(ver),
                    active=self.current() == ver,
                    release_date=entry.get("latestReleaseDate"),
                ))
            versions.sort(
                key=lambda v: [int(x) for x in re.split(r"[.+_\-]", v.version) if x.isdigit()],
                reverse=True,
            )
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

        filename = _dl_filename(version)
        url = f"{CDN_BASE}/{version}/{filename}"
        ext = ".zip" if is_windows() else ".tar.gz"
        tmp = self.versions_root / f"_dl_{version}{ext}"
        try:
            download_file(url, tmp, progress_callback)
            # .NET SDK zip has no root subfolder — extract flat
            extract_archive(tmp, self.install_path(version), strip_root=False)
            return True
        finally:
            tmp.unlink(missing_ok=True)

    def uninstall(self, version: str) -> bool:
        path = self.install_path(version)
        if path.exists():
            shutil.rmtree(path)
        if self.current() == version:
            self.config.set_active("dotnet", None)
            remove_shim(self.shims_dir, "dotnet")
        self._cache = None
        return True

    def use(self, version: str) -> bool:
        binary = self.get_binary_path(version)
        if not binary:
            return False
        self.config.set_active("dotnet", version)
        create_shim(self.shims_dir, "dotnet", binary)
        self._cache = None
        return True

    def current(self) -> Optional[str]:
        return self.config.get_active("dotnet")

    def get_binary_path(self, version: str) -> Optional[Path]:
        base = self.install_path(version)
        for candidate in ("dotnet.exe", "dotnet"):
            p = base / candidate
            if p.exists():
                return p
        return None
