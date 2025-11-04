
# ------------------------------
# utils/launcher.py
# ------------------------------
from __future__ import annotations
import os, sys, subprocess
from pathlib import Path

def launch_path(path: str, args: str = "", workdir: str = "") -> bool:
    path = path.strip(); args = args.strip(); cwd = workdir.strip() or None
    if "://" in path:
        try:
            if sys.platform.startswith("win"): os.startfile(path)  # type: ignore
            elif sys.platform == "darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
            return True
        except Exception: 
            return False
    try:
        if sys.platform.startswith("win"):
            cmd = f'"{path}"' + (f" {args}" if args else "")
            subprocess.Popen(cmd, cwd=cwd, shell=True)
            return True
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path], cwd=cwd)
            return True
        else:
            if Path(path).is_dir():
                subprocess.Popen(["xdg-open", path], cwd=cwd)
            else:
                if os.access(path, os.X_OK):
                    subprocess.Popen([path] + (args.split() if args else []), cwd=cwd)
                else:
                    subprocess.Popen(["xdg-open", path], cwd=cwd)
            return True
    except Exception:
        return False
