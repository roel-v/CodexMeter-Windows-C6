import asyncio
import sys
from types import SimpleNamespace

import pytest

from codexmeter.bluetooth_recovery import BluetoothRecovery, cycle_windows_radio
from codexmeter.multi_ble import scan_codexmeter_devices


def make_monitor(tmp_path):
    state = {"connected": False, "configured_count": 1}
    now = [10000.0]
    calls = []
    async def cycle():
        calls.append(now[0])
        return "radio restarted"
    monitor = BluetoothRecovery(lambda: state, cycle=cycle,
        path=tmp_path / "recovery.json", clock=lambda: now[0], epoch=lambda: now[0])
    return monitor, state, now, calls


def test_threshold_cooldown_persistence_and_outage_cap(tmp_path):
    async def run():
        m, state, now, calls = make_monitor(tmp_path)
        for t in (10000, 10060, 10119):
            now[0] = t
            await m.observe(0)
        assert not calls
        now[0] = 10120
        await m.observe(0)
        assert len(calls) == 1
        # Restarting the app cannot bypass the persisted cooldown.
        restarted, _, _, _ = make_monitor(tmp_path)
        assert restarted.last_attempt == 10120 and restarted.attempts == 1
        for t in (10130, 10200, 10300):
            now[0] = t
            await m.observe(0)
        assert len(calls) == 1
        for base in (12000, 14000, 16000):
            for t in (base, base+60, base+120):
                now[0] = t
                await m.observe(0)
        assert len(calls) == 3
        state["connected"] = True
        await m.observe(0)
        assert m.attempts == 0 and m.empty_scans == 0
    asyncio.run(run())


@pytest.mark.parametrize("reset", [None, 5, "connected", "unconfigured"])
def test_no_reset_for_unknown_scan_nearby_devices_or_healthy_connection(tmp_path, reset):
    async def run():
        m, state, now, calls = make_monitor(tmp_path)
        await m.observe(0)
        now[0] += 60
        await m.observe(0)
        if reset == "connected": state["connected"] = True
        if reset == "unconfigured": state["configured_count"] = 0
        await m.observe(reset if reset in (None, 5) else 0)
        assert m.empty_scans == 0
        state.update(connected=False, configured_count=1)
        now[0] += 70
        await m.observe(0)
        assert not calls
    asyncio.run(run())


def test_failed_recovery_is_throttled(tmp_path):
    async def run():
        m, _, now, _ = make_monitor(tmp_path)
        async def fail(): raise OSError("denied")
        m.cycle = fail
        for t in (10000, 10060, 10120):
            now[0] = t
            await m.observe(0)
        assert m.attempts == 1 and "failed" in m.result
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["success", "off", "denied", "cancel", "timeout"])
def test_radio_restoration_and_manual_off(monkeypatch, mode):
    async def run():
        calls = []
        off_called = asyncio.Event()
        class FakeRadio:
            state = 0 if mode == "off" else 1
            kind = 3
            async def set_state_async(self, state):
                calls.append(state)
                if state == 0:
                    off_called.set()
                    if mode == "cancel": await asyncio.Future()
                    if mode == "timeout": raise TimeoutError()
                    if mode == "denied": return 2
                return 1
        async def get_radios(): return [FakeRadio()]
        monkeypatch.setitem(sys.modules, "winrt.windows.devices.radios", SimpleNamespace(
            Radio=SimpleNamespace(get_radios_async=get_radios), RadioKind=SimpleNamespace(BLUETOOTH=3),
            RadioState=SimpleNamespace(ON=1, OFF=0), RadioAccessStatus=SimpleNamespace(ALLOWED=1)))
        task = asyncio.create_task(cycle_windows_radio())
        if mode == "cancel":
            await off_called.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
        elif mode == "timeout":
            with pytest.raises(TimeoutError): await task
        else:
            result = await task
            assert (result == "radio restarted") == (mode == "success")
        assert calls == ([] if mode == "off" else [0, 1])
    asyncio.run(run())


def test_raw_scan_count_includes_unrelated_devices():
    async def run():
        counts = []
        async def discover(**kwargs):
            return {"other": (SimpleNamespace(name="Other"), SimpleNamespace(local_name="Other", service_uuids=[]))}
        async def connected(): return []
        found = await scan_codexmeter_devices(discover=discover, connected_lookup=connected,
                                             raw_count_observer=counts.append)
        assert found == [] and counts == [1]
    asyncio.run(run())


def test_discovery_loop_feeds_monitor_and_clears_failed_scan_evidence(tmp_path):
    from codexmeter.multi_ble import DiscoveryService
    async def run():
        monitor, _, now, calls = make_monitor(tmp_path)
        stop = asyncio.Event()
        scans = 0
        async def scan(timeout):
            nonlocal scans
            scans += 1
            now[0] += 60
            if scans == 3: raise OSError("scan failed")
            discovery.raw_result_count = 0
            return []
        discovery = DiscoveryService(scanner=scan, scan_interval_sec=0)
        async def after_scan(raw_count):
            await monitor.observe(raw_count)
            if scans == 5:
                assert not calls  # Error at scan 3 restarted the two-minute window.
            if scans == 6: stop.set()
        discovery.after_scan = after_scan
        await discovery.run(stop)
        assert len(calls) == 1
    asyncio.run(run())
