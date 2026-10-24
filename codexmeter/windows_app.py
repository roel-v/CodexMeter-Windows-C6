"""English Windows control panel. BLE and the daemon run in separate processes."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

from .app_server import resolve_codex_binary
from .launch import app_command
from .settings import LOG_FILE


class MeterApp:
    def __init__(self, root: tk.Tk, *, tray_managed: bool = False) -> None:
        self.root = root
        root.title("CodexMeter")
        root.geometry("780x590")
        root.minsize(680, 500)
        self.results: queue.Queue = queue.Queue()
        self.busy = False
        self.codex = tk.StringVar(value="codex")
        self.short_id = tk.StringVar()
        self.alias = tk.StringVar(value="Desk")
        self.status = tk.StringVar(value="Ready — start the bridge, then scan for your display.")
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="CodexMeter", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Codex usage and task alerts on your Waveshare display").pack(anchor="w", pady=(0, 16))
        path_row = ttk.Frame(frame)
        path_row.pack(fill="x", pady=4)
        ttk.Label(path_row, text="Codex executable").pack(side="left", padx=(0, 10))
        ttk.Entry(path_row, textvariable=self.codex).pack(side="left", fill="x", expand=True)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=10)
        for label, callback in [
            ("Start bridge", self.start), ("Stop bridge", self.stop),
            ("Status", lambda: self.command("status")),
            ("Read usage", lambda: self.command("once", "--codex-bin", self.codex.get())),
            ("Scan displays", lambda: self.command("devices", "scan")),
        ]:
            ttk.Button(actions, text=label, command=callback).pack(side="left", padx=(0, 5))
        register = ttk.Frame(frame)
        register.pack(fill="x", pady=4)
        ttk.Label(register, text="Display ID").pack(side="left")
        ttk.Entry(register, textvariable=self.short_id, width=10).pack(side="left", padx=8)
        ttk.Label(register, text="Name").pack(side="left")
        ttk.Entry(register, textvariable=self.alias, width=16).pack(side="left", padx=8)
        ttk.Button(register, text="Register display", command=self.adopt).pack(side="left")
        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=10)
        for label, args in [("Test alert", ("demo-alert", "CodexMeter is connected.")),
                            ("Screen on", ("screen-on",)), ("Screen off", ("screen-off",))]:
            ttk.Button(controls, text=label, command=lambda a=args: self.command(*a)).pack(side="left", padx=(0, 5))
        ttk.Button(controls, text="Open log", command=self.open_log).pack(side="left")
        ttk.Label(frame, textvariable=self.status, wraplength=720).pack(anchor="w", pady=6)
        self.output = tk.Text(frame, wrap="word", font=("Consolas", 10), height=15, state="disabled")
        self.output.pack(fill="both", expand=True)
        footer = ("Closing this window hides it. Use the tray icon to reopen it or quit CodexMeter."
                  if tray_managed else "Closing this window leaves the bridge running. Stop it with Stop bridge.")
        ttk.Label(frame, text=footer).pack(anchor="w", pady=(10, 0))
        self.poll_after = root.after(100, self.poll)
        root.bind("<Destroy>", self._on_destroy, add="+")

    def _on_destroy(self, event):
        if event.widget is self.root:
            self.root.after_cancel(self.poll_after)

    def launch_job(self, job) -> None:
        if self.busy:
            self.status.set("Please wait for the current operation to finish.")
            return
        self.busy = True
        self.status.set("Working…")
        def worker():
            try:
                self.results.put((True, job()))
            except Exception as exc:
                self.results.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def command(self, *args: str) -> None:
        def run():
            proc = subprocess.run(
                app_command("cli", *args),
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120, creationflags=subprocess.CREATE_NO_WINDOW,
                env={**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"},
            )
            if proc.returncode:
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
            return proc.stdout.strip()
        self.launch_job(run)

    def start(self) -> None:
        requested_executable = self.codex.get()
        executable = resolve_codex_binary(requested_executable)
        if not executable:
            self.status.set("Codex was not found. Enter the path to codex.exe.")
            return
        def run():
            from .events import send_event
            try:
                status = asyncio.run(send_event({"type": "ping"}))
                if status.get("ok"):
                    return "Bridge is already running."
            except (OSError, ValueError, TimeoutError):
                pass
            subprocess.Popen(
                app_command("daemon", "--codex-bin", requested_executable),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            import time
            for _ in range(300):
                time.sleep(0.1)
                try:
                    if asyncio.run(send_event({"type": "ping"})).get("ok"):
                        return "Bridge started. Read usage to check Codex, or scan for a flashed display."
                except (OSError, ValueError, TimeoutError):
                    pass
            raise RuntimeError(f"Bridge did not become ready. Check {LOG_FILE}.")
        self.launch_job(run)

    def stop(self) -> None:
        from .events import send_event
        self.launch_job(lambda: json.dumps(asyncio.run(send_event({"type": "shutdown"})), indent=2))

    def adopt(self) -> None:
        self.command("devices", "adopt", self.short_id.get().strip(), "--alias", self.alias.get().strip())

    def open_log(self) -> None:
        if LOG_FILE.exists():
            os.startfile(LOG_FILE)
        else:
            self.status.set("No log yet. Start the bridge first.")

    def poll(self) -> None:
        try:
            success, text = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.status.set("Done. After registering a display, stop and start the bridge." if success else "Operation failed — details below.")
            self.output.configure(state="normal")
            self.output.delete("1.0", "end")
            self.output.insert("end", text)
            self.output.configure(state="disabled")
        self.poll_after = self.root.after(100, self.poll)


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("This control panel requires Windows.")
    root = tk.Tk()
    ttk.Style().theme_use("vista")
    MeterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
