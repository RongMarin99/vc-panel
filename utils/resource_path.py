import sys
import os
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Return path that works in dev, PyInstaller, and cx_Freeze."""
    if getattr(sys, "frozen", False):
        # cx_Freeze: files sit next to the exe
        base = Path(os.path.dirname(sys.executable))
    else:
        base = Path(__file__).parent.parent
    return base.joinpath(*parts)
