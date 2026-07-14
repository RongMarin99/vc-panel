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

GITHUB_API  = "https://api.github.com/repos/rust-lang/rust/releases?per_page=30"
DIST_BASE   = "https://static.rust-lang.org/dist"
_STABLE_RE  = re.compile(r"^\d+\.\d+\.\d+$")


def _target(version: str) -> str:
    arch = "aarch64" if get_arch() == "arm64" else "x86_64"
    if is_windows():
        return f"{arch}-pc-windows-msvc"
    elif is_mac():
        return f"{arch}-apple-darwin"
    return f"{arch}-unknown-linux-gnu"


class RustManager(BaseManager):
    name = "rust"
    display_name = "Rust"

    def __init__(self, config: Config):
        super().__init__(config.versions_dir)
        self.config = config
        self.shims_dir = config.shims_dir
        self._cache: list[VersionInfo] | None = None

    def list_remote(self) -> list[VersionInfo]:
        if self._cache:
            return self._cache
        try:
            r = requests.get(
                GITHUB_API, timeout=10,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            r.raise_for_status()
            versions = []
            for entry in r.json():
                tag = entry.get("tag_name", "").lstrip("v")
                if not _STABLE_RE.match(tag):
                    continue
                if entry.get("prerelease") or entry.get("draft"):
                    continue
                versions.append(VersionInfo(
                    version=tag,
                    installed=self.is_installed(tag),
                    active=self.current() == tag,
                    release_date=entry.get("published_at", "")[:10] or None,
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
        target = _target(version)
        if is_windows():
            filename = f"rust-{version}-{target}.zip"
            tmp = self.versions_root / f"_rust_{version}.zip"
        else:
            filename = f"rust-{version}-{target}.tar.gz"
            tmp = self.versions_root / f"_rust_{version}.tar.gz"
        url = f"{DIST_BASE}/{filename}"
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
            self.config.set_active("rust", None)
            for tool in ("rustc", "cargo", "rustfmt", "clippy-driver"):
                remove_shim(self.shims_dir, tool)
        self._cache = None
        return True

    def use(self, version: str) -> bool:
        base = self.install_path(version)
        if not base.exists():
            return False
        self.config.set_active("rust", version)
        # Rust dist zip extracts multiple component dirs — each has bin/
        ext = ".exe" if is_windows() else ""
        for component_dir in base.iterdir():
            if not component_dir.is_dir():
                continue
            bin_dir = component_dir / "bin"
            if not bin_dir.exists():
                continue
            for tool in ("rustc", "cargo", "rustfmt", "clippy-driver", "rust-gdb", "rust-lldb"):
                exe = bin_dir / f"{tool}{ext}"
                if exe.exists():
                    create_shim(self.shims_dir, tool, exe)
        self._cache = None
        return True

    def current(self) -> Optional[str]:
        return self.config.get_active("rust")

    def get_binary_path(self, version: str) -> Optional[Path]:
        base = self.install_path(version)
        for candidate in (
            "rustc/bin/rustc.exe", "rustc/bin/rustc",
            "bin/rustc.exe",        "bin/rustc",
        ):
            p = base / candidate
            if p.exists():
                return p
        return None
