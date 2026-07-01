import sys
import stat
from pathlib import Path


def create_shim(shims_dir: Path, tool_name: str, binary_path: Path):
    if sys.platform == "win32":
        shim = shims_dir / f"{tool_name}.bat"
        shim.write_text(f'@echo off\n"{binary_path}" %*\n')
    else:
        shim = shims_dir / tool_name
        shim.write_text(f'#!/bin/sh\nexec "{binary_path}" "$@"\n')
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def remove_shim(shims_dir: Path, tool_name: str):
    for name in [tool_name, f"{tool_name}.bat"]:
        p = shims_dir / name
        if p.exists():
            p.unlink()
