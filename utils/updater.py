import requests
from packaging.version import Version

CURRENT_VERSION = "0.1.2"
GITHUB_REPO     = "RongMarin99/vc-panel"
RELEASES_URL    = f"https://github.com/{GITHUB_REPO}/releases"
_API_URL        = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def check_update() -> tuple[str, str] | tuple[None, None]:
    """
    Returns (latest_version, download_url) if a newer version exists,
    otherwise (None, None).
    """
    try:
        r = requests.get(
            _API_URL, timeout=8,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        r.raise_for_status()
        data = r.json()
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
