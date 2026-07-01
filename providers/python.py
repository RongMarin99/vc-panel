import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Optional, Callable

import requests

from core.base_manager import BaseManager, VersionInfo
from storage.config import Config
from utils.downloader import download_file, extract_archive
from utils.shell import create_shim, remove_shim
from utils.platform_utils import is_windows, is_mac, get_arch

FTP_BASE = "https://www.python.org/ftp/python"
EOL_API = "https://endoflife.date/api/python.json"


class PythonManager(BaseManager):
    name = "python"
    display_name = "Python"

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
                v = entry["latest"]
                versions.append(VersionInfo(
                    version=v,
                    installed=self.is_installed(v),
                    active=self.current() == v,
                    release_date=entry.get("releaseDate"),
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
        if is_windows():
            return self._install_windows(version, progress_callback)
        if is_mac():
            return self._install_mac(version)
        raise RuntimeError("Linux Python install not yet supported")

    def _install_windows(self, version: str, cb=None) -> bool:
        filename = f"python-{version}-embed-amd64.zip"
        url = f"{FTP_BASE}/{version}/{filename}"
        tmp = self.versions_root / f"_{version}.zip"
        try:
            download_file(url, tmp, cb)
            dest = self.install_path(version)
            extract_archive(tmp, dest, strip_root=False)
            self._bootstrap_pip(dest, version)
            return True
        finally:
            tmp.unlink(missing_ok=True)

    def _bootstrap_pip(self, install_dir: Path, version: str):
        # Uncomment 'import site' in the ._pth file so pip works
        for pth in install_dir.glob("python*._pth"):
            text = pth.read_text()
            pth.write_text(text.replace("#import site", "import site"))

        get_pip = install_dir / "get-pip.py"
        try:
            urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", str(get_pip))
        except Exception:
            return  # pip bootstrap optional; python still usable without it

        python_exe = install_dir / "python.exe"
        if python_exe.exists():
            subprocess.run([str(python_exe), str(get_pip)], cwd=str(install_dir),
                           capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)

    def _install_mac(self, version: str) -> bool:
        brew = shutil.which("brew")
        if not brew:
            raise RuntimeError("Homebrew required on macOS. Install: https://brew.sh")
        major_minor = ".".join(version.split(".")[:2])
        r = subprocess.run([brew, "install", f"python@{major_minor}"], capture_output=True)
        return r.returncode == 0

    def uninstall(self, version: str) -> bool:
        path = self.install_path(version)
        if path.exists():
            shutil.rmtree(path)
        if self.current() == version:
            self.config.set_active("python", None)
            for tool in ["python", "pip"]:
                remove_shim(self.shims_dir, tool)
        if self._cache:
            self._cache = None
        return True

    def use(self, version: str) -> bool:
        if not self.is_installed(version):
            return False
        binary = self.get_binary_path(version)
        if not binary:
            return False
        self.config.set_active("python", version)
        create_shim(self.shims_dir, "python", binary)
        bin_dir = binary.parent
        for pip_name in ["pip.exe", "pip3.exe", "pip", "pip3"]:
            p = bin_dir / pip_name
            if p.exists():
                create_shim(self.shims_dir, "pip", p)
                break
        return True

    def current(self) -> Optional[str]:
        return self.config.get_active("python")

    def get_binary_path(self, version: str) -> Optional[Path]:
        base = self.install_path(version)
        for name in ["python.exe", "python3.exe", "bin/python3", "bin/python"]:
            p = base / name
            if p.exists():
                return p
        return None
