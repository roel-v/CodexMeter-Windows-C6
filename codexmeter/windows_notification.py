"""Native tray notification click dispatch, without calling Tk from Win32."""
from pystray._win32 import Icon

# Shell notification callback: NIN_BALLOONUSERCLICK = WM_USER + 5.
BALLOON_CLICK = 0x405


class NotificationIcon(Icon):
    def __init__(self, *args, on_notification_click, **kwargs):
        self.on_notification_click = on_notification_click
        super().__init__(*args, **kwargs)

    def _on_notify(self, wparam, lparam):
        if lparam & 0xFFFF == BALLOON_CLICK:
            self.on_notification_click()
            return 0
        return super()._on_notify(wparam, lparam)
