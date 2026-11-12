"""Bounded native Windows tray acceptance check; never touches the live bridge."""
import threading

from .windows_tray import WindowsTray


def check_tray():
    from pystray._util import win32

    tray = WindowsTray()
    stopped = threading.Event()
    result = {}
    failures = []
    original_panel = []

    def bridge():
        tray.bind_shutdown(stopped.set)
        if not stopped.wait(20):
            raise TimeoutError("Tray check timed out")

    def step(action, next_action=None):
        try:
            action()
        except BaseException as exc:
            failures.append(exc)
            tray.quit()
            return
        if next_action:
            tray.root.after(400, next_action)

    def ready():
        def check():
            assert tray.icon.visible and tray.icon._hwnd
            result["native_icon"] = True
            tray.publish_status({"configured_count": 1, "devices": [{"connected": True, "label": "Test display"}]})
        step(check, connected)

    def connected():
        def check():
            assert tray.snapshot["state"] == "green"
            assert "Connected: Test display" in tray.icon.title
            assert list(tray.icon.menu)[1].text == "Connected: Test display"
            result["connected_tooltip_and_menu"] = True
            # Exercise the actual Win32 left-click handler and default menu action.
            win32.PostMessage(tray.icon._hwnd, win32.WM_NOTIFY, 0, win32.WM_LBUTTONUP)
        step(check, opened)

    def opened():
        def check():
            assert tray.snapshot["panel_open"] and tray.app is not None
            original_panel.append(tray.app)
            result["native_click_opens_panel"] = True
            tray.root.tk.call(tray.root.protocol("WM_DELETE_WINDOW"))
            assert not tray.snapshot["panel_open"] and not stopped.is_set()
            result["close_hides_panel"] = True
            tray.icon._menu_handle[1][0](tray.icon)
        step(check, reopened)

    def reopened():
        def check():
            assert tray.snapshot["panel_open"] and tray.app is original_panel[0]
            result["menu_reuses_panel"] = True
            tray.publish_status({"configured_count": 1, "devices": [{"connected": False}]})
        step(check, notification_click)

    def notification_click():
        def check():
            from .windows_notification import BALLOON_CLICK
            tray._hide_panel()
            win32.PostMessage(tray.icon._hwnd, win32.WM_NOTIFY, 0, BALLOON_CLICK)
        step(check, notification_opened)

    def notification_opened():
        def check():
            assert tray.notification_dialog is not None and tray.notification_dialog.winfo_exists()
            assert not tray.snapshot["panel_open"]
            result["native_notification_click_opens_dialog"] = True
            tray.notification_dialog.destroy()
            tray.open_updates()
        step(check, updates_opened)

    def updates_opened():
        def check():
            assert tray.update_dialog is not None and tray.update_dialog.winfo_exists()
            result["updates_dialog"] = True
            tray.update_dialog.destroy()
            tray.open_pricing_notice()
        step(check, pricing_opened)

    def pricing_opened():
        def check():
            assert tray.pricing_dialog is not None and tray.pricing_dialog.winfo_exists()
            tray.pricing_dialog.destroy()
        step(check, disconnected)

    def disconnected():
        def check():
            assert tray.snapshot["state"] == "amber"
            assert "disconnected" in tray.icon.title
            result["disconnected_tooltip_and_icon"] = True
            # Invoke the callback installed in the real native popup menu.
            tray.icon._menu_handle[1][-1](tray.icon)
        step(check)

    tray.run(bridge, on_ready=ready)
    if failures:
        raise failures[0]
    assert stopped.is_set() and tray.quit_requested and not tray.icon.visible
    result["quit_stops_bridge_and_removes_icon"] = True
    return result
