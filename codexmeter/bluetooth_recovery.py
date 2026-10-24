"""Conservative Windows radio recovery after sustained empty BLE scans."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from .persistence import atomic_write_json
from .settings import APP_DIR

log = logging.getLogger(__name__)


async def cycle_windows_radio() -> str:
    from winrt.windows.devices.radios import Radio, RadioKind, RadioState, RadioAccessStatus

    radios = [r for r in await asyncio.wait_for(Radio.get_radios_async(), 10)
              if r.kind == RadioKind.BLUETOOTH]
    if len(radios) != 1:
        return "skipped: expected one Bluetooth radio"
    radio = radios[0]
    if radio.state != RadioState.ON:
        return "skipped: Bluetooth is switched off"
    # Once off is requested, always attempt restoration, even on timeout/exit.
    async def restore():
        result = await asyncio.wait_for(radio.set_state_async(RadioState.ON), 10)
        if result != RadioAccessStatus.ALLOWED:
            raise RuntimeError("Windows denied restoring Bluetooth radio")

    try:
        result = await asyncio.wait_for(radio.set_state_async(RadioState.OFF), 10)
        if result != RadioAccessStatus.ALLOWED:
            return "skipped: Windows denied Bluetooth control"
        await asyncio.sleep(2)
    finally:
        task = asyncio.create_task(restore())
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise
    return "radio restarted"


class BluetoothRecovery:
    def __init__(self, status_provider, *, cycle=cycle_windows_radio,
                 path: Path = APP_DIR / "bluetooth-recovery.json",
                 clock=time.monotonic, epoch=time.time):
        self.status_provider = status_provider
        self.cycle = cycle
        self.path = path
        self.clock, self.epoch = clock, epoch
        self.empty_since = None
        self.empty_scans = 0
        self.attempts = 0
        self.last_attempt = 0
        self.result = "monitoring"
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.last_attempt = float(saved["last_attempt"])
            self.attempts = int(saved["outage_attempts"])
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def status(self):
        return {"enabled": True, "empty_scans": self.empty_scans,
                "outage_attempts": self.attempts, "last_result": self.result,
                "last_attempt_epoch": self.last_attempt or None}

    async def observe(self, raw_count: int | None):
        status = self.status_provider()
        if status["connected"] or not status["configured_count"]:
            self.empty_since, self.empty_scans = None, 0
            if self.attempts and status["connected"]:
                self.attempts = 0
                self._save()
            return
        if raw_count != 0:
            self.empty_since, self.empty_scans = None, 0
            return
        now = self.clock()
        if self.empty_since is None:
            self.empty_since = now
        self.empty_scans += 1
        if (self.empty_scans < 3 or now - self.empty_since < 120
                or self.attempts >= 3
                or (self.last_attempt and self.epoch() - self.last_attempt < 1800)):
            return
        self.last_attempt = self.epoch()
        self.attempts += 1
        # Persist before touching the radio, preventing restart/reset loops.
        self._save()
        log.warning("No BLE devices seen for two minutes; attempting Bluetooth radio recovery")
        try:
            self.result = await self.cycle()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.result = f"recovery failed: {type(exc).__name__}: {exc}"
        self.empty_since, self.empty_scans = None, 0
        log.warning("Bluetooth recovery: %s", self.result)

    def _save(self):
        atomic_write_json(self.path, {"last_attempt": self.last_attempt,
                                     "outage_attempts": self.attempts})
