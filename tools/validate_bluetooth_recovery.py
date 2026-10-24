"""Inject empty-scan evidence into the monitor and exercise a REAL radio reset.

Other Bluetooth accessories briefly disconnect. No persistent failure is
introduced. Run the packaged bridge alongside this test to verify reconnection.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codexmeter.bluetooth_recovery import BluetoothRecovery


async def validate(output):
    output.mkdir(parents=True, exist_ok=True)
    now = [10000.0]
    monitor = BluetoothRecovery(lambda: {"connected": False, "configured_count": 1},
        path=output / "isolated-recovery-state.json", clock=lambda: now[0], epoch=lambda: now[0])
    # Deliberate test evidence, not an attempt to jam the Windows Bluetooth stack.
    monitor.attempts = 0
    monitor.last_attempt = 0
    for t in (10000, 10060, 10120):
        now[0] = t
        await monitor.observe(0)
    assert monitor.result == "radio restarted", monitor.status()
    result = {"simulated_empty_scans": 3, "simulated_elapsed_seconds": 120,
              "real_radio_cycle": True, "monitor": monitor.status()}
    (output / "recovery-test.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Recovery monitor triggered a real radio restart after simulated empty scans.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    asyncio.run(validate(args.output))
