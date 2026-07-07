"""Shared Windows service control helpers (sc.exe / systemctl fallback)."""
import subprocess
import sys

_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def run_cmd(args: list[str], timeout: int = 8):
    try:
        return subprocess.run(
            args, capture_output=True, text=True,
            timeout=timeout, creationflags=_FLAGS,
        )
    except Exception:
        return None


def sc_query(svc: str) -> str:
    """Return 'running' | 'stopped' | 'not_found'."""
    if sys.platform == "win32":
        r = run_cmd(["sc", "query", svc])
        if not r or r.returncode != 0:
            return "not_found"
        if "RUNNING" in r.stdout:
            return "running"
        if "STOPPED" in r.stdout or "STOP_PENDING" in r.stdout:
            return "stopped"
        return "not_found"
    else:
        r = run_cmd(["systemctl", "is-active", svc])
        if not r:
            return "not_found"
        state = r.stdout.strip()
        if state == "active":
            return "running"
        if state in ("inactive", "failed"):
            return "stopped"
        return "not_found"


def sc_start(svc: str) -> bool:
    if sys.platform == "win32":
        r = run_cmd(["sc", "start", svc], timeout=20)
    else:
        r = run_cmd(["systemctl", "start", svc], timeout=20)
    return bool(r and r.returncode == 0)


def sc_stop(svc: str) -> bool:
    if sys.platform == "win32":
        r = run_cmd(["sc", "stop", svc], timeout=20)
    else:
        r = run_cmd(["systemctl", "stop", svc], timeout=20)
    return bool(r and r.returncode == 0)


def find_service(candidates: list[str]) -> tuple[str | None, str | None]:
    """Return (service_name, status) for first candidate found."""
    for svc in candidates:
        status = sc_query(svc)
        if status != "not_found":
            return svc, status
    return None, None


def reg_get(key_path: str, value: str) -> str | None:
    """Read a HKLM registry string value (Windows only)."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
            return winreg.QueryValueEx(k, value)[0]
    except Exception:
        return None


def reg_enum_subkeys(key_path: str) -> list[str]:
    if sys.platform != "win32":
        return []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
            count = winreg.QueryInfoKey(k)[0]
            return [winreg.EnumKey(k, i) for i in range(count)]
    except Exception:
        return []
