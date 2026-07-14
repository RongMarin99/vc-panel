"""Shared Windows service control helpers (sc.exe / systemctl fallback)."""
import os
import subprocess
import sys
from pathlib import Path

_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0)  # Windows only (0x8)


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


def start_direct(args: list[str], pid_file: Path) -> bool:
    """Launch a background process without admin. Saves PID to pid_file."""
    try:
        flags = _FLAGS | _DETACHED
        proc = subprocess.Popen(
            args,
            creationflags=flags,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pid_file.write_text(str(proc.pid))
        return True
    except Exception:
        return False


def stop_direct(pid_file: Path) -> bool:
    """Kill a process started by start_direct()."""
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
        if sys.platform == "win32":
            r = run_cmd(["taskkill", "/PID", str(pid), "/F"], timeout=10)
            ok = bool(r and r.returncode == 0)
        else:
            os.kill(pid, 15)  # SIGTERM
            ok = True
        pid_file.unlink(missing_ok=True)
        return ok
    except Exception:
        pid_file.unlink(missing_ok=True)
        return False


def pid_running(pid_file: Path) -> bool:
    """Return True if the process saved in pid_file is still alive."""
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
        if sys.platform == "win32":
            r = run_cmd(["tasklist", "/FI", f"PID eq {pid}", "/NH"], timeout=5)
            return bool(r and str(pid) in r.stdout)
        else:
            os.kill(pid, 0)  # signal 0 = existence check
            return True
    except Exception:
        return False


def grant_service_control(svc: str) -> bool:
    """
    Grant the current user Start/Stop rights on a Windows service without
    requiring permanent elevation. Runs sc sdset once; requires admin the
    first time. Returns True if successful.
    """
    if sys.platform != "win32":
        return False
    import ctypes
    # Read current SDDL
    r = run_cmd(["sc", "sdshow", svc])
    if not r or r.returncode != 0:
        return False
    sddl = r.stdout.strip()
    # Append RPWP (start+stop) for Authenticated Users (AU)
    if "AU" in sddl:
        return True  # already granted
    # Insert ACE before the first S: (SACL) or append to D: DACL
    new_ace = "(A;;RPWP;;;AU)"
    if "D:" in sddl:
        sddl = sddl.replace("D:", f"D:{new_ace}", 1)
    else:
        sddl += f"D:{new_ace}"
    r2 = run_cmd(["sc", "sdset", svc, sddl], timeout=10)
    return bool(r2 and r2.returncode == 0)


def grant_port_80(user: str = "Everyone") -> bool:
    """
    Grant non-admin access to bind port 80 via netsh urlacl.
    Requires admin the first time. Returns True on success.
    """
    if sys.platform != "win32":
        return False
    r = run_cmd(
        ["netsh", "http", "add", "urlacl",
         "url=http://+:80/", f"user={user}"],
        timeout=15,
    )
    return bool(r and r.returncode == 0)


def tcp_test(host: str = "127.0.0.1", port: int = 3306, timeout: float = 2.0) -> bool:
    """Return True if a TCP connection to host:port succeeds."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


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
