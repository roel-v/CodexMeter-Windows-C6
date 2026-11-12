"""Launch another app role in both source and Nuitka onefile distributions."""
from pathlib import Path
import sys


def app_command(role: str, *args: str) -> list[str]:
    modules = {"cli": "codexmeter.cli", "daemon": "codexmeter.daemon"}
    if role not in modules:
        raise ValueError(f"Unknown app role: {role}")
    if "__compiled__" in globals():
        # In Nuitka onefile, argv[0] is the outer executable; sys.executable
        # must not be used as a general-purpose Python interpreter.
        return [str(Path(sys.argv[0]).resolve()), f"--{role}", *args]
    return [sys.executable, "-m", modules[role], *args]


def launch_background(command: list[str]):
    """Start an independent process, never tied to a terminal or host job lifetime."""
    import os
    import subprocess
    from .diagnostics import windows_process_context

    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        if windows_process_context().get("in_job"):
            flags |= subprocess.CREATE_BREAKAWAY_FROM_JOB
    environment = dict(os.environ)
    # A fresh outer onefile bootstrap must own its own child and extraction.
    environment.pop("NUITKA_ONEFILE_PARENT", None)
    environment["CODEXMETER_BACKGROUND_ISOLATED"] = "1"
    return subprocess.Popen(command, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=flags, env=environment)


def detach_background_daemon(args: list[str]) -> bool:
    """Detach before acquiring the daemon lock. Foreground mode remains attached."""
    import os
    if os.environ.pop("CODEXMETER_BACKGROUND_ISOLATED", None) == "1":
        # Runtime bootstraps can allocate a fresh console for their inner process.
        if sys.platform == "win32":
            import ctypes
            ctypes.WinDLL("kernel32", use_last_error=True).FreeConsole()
        return False
    if sys.platform != "win32" or "--foreground" in args:
        return False
    from .diagnostics import windows_process_context
    context = windows_process_context()
    if not context.get("in_job") and not context.get("console_process_count"):
        return False
    # Do not silently fall back to an attached process if breakaway is denied.
    launch_background(app_command("daemon", *args))
    return True
