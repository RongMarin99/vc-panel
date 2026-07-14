import urllib.request
from pathlib import Path
from packaging.version import Version
from typing import Callable, Optional

CURRENT_VERSION = "0.2.0"
GITHUB_REPO     = "RongMarin99/vc-panel"
RELEASES_URL    = f"https://github.com/{GITHUB_REPO}/releases"
_API_URL        = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def check_update() -> tuple[str, str] | tuple[None, None]:
    """Return (latest_version, installer_url) if newer, else (None, None)."""
    try:
        req = urllib.request.Request(
            _API_URL,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"VC-VersionController/{CURRENT_VERSION}",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            import json
            data = json.loads(resp.read())

        tag = data.get("tag_name", "").lstrip("v")
        if not tag:
            return None, None

        if Version(tag) > Version(CURRENT_VERSION):
            assets = data.get("assets", [])
            url = next(
                (a["browser_download_url"] for a in assets
                 if a["name"].lower().endswith(".exe")),
                data.get("html_url", RELEASES_URL),
            )
            return tag, url
    except Exception:
        pass
    return None, None


def download_installer(url: str, dest: Path,
                       progress_cb: Optional[Callable] = None) -> bool:
    """Download installer EXE to dest with optional progress callback(done, total)."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": f"VC-VersionController/{CURRENT_VERSION}"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
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
    return True


def apply_update(installer_path: Path) -> None:
    """Launch installer silently and exit VC. Inno Setup /CLOSEAPPLICATIONS
    handles closing the running VC.exe before overwriting files."""
    import subprocess, sys
    subprocess.Popen(
        [str(installer_path),
         "/VERYSILENT",
         "/SUPPRESSMSGBOXES",
         "/NORESTART",
         "/CLOSEAPPLICATIONS",
         "/RESTARTAPPLICATIONS"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
    )
    from PyQt6.QtWidgets import QApplication
    QApplication.quit()
