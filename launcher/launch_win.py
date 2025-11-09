"""Windows specific helpers to launch executables and shortcuts."""
from __future__ import annotations

import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

_LOGGER = logging.getLogger(__name__)

URI_PREFIXES = ("steam://", "com.epicgames.launcher://")


def _is_uri(path: str) -> bool:
    return any(path.lower().startswith(prefix) for prefix in URI_PREFIXES)


def _resolve_shortcut(path: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Resolve a Windows shortcut (.lnk) using PowerShell.

    Returns tuple of (target_path, arguments, working_directory).
    """

    if not sys.platform.startswith("win"):
        return None, None, None

    script = (
        "$sh = New-Object -ComObject WScript.Shell;"
        f"$lnk = $sh.CreateShortcut('{path.as_posix().replace("'", "''")}');"
        "Write-Output $lnk.TargetPath;"
        "Write-Output $lnk.Arguments;"
        "Write-Output $lnk.WorkingDirectory;"
    )

    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.error("Failed to invoke PowerShell for shortcut %s: %s", path, exc)
        return None, None, None

    if completed.returncode != 0:
        _LOGGER.error(
            "PowerShell failed to resolve shortcut %s: %s", path, completed.stderr.strip()
        )
        return None, None, None

    outputs = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not outputs:
        return None, None, None

    target = outputs[0]
    arguments = outputs[1] if len(outputs) > 1 else None
    working_dir = outputs[2] if len(outputs) > 2 else None
    return target or None, arguments or None, working_dir or None


def _merge_args(link_args: Optional[str], extra_args: Optional[str]) -> Optional[str]:
    values = [arg for arg in (link_args, extra_args) if arg]
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return " ".join(values)


def build_cmd(exec_path: str, args: Optional[str] = None) -> Tuple[str, Optional[str], str]:
    """Prepare execution target, its parameters and working directory."""

    exec_path = exec_path.strip()
    if _is_uri(exec_path):
        return exec_path, args, ""

    path = Path(exec_path)
    params = args
    cwd = ""

    if sys.platform.startswith("win") and path.suffix.lower() == ".lnk":
        target, link_args, working_dir = _resolve_shortcut(path)
        if target:
            params = _merge_args(link_args, args)
            exec_path = target
            cwd = working_dir or ""
            path = Path(exec_path)
        else:
            _LOGGER.warning("Falling back to shortcut path because resolution failed: %s", path)
    if not cwd:
        cwd = str(path.parent)
    return str(path), params, cwd


def _shell_execute(file: str, params: Optional[str], cwd: str, run_as_admin: bool) -> int:
    import ctypes
    from ctypes import wintypes

    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    SW_SHOWNORMAL = 1

    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", wintypes.ULONG),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", wintypes.LPVOID),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIcon", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    shell_execute_ex = ctypes.windll.shell32.ShellExecuteExW  # type: ignore[attr-defined]

    info = SHELLEXECUTEINFO()
    info.cbSize = ctypes.sizeof(SHELLEXECUTEINFO)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.hwnd = None
    info.lpVerb = "runas" if run_as_admin else None
    info.lpFile = file
    info.lpParameters = params
    info.lpDirectory = cwd or None
    info.nShow = SW_SHOWNORMAL
    info.hInstApp = None
    info.lpIDList = None
    info.lpClass = None
    info.hkeyClass = None
    info.dwHotKey = 0
    info.hIcon = None
    info.hProcess = None

    success = shell_execute_ex(ctypes.byref(info))
    if not success:
        error = ctypes.GetLastError()
        _LOGGER.error("ShellExecuteExW failed for %s (error %s)", file, error)
        return int(error or 1)
    return 0


def _spawn_subprocess(file: str, params: Optional[str], cwd: str) -> int:
    cmd = [file]
    if params:
        cmd.extend(shlex.split(params, posix=False))
    try:
        subprocess.Popen(cmd, cwd=cwd or None)
        return 0
    except FileNotFoundError as exc:
        _LOGGER.error("Executable not found: %s", exc)
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.error("Failed to launch %s: %s", file, exc)
    return 1


def launch(exec_path: str, args: Optional[str] = None, run_as_admin: bool = False) -> int:
    """Launch a target path or URI.

    Returns 0 on success, non-zero on failure.
    """

    file, params, cwd = build_cmd(exec_path, args)

    if _is_uri(file):
        if not sys.platform.startswith("win"):
            _LOGGER.error("URI launch is only supported on Windows: %s", file)
            return 1
        try:
            os.startfile(file)  # type: ignore[attr-defined]
            _LOGGER.info("Launched URI: %s", file)
            return 0
        except OSError as exc:
            _LOGGER.error("Failed to start URI %s: %s", file, exc)
            return 1

    if sys.platform.startswith("win"):
        return _shell_execute(file, params, cwd, run_as_admin)
    return _spawn_subprocess(file, params, cwd)
