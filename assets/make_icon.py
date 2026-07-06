"""Run once: python assets/make_icon.py  — converts icon.png → icon.ico"""
from pathlib import Path
from PIL import Image

src = Path(__file__).parent / "icon.png"
dst = Path(__file__).parent / "icon.ico"

img = Image.open(src).convert("RGBA")
sizes = [16, 24, 32, 48, 64, 128, 256]
icons = [img.resize((s, s), Image.LANCZOS) for s in sizes]
icons[0].save(dst, format="ICO", sizes=[(s, s) for s in sizes], append_images=icons[1:])
print(f"Saved {dst}")
