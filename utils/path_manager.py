import sys
from pathlib import Path


def add_to_path(directory: Path):
    if sys.platform == "win32":
        _win_add(str(directory))
    else:
        _unix_add(directory)


def _is_admin() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _win_add_to_key(hive, subkey: str, directory: str) -> bool:
    import winreg
    try:
        key = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE)
        try:
            current, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current = ""
        entries = [e for e in current.split(";") if e]
        if directory not in entries:
            entries.insert(0, directory)
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(entries))
            _win_broadcast()
        winreg.CloseKey(key)
        return True
    except PermissionError:
        return False
    except Exception:
        return False


def _win_add(directory: str):
    import winreg
    # Try system PATH first (beats other version managers like NVM).
    # Only works if VC is running as admin.
    if _is_admin():
        ok = _win_add_to_key(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            directory,
        )
        if ok:
            return

    # Fall back to user PATH
    _win_add_to_key(
        winreg.HKEY_CURRENT_USER,
        "Environment",
        directory,
    )


def _win_broadcast():
    import ctypes
    ctypes.windll.user32.SendMessageTimeoutW(
        0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None
    )


def _unix_add(directory: Path):
    home = Path.home()
    for profile in [home / ".zshrc", home / ".bashrc", home / ".bash_profile", home / ".profile"]:
        if profile.exists():
            content = profile.read_text()
            line = f'\nexport PATH="{directory}:$PATH"'
            if str(directory) not in content:
                profile.write_text(content + line + "\n")
            return
    (home / ".profile").write_text(f'export PATH="{directory}:$PATH"\n')
