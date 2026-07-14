from cx_Freeze import setup, Executable
import sys
import os
import sysconfig
import PyQt6

# Qt6 DLLs live in PyQt6/Qt6/bin — copy them to build root so Windows finds them
_qt6_bin = os.path.join(os.path.dirname(PyQt6.__file__), "Qt6", "bin")
_qt6_dlls = [
    (os.path.join(_qt6_bin, f), f)
    for f in os.listdir(_qt6_bin)
    if f.lower().endswith(".dll")
] if os.path.isdir(_qt6_bin) else []

# python3.dll (stable ABI forwarder, ~72KB) — needed by PyQt6 .pyd files but not copied by cx_Freeze
# C:\Python313\python3.dll is a symlink to python313.dll (6MB) — filter it out by size
_base_python = sysconfig.get_config_var("installed_platbase") or ""
_python3_dll_candidates = [
    os.path.join(_base_python, "python3.dll"),
    os.path.join(os.path.dirname(sys.executable), "python3.dll"),
    r"C:\Users\back-end.03\AppData\Local\Programs\Python\Python313\python3.dll",
]
_python3_dll = next(
    (p for p in _python3_dll_candidates
     if os.path.isfile(p) and 1000 < os.path.getsize(p) < 1_000_000),
    None,
)
_extra_dlls = [(_python3_dll, "python3.dll")] if _python3_dll else []

# VCRUNTIME DLLs — bundle so app works on clean machines without VC++ Redist installed
_vcrt_sources = [
    ("MSVCP140.dll",      [r"C:\Windows\System32\MSVCP140.dll"]),
    ("VCRUNTIME140.dll",  [r"C:\Python313\VCRUNTIME140.dll",
                           r"C:\Windows\System32\VCRUNTIME140.dll"]),
    ("VCRUNTIME140_1.dll",[r"C:\Windows\System32\VCRUNTIME140_1.dll"]),
]
_vcrt_dlls = []
for _name, _candidates in _vcrt_sources:
    _src = next((p for p in _candidates if os.path.isfile(p) and os.path.getsize(p) > 0), None)
    if _src:
        _vcrt_dlls.append((_src, _name))

build_options = {
    "packages": [
        "PyQt6", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
        "requests", "sqlite3", "packaging", "winreg",
        "providers", "core", "storage", "ui", "utils",
    ],
    "include_files": [
        ("assets", "assets"),
    ] + _qt6_dlls + _extra_dlls + _vcrt_dlls,
    "excludes": ["tkinter", "unittest", "email", "xml"],
}

_icon = "assets/icon.ico" if os.path.isfile("assets/icon.ico") else None

exe = Executable(
    script="main.py",
    base="gui" if sys.platform == "win32" else None,
    target_name="VC.exe",
    icon=_icon,
)

setup(
    name="VC",
    version="0.2.1",
    description="VC — Version Controller",
    options={"build_exe": build_options},
    executables=[exe],
)
