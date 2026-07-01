import shutil
from pathlib import Path
from typing import Optional, Callable

import requests

from core.base_manager import BaseManager, VersionInfo
from storage.config import Config
from utils.downloader import download_file, extract_archive
from utils.shell import create_shim, remove_shim
from utils.platform_utils import is_windows, is_mac, get_arch

DIST_BASE = "https://nodejs.org/dist"
INDEX_URL = "https://nodejs.org/dist/index.json"


class NodeManager(BaseManager):
    name = "node"
    display_name = "Node.js"

    def __init__(self, config: Config):
        super().__init__(config.versions_dir)
        self.config = config
        self.shims_dir = config.shims_dir
        self._cache: list[VersionInfo] | None = None

    def list_remote(self) -> list[VersionInfo]:
        if self._cache:
            return self._cache
        try:
            r = requests.get(INDEX_URL, timeout=10)
            r.raise_for_status()
            data = r.json()
            versions = []
            for entry in data[:80]:
                v = entry["version"].lstrip("v")
                versions.append(VersionInfo(
                    version=v,
                    installed=self.is_installed(v),
                    active=self.current() == v,
                    release_date=entry.get("date"),
                ))
            self._cache = versions
            return versions
        except Exception:
            return []

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
        arch = get_arch()
        if is_windows():
            filename = f"node-v{version}-win-{arch}.zip"
            ext = ".zip"
        elif is_mac():
            filename = f"node-v{version}-darwin-{arch}.tar.gz"
            ext = ".tar.gz"
        else:
            filename = f"node-v{version}-linux-{arch}.tar.xz"
            ext = ".tar.xz"

        url = f"{DIST_BASE}/v{version}/{filename}"
        tmp = self.versions_root / f"_{version}{ext}"
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
            self.config.set_active("node", None)
            for tool in ["node", "npm", "npx"]:
                remove_shim(self.shims_dir, tool)
        if self._cache:
            self._cache = None
        return True

    def use(self, version: str) -> bool:
        if not self.is_installed(version):
            return False
        node = self.get_binary_path(version)
        if not node:
            return False
        self.config.set_active("node", version)
        create_shim(self.shims_dir, "node", node)
        bin_dir = node.parent
        for tool in ["npm", "npx"]:
            for name in [f"{tool}.cmd", tool]:
                p = bin_dir / name
                if p.exists():
                    create_shim(self.shims_dir, tool, p)
                    break
        return True

    def current(self) -> Optional[str]:
        return self.config.get_active("node")

    def get_binary_path(self, version: str) -> Optional[Path]:
        base = self.install_path(version)
        for name in ["node.exe", "bin/node", "node"]:
            p = base / name
            if p.exists():
                return p
        return None
