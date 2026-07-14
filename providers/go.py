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

GO_DL_API  = "https://go.dev/dl/?mode=json&include=all"
GO_DL_BASE = "https://go.dev/dl"


class GoManager(BaseManager):
    name = "go"
    display_name = "Go"

    def __init__(self, config: Config):
        super().__init__(config.versions_dir)
        self.config = config
        self.shims_dir = config.shims_dir
        self._cache: list[VersionInfo] | None = None

    def list_remote(self) -> list[VersionInfo]:
        if self._cache:
            return self._cache
        try:
            r = requests.get(GO_DL_API, timeout=10)
            r.raise_for_status()
            versions = []
            for entry in r.json():
                if not entry.get("stable", True):
                    continue
                ver = entry.get("version", "").lstrip("go")
                if not ver:
                    continue
                versions.append(VersionInfo(
                    version=ver,
                    installed=self.is_installed(ver),
                    active=self.current() == ver,
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
        arch = "arm64" if get_arch() == "arm64" else "amd64"
        if is_windows():
            filename = f"go{version}.windows-{arch}.zip"
            tmp = self.versions_root / f"_go_{version}.zip"
        elif is_mac():
            filename = f"go{version}.darwin-{arch}.tar.gz"
            tmp = self.versions_root / f"_go_{version}.tar.gz"
        else:
            filename = f"go{version}.linux-{arch}.tar.gz"
            tmp = self.versions_root / f"_go_{version}.tar.gz"
        url = f"{GO_DL_BASE}/{filename}"
        try:
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
            self.config.set_active("go", None)
            for tool in ("go", "gofmt"):
                remove_shim(self.shims_dir, tool)
        self._cache = None
        return True

    def use(self, version: str) -> bool:
        binary = self.get_binary_path(version)
        if not binary:
            return False
        self.config.set_active("go", version)
        bin_dir = binary.parent
        for tool in ("go", "gofmt"):
            exe = bin_dir / (f"{tool}.exe" if is_windows() else tool)
            if exe.exists():
                create_shim(self.shims_dir, tool, exe)
        self._cache = None
        return True

    def current(self) -> Optional[str]:
        return self.config.get_active("go")

    def get_binary_path(self, version: str) -> Optional[Path]:
        base = self.install_path(version)
        for candidate in ("bin/go.exe", "bin/go"):
            p = base / candidate
            if p.exists():
                return p
        return None
