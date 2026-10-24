import asyncio

import pytest

from codexmeter.events import EventServer
from codexmeter.windows_tray import WindowsTray, connection_display


@pytest.mark.parametrize("devices,total,text,color", [
    ([], 0, "No display configured", "gray"),
    ([{"connected": False}], 1, "Display disconnected — reconnecting", "amber"),
    ([{"connected": True, "label": "Desk"}], 1, "Connected: Desk", "green"),
    ([{"connected": True}, {"connected": False}], 2, "Connected: 1 of 2 displays", "amber"),
    ([{"connected": True}, {"connected": True}], 2, "Connected: 2 displays", "green"),
])
def test_connection_state(devices, total, text, color):
    assert connection_display({"devices": devices, "configured_count": total}) == (text, color)


def test_early_quit_is_not_lost_before_bridge_binds():
    tray = WindowsTray()
    tray.quit_requested = True
    stopped = []
    tray.bind_shutdown(lambda: stopped.append(True))
    assert stopped == [True]


def test_control_panel_event_does_not_send_device_payload():
    async def scenario():
        opened = []
        async def sink(payload):
            pytest.fail("Opening the control panel should not send a BLE payload")
        server = EventServer(sink, open_control_panel=lambda: opened.append(True))
        response = await server._dispatch({"type": "open_control_panel"})
        assert response == {"ok": True, "queued": "open_control_panel"}
        assert opened == [True]
    asyncio.run(scenario())
