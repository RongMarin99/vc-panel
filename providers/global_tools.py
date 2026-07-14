"""Global CLI tool providers: pnpm, bun, deno, uv, yarn, composer."""
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


@dataclass
class ToolVersion:
    version: str
    installed: bool = False
    active: bool = False
    release_date: str = ""


class BaseTool(ABC):
    name: str
    display_name: str
    icon: str
    exe_name: str
    description: str = ""

    def __init__(self, config=None):
        self._config = config

    @property
    def tools_root(self) -> Path:
        base = Path(self._config.tools_dir) if self._config else Path.home() / ".vc" / "tools"
        root = base / self.name
        root.mkdir(parents=True, exist_ok=True)
        return root

    @property
    def shims_dir(self) -> Path:
        d = Path(self._config.shims_dir) if self._config else Path.home() / ".vc" / "shims"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def current(self) -> Optional[str]:
        f = self.tools_root / ".active"
        if not f.exists():
            return None
        v = f.read_text().strip()
        return v or None

    def _exe_path(self, version: str) -> Optional[Path]:
        d = self.tools_root / version
        for name in (f"{self.exe_name}.exe", self.exe_name):
            p = d / name
            if p.exists():
                return p
        return None

    def _write_shim(self, version: str) -> bool:
        exe = self._exe_path(version)
        if not exe:
            return False
        (self.shims_dir / f"{self.exe_name}.cmd").write_text(
            f'@echo off\n"{exe}" %*\n', encoding="utf-8"
        )
        return True

    def _write_node_shim(self, version: str, js_rel: str) -> bool:
        js = self.tools_root / version / js_rel
        if not js.exists():
            return False
        (self.shims_dir / f"{self.exe_name}.cmd").write_text(
            f'@echo off\nnode "{js}" %*\n', encoding="utf-8"
        )
        return True

    def _write_php_shim(self, version: str, phar_rel: str) -> bool:
        phar = self.tools_root / version / phar_rel
        if not phar.exists():
            return False
        (self.shims_dir / f"{self.exe_name}.cmd").write_text(
            f'@echo off\nphp "{phar}" %*\n', encoding="utf-8"
        )
        return True

    def use(self, version: str) -> bool:
        (self.tools_root / ".active").write_text(version)
        return self._write_shim(version)

    def uninstall(self, version: str) -> bool:
        shutil.rmtree(self.tools_root / version, ignore_errors=True)
        if self.current() == version:
            (self.tools_root / ".active").unlink(missing_ok=True)
            (self.shims_dir / f"{self.exe_name}.cmd").unlink(missing_ok=True)
        return True

    def detect_system(self) -> Optional[str]:
        exe = shutil.which(self.exe_name)
        if not exe:
            return None
        try:
            if str(self.shims_dir).lower() in exe.lower():
                return None  # our own shim
        except Exception:
            pass
        try:
            r = subprocess.run(
                [exe, "--version"], capture_output=True, text=True,
                timeout=5, creationflags=_FLAGS,
            )
            m = re.search(r"(\d+\.\d+[\.\d]*)", r.stdout + r.stderr)
            return m.group(1) if m else "installed"
        except Exception:
            return "installed"

    def list_versions(self) -> list[ToolVersion]:
        installed = {
            d.name for d in self.tools_root.iterdir()
            if d.is_dir() and (d / ".installed").exists()
        }
        active = self.current()
        return [
            ToolVersion(
                version=ver,
                installed=ver in installed,
                active=(ver == active and ver in installed),
                release_date=date,
            )
            for ver, date in self._remote_versions()
        ]

    @abstractmethod
    def _remote_versions(self) -> list[tuple[str, str]]:
        ...

    @abstractmethod
    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool:
        ...

    def _download(self, url: str, dest: Path,
                  progress_cb: Optional[Callable] = None,
                  extra_headers: Optional[dict] = None):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/octet-stream, application/zip, */*",
        }
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=180) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress_cb and total > 0:
                        progress_cb(done, total)

    def _extract_zip_flat(self, zip_path: Path, dest: Path):
        """Extract zip, stripping any single top-level dir."""
        with zipfile.ZipFile(zip_path) as zf:
            names = [m.filename for m in zf.infolist()]
            top_dirs = {n.split("/")[0] for n in names if "/" in n}
            strip = ""
            if len(top_dirs) == 1:
                candidate = next(iter(top_dirs)) + "/"
                if all(n.startswith(candidate) or "/" not in n for n in names):
                    strip = candidate
            for member in zf.infolist():
                rel = member.filename
                if strip and rel.startswith(strip):
                    rel = rel[len(strip):]
                if not rel:
                    continue
                target = dest / rel
                if member.filename.endswith("/"):
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(member.filename))

    def _extract_tgz(self, tgz_path: Path, dest: Path):
        """Extract tar.gz, stripping the single top-level dir."""
        with tarfile.open(tgz_path, "r:gz") as tf:
            members = tf.getmembers()
            top_dirs = {m.name.split("/")[0] for m in members if "/" in m.name}
            strip = (next(iter(top_dirs)) + "/") if len(top_dirs) == 1 else ""
            for member in members:
                rel = member.name
                if strip and rel.startswith(strip):
                    rel = rel[len(strip):]
                if not rel:
                    continue
                target = dest / rel
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    f = tf.extractfile(member)
                    if f:
                        target.write_bytes(f.read())


# ── pnpm ──────────────────────────────────────────────────────────────────────

class PnpmTool(BaseTool):
    name = "pnpm"
    display_name = "pnpm"
    icon = "📦"
    exe_name = "pnpm"
    description = "Fast, disk space efficient package manager for Node.js"

    _VERSIONS = [
        ("9.5.0",  "2024-07-15"),
        ("9.4.0",  "2024-07-01"),
        ("9.3.0",  "2024-06-15"),
        ("9.2.0",  "2024-05-28"),
        ("9.1.4",  "2024-05-14"),
        ("8.15.9", "2024-07-01"),
        ("8.15.6", "2024-06-01"),
    ]

    def _remote_versions(self):
        return self._VERSIONS

    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool:
        dest = self.tools_root / version
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        url = f"https://github.com/pnpm/pnpm/releases/download/v{version}/pnpm-win-x64.exe"
        try:
            self._download(url, dest / "pnpm.exe", progress_callback)
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Download failed: {e}")

        (dest / ".installed").write_text(version)
        if not self.current():
            self.use(version)
        return True

    def use(self, version: str) -> bool:
        (self.tools_root / ".active").write_text(version)
        return self._write_shim(version)


# ── bun ───────────────────────────────────────────────────────────────────────

class BunTool(BaseTool):
    name = "bun"
    display_name = "Bun"
    icon = "🍞"
    exe_name = "bun"
    description = "Incredibly fast JavaScript runtime, bundler, and package manager"

    _VERSIONS = [
        ("1.1.21", "2024-07-15"),
        ("1.1.18", "2024-07-01"),
        ("1.1.13", "2024-06-01"),
        ("1.1.8",  "2024-05-01"),
        ("1.0.35", "2024-03-15"),
    ]

    def _remote_versions(self):
        return self._VERSIONS

    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool:
        dest = self.tools_root / version
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        url = (
            f"https://github.com/oven-sh/bun/releases/download/"
            f"bun-v{version}/bun-windows-x64.zip"
        )
        zip_path = dest / "bun.zip"
        try:
            self._download(url, zip_path, progress_callback)
            self._extract_zip_flat(zip_path, dest)
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Install failed: {e}")
        finally:
            zip_path.unlink(missing_ok=True)

        (dest / ".installed").write_text(version)
        if not self.current():
            self.use(version)
        return True

    def use(self, version: str) -> bool:
        (self.tools_root / ".active").write_text(version)
        return self._write_shim(version)


# ── deno ──────────────────────────────────────────────────────────────────────

class DenoTool(BaseTool):
    name = "deno"
    display_name = "Deno"
    icon = "🦕"
    exe_name = "deno"
    description = "Secure runtime for JavaScript and TypeScript built on V8"

    _VERSIONS = [
        ("1.45.3", "2024-07-17"),
        ("1.44.4", "2024-06-20"),
        ("1.43.6", "2024-05-29"),
        ("1.42.4", "2024-04-25"),
        ("1.41.3", "2024-03-28"),
    ]

    def _remote_versions(self):
        return self._VERSIONS

    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool:
        dest = self.tools_root / version
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        url = (
            f"https://github.com/denoland/deno/releases/download/"
            f"v{version}/deno-x86_64-pc-windows-msvc.zip"
        )
        zip_path = dest / "deno.zip"
        try:
            self._download(url, zip_path, progress_callback)
            self._extract_zip_flat(zip_path, dest)
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Install failed: {e}")
        finally:
            zip_path.unlink(missing_ok=True)

        (dest / ".installed").write_text(version)
        if not self.current():
            self.use(version)
        return True

    def use(self, version: str) -> bool:
        (self.tools_root / ".active").write_text(version)
        return self._write_shim(version)


# ── uv ────────────────────────────────────────────────────────────────────────

class UvTool(BaseTool):
    name = "uv"
    display_name = "uv"
    icon = "⚡"
    exe_name = "uv"
    description = "Extremely fast Python package and project manager written in Rust"

    _VERSIONS = [
        ("0.3.0",  "2024-07-19"),
        ("0.2.37", "2024-07-15"),
        ("0.2.36", "2024-07-12"),
        ("0.2.35", "2024-07-10"),
        ("0.2.20", "2024-06-04"),
    ]

    def _remote_versions(self):
        return self._VERSIONS

    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool:
        dest = self.tools_root / version
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        url = (
            f"https://github.com/astral-sh/uv/releases/download/"
            f"{version}/uv-x86_64-pc-windows-msvc.zip"
        )
        zip_path = dest / "uv.zip"
        try:
            self._download(url, zip_path, progress_callback)
            self._extract_zip_flat(zip_path, dest)
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Install failed: {e}")
        finally:
            zip_path.unlink(missing_ok=True)

        # Also write uvx shim if uvx.exe exists
        uvx = dest / "uvx.exe"
        if uvx.exists():
            (self.shims_dir / "uvx.cmd").write_text(
                f'@echo off\n"{uvx}" %*\n', encoding="utf-8"
            )

        (dest / ".installed").write_text(version)
        if not self.current():
            self.use(version)
        return True

    def use(self, version: str) -> bool:
        (self.tools_root / ".active").write_text(version)
        ok = self._write_shim(version)
        # Also update uvx shim
        uvx = self.tools_root / version / "uvx.exe"
        if uvx.exists():
            (self.shims_dir / "uvx.cmd").write_text(
                f'@echo off\n"{uvx}" %*\n', encoding="utf-8"
            )
        return ok


# ── yarn (classic 1.x) ───────────────────────────────────────────────────────

class YarnTool(BaseTool):
    name = "yarn"
    display_name = "Yarn"
    icon = "🧶"
    exe_name = "yarn"
    description = "Fast, reliable, and secure dependency management for Node.js (requires Node.js)"

    _VERSIONS = [
        ("1.22.22", "2023-11-06"),
        ("1.22.21", "2023-09-20"),
        ("1.22.19", "2021-09-10"),
    ]

    def _remote_versions(self):
        return self._VERSIONS

    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool:
        dest = self.tools_root / version
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        url = (
            f"https://github.com/yarnpkg/yarn/releases/download/"
            f"v{version}/yarn-v{version}.tar.gz"
        )
        tgz_path = dest / "yarn.tar.gz"
        try:
            self._download(url, tgz_path, progress_callback)
            self._extract_tgz(tgz_path, dest)
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Install failed: {e}")
        finally:
            tgz_path.unlink(missing_ok=True)

        (dest / ".installed").write_text(version)
        if not self.current():
            self.use(version)
        return True

    def _exe_path(self, version: str) -> Optional[Path]:
        d = self.tools_root / version
        js = d / "bin" / "yarn.js"
        return js if js.exists() else None

    def use(self, version: str) -> bool:
        (self.tools_root / ".active").write_text(version)
        return self._write_node_shim(version, "bin/yarn.js")

    def detect_system(self) -> Optional[str]:
        exe = shutil.which("yarn")
        if not exe:
            return None
        try:
            if str(self.shims_dir).lower() in exe.lower():
                return None
        except Exception:
            pass
        try:
            r = subprocess.run(
                [exe, "--version"], capture_output=True, text=True,
                timeout=5, creationflags=_FLAGS,
            )
            m = re.search(r"(\d+\.\d+[\.\d]*)", r.stdout + r.stderr)
            return m.group(1) if m else "installed"
        except Exception:
            return "installed"


# ── composer ─────────────────────────────────────────────────────────────────

class ComposerTool(BaseTool):
    name = "composer"
    display_name = "Composer"
    icon = "🎼"
    exe_name = "composer"
    description = "Dependency manager for PHP (requires PHP on PATH)"

    _VERSIONS = [
        ("2.7.7", "2024-06-10"),
        ("2.7.6", "2024-05-04"),
        ("2.6.6", "2023-12-08"),
        ("2.5.8", "2023-06-09"),
    ]

    def _remote_versions(self):
        return self._VERSIONS

    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool:
        dest = self.tools_root / version
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        url = f"https://getcomposer.org/download/{version}/composer.phar"
        try:
            self._download(url, dest / "composer.phar", progress_callback,
                           extra_headers={"Referer": "https://getcomposer.org/download/"})
        except Exception as e:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Download failed: {e}")

        (dest / ".installed").write_text(version)
        if not self.current():
            self.use(version)
        return True

    def _exe_path(self, version: str) -> Optional[Path]:
        p = self.tools_root / version / "composer.phar"
        return p if p.exists() else None

    def use(self, version: str) -> bool:
        (self.tools_root / ".active").write_text(version)
        return self._write_php_shim(version, "composer.phar")

    def detect_system(self) -> Optional[str]:
        for cmd in ("composer", "composer.phar"):
            exe = shutil.which(cmd)
            if not exe:
                continue
            try:
                if str(self.shims_dir).lower() in exe.lower():
                    continue
            except Exception:
                pass
            try:
                r = subprocess.run(
                    [exe, "--version"], capture_output=True, text=True,
                    timeout=8, creationflags=_FLAGS,
                )
                m = re.search(r"Composer version (\d+\.\d+[\.\d]*)", r.stdout + r.stderr)
                return m.group(1) if m else "installed"
            except Exception:
                return "installed"
        return None
