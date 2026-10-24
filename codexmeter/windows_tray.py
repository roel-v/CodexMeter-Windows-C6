"""Windows tray and control panel, with the BLE asyncio loop on its own thread."""
from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable


def connection_display(status: dict) -> tuple[str, str]:
    devices = status.get("devices", [])
    total = status.get("configured_count", len(devices))
    connected = sum(bool(device.get("connected")) for device in devices)
    if not total:
        return "No display configured", "gray"
    if connected == total:
        label = devices[0].get("label", "Display") if total == 1 else f"{connected} displays"
        return f"Connected: {label}", "green"
    if connected:
        return f"Connected: {connected} of {total} displays", "amber"
    return "Display disconnected — reconnecting", "amber"


def make_icon(state: str):
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (64, 64))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((5, 5, 57, 53), radius=9, fill="#172431", outline="#e9f2ff", width=4)
    draw.line((22, 59, 40, 59), fill="#e9f2ff", width=4)
    for x, height in ((16, 12), (27, 22), (38, 32)):
        draw.rectangle((x, 44 - height, x + 6, 44), fill="#e9f2ff")
    color = {"green": "#32d583", "amber": "#ffbf47", "gray": "#98a2b3"}[state]
    draw.ellipse((40, 39, 63, 62), fill=color, outline="#172431", width=3)
    return image


class WindowsTray:
    def __init__(self, *, show_panel: bool = False):
        self.show_panel = show_panel
        self.commands: queue.Queue = queue.Queue()
        self.shutdown: Callable[[], None] | None = None
        self.quit_requested = False
        self.done = threading.Event()
        self.ready = threading.Event()
        self.on_ready = None
        self.error: BaseException | None = None
        self.snapshot = {"visible": False, "text": "Starting bridge", "state": "gray", "panel_open": False}
        self.root = None
        self.icon = None
        self.app = None
        self.last_poll_at = None

    def bind_shutdown(self, callback: Callable[[], None]):
        self.shutdown = callback
        if self.quit_requested:
            callback()

    def publish_status(self, status: dict):
        self.commands.put(("status", connection_display(status)))

    def open_control_panel(self):
        self.commands.put(("open", None))

    def quit(self):
        logging.getLogger("codexmeter.lifecycle").info("SHUTDOWN_REQUEST source=tray_quit")
        self.commands.put(("quit", None))

    def _request_quit(self):
        self.quit_requested = True
        self.icon.title = "CodexMeter — stopping"
        if self.shutdown is not None:
            self.shutdown()

    def _hide_panel(self):
        self.root.withdraw()
        self.snapshot = {**self.snapshot, "panel_open": False}

    def _show_panel(self):
        if self.quit_requested:
            return
        if self.app is None:
            from .windows_app import MeterApp
            self.app = MeterApp(self.root, tray_managed=True)
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.snapshot = {**self.snapshot, "panel_open": True}

    def _poll(self):
        self.last_poll_at = time.time()
        if self.done.is_set():
            self.root.destroy()
            return
        if not self.ready.is_set():
            self.root.after(100, self._poll)
            return
        if self.on_ready is not None:
            callback, self.on_ready = self.on_ready, None
            self.root.after(100, callback)
        while True:
            try:
                command, value = self.commands.get_nowait()
            except queue.Empty:
                break
            if command == "open":
                self._show_panel()
            elif command == "quit":
                self._request_quit()
            elif command == "status" and not self.quit_requested:
                text, state = value
                if (text, state) != (self.snapshot["text"], self.snapshot["state"]):
                    self.snapshot = {**self.snapshot, "text": text, "state": state}
                    self.icon.icon = self.images[state]
                    self.icon.title = ("CodexMeter — " + text)[:127]
                    self.icon.update_menu()
        self.snapshot = {**self.snapshot, "visible": self.icon.visible}
        self.root.after(100, self._poll)

    def run(self, bridge: Callable[[], None], *, on_ready=None):
        import tkinter as tk
        from tkinter import ttk
        # Select the native backend explicitly so a user environment variable
        # cannot select an unsupported Linux backend in the Windows bundle.
        from pystray._win32 import Icon
        from pystray import Menu, MenuItem

        self.root = tk.Tk()
        self.root.report_callback_exception = lambda typ, exc, tb: logging.getLogger(
            "codexmeter.lifecycle").error("TK_CALLBACK_EXCEPTION", exc_info=(typ, exc, tb))
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self._hide_panel)
        ttk.Style().theme_use("vista")
        self.images = {state: make_icon(state) for state in ("green", "amber", "gray")}
        self.icon = Icon("CodexMeter", self.images["gray"], "CodexMeter — starting bridge", Menu(
            MenuItem("Open control panel", lambda: self.open_control_panel(), default=True),
            MenuItem(lambda item: self.snapshot["text"], None, enabled=False),
            Menu.SEPARATOR,
            MenuItem("Quit CodexMeter", lambda: self.quit()),
        ))

        def worker():
            try:
                bridge()
            except BaseException as exc:
                self.error = exc
                logging.exception("CodexMeter bridge stopped unexpectedly")
            finally:
                self.done.set()

        thread = threading.Thread(target=worker, name="CodexMeter bridge")
        def setup(icon):
            try:
                icon.visible = True
                self.ready.set()
            except BaseException as exc:
                self.error = exc
                self.quit_requested = True
                logging.getLogger("codexmeter.lifecycle").exception("TRAY_SETUP_EXCEPTION")
                if self.shutdown is not None:
                    self.shutdown()

        self.on_ready = on_ready
        self.icon.run_detached(setup)
        thread.start()
        if self.show_panel:
            self.open_control_panel()
        self.root.after(100, self._poll)
        try:
            self.root.mainloop()
        finally:
            logging.getLogger("codexmeter.lifecycle").info(
                "UI_LOOP_ENDED bridge_done=%s quit_requested=%s", self.done.is_set(), self.quit_requested)
            if not self.done.is_set():
                self._request_quit()
            thread.join(timeout=30)
            self.icon.visible = False
            self.icon.stop()
            self.snapshot = {**self.snapshot, "visible": False, "panel_open": False}
        if self.error is not None:
            raise self.error


def open_existing_panel() -> bool:
    import asyncio
    from .events import send_event
    try:
        return bool(asyncio.run(send_event({"type": "open_control_panel"})).get("ok"))
    except (OSError, ValueError, TimeoutError):
        return False
