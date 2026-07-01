import shutil
import zipfile
import tarfile
from pathlib import Path
from typing import Callable, Optional

import requests


def download_file(
    url: str,
    dest: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total:
                    progress_callback(downloaded, total)
    return dest


def extract_archive(archive: Path, dest: Path, strip_root: bool = True):
    dest.mkdir(parents=True, exist_ok=True)
    suffix = "".join(archive.suffixes)

    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            members = zf.namelist()
            root = _find_root(members) if strip_root else None
            for member in members:
                target = _strip_prefix(member, root) if root else member
                if not target:
                    continue
                target_path = dest / target
                if member.endswith("/"):
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(target_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)

    elif ".tar" in suffix or suffix in (".tgz", ".gz", ".xz"):
        mode = "r:gz" if suffix.endswith(".gz") else "r:xz" if suffix.endswith(".xz") else "r:*"
        with tarfile.open(archive, mode) as tf:
            names = [m.name for m in tf.getmembers()]
            root = _find_root(names) if strip_root else None
            for member in tf.getmembers():
                target = _strip_prefix(member.name, root) if root else member.name
                if not target:
                    continue
                member.name = target
                tf.extract(member, dest, filter="data")


def _find_root(members: list[str]) -> Optional[str]:
    roots = {m.split("/")[0] for m in members if "/" in m}
    return roots.pop() if len(roots) == 1 else None


def _strip_prefix(member: str, root: str) -> str:
    prefix = root + "/"
    return member[len(prefix):] if member.startswith(prefix) else member
