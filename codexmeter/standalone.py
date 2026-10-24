"""Single executable entry point and packaged-runtime diagnostic."""
from __future__ import annotations

import json
from pathlib import Path
import sys


def self_test(output: Path) -> int:
    import subprocess
    import time
    import traceback
    result = {"ok": False, "compiled": "__compiled__" in globals()}
    root = None
    try:
        import bleak.backends.winrt.client
        import bleak.backends.winrt.scanner
        from winrt.windows.devices.radios import Radio, RadioState
        import serial
        import tkinter as tk
        from .ipc import _dpapi
        from .launch import app_command
        from .windows_app import MeterApp

        assert _dpapi(_dpapi(b"CodexMeter package check"), decrypt=True) == b"CodexMeter package check"
        root = tk.Tk()
        root.withdraw()
        app = MeterApp(root)
        root.update()
        command = app_command("cli", "devices", "list")
        child = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                               timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        if child.returncode:
            raise RuntimeError(child.stderr or child.stdout or f"Child exited {child.returncode}")
        json.loads(child.stdout)
        # Exercise the real GUI worker, subprocess launcher and result polling.
        app.command("devices", "list")
        deadline = time.monotonic() + 60
        while app.busy and time.monotonic() < deadline:
            root.update()
            time.sleep(0.02)
        assert not app.busy, "GUI command timed out"
        assert not app.status.get().startswith("Operation failed"), app.output.get("1.0", "end")
        json.loads(app.output.get("1.0", "end"))
        result.update(ok=True, tkinter=tk.TkVersion, bleak_winrt=True, dpapi=True,
                      gui_command=True, child_command=command, executable=sys.executable,
                      entrypoint=sys.argv[0])
        root.destroy()
        root = None
        from .tray_diagnostics import check_tray
        result["tray"] = check_tray()
    except Exception:
        result["ok"] = False
        result["error"] = traceback.format_exc()
    finally:
        if root is not None:
            root.destroy()
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--daemon":
        from .daemon import main as daemon_main
        return daemon_main(args[1:])
    if args and args[0] == "--cli":
        from .cli import main as cli_main
        return cli_main(args[1:])
    if args and args[0] == "--self-test":
        if len(args) != 2:
            raise SystemExit("Usage: CodexMeter.exe --self-test OUTPUT.json")
        return self_test(Path(args[1]))
    if args:
        raise SystemExit("Use --daemon, --cli COMMAND, or no arguments for the control panel.")
    from .windows_tray import open_existing_panel
    if open_existing_panel():
        return 0
    from .daemon import main as daemon_main
    return daemon_main(["--show-control-panel"])
