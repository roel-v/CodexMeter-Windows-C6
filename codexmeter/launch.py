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
