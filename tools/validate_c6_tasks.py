"""Exercise Classic Tasks layout, stale counts, rotations and switching on C6.

Stop the desktop bridge before running: these are deliberate synthetic samples.
"""
import argparse
import json
from pathlib import Path
import re
import time

from capture_c6_screen import capture
from serial_device import SerialSession, SerialToolError


def validate(port_name, output):
    output.mkdir(parents=True, exist_ok=True)
    records = []
    with SerialSession(port_name) as port, (output / "serial.log").open("w", encoding="utf-8") as log:
        def command(text, marker):
            for _ in range(3):
                port.write_line(text)
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    try:
                        line = port.read_line(0.7).decode("utf-8", errors="replace")
                    except SerialToolError:
                        continue
                    log.write(line + "\n")
                    log.flush()
                    if "panic" in line or "Guru Meditation" in line or " ERROR " in line:
                        raise RuntimeError(line)
                    if marker in line:
                        return line
            raise RuntimeError(f"Missing response to {text}")

        def activity(run, wait, done, valid=True):
            payload = {"v": 1, "k": "activity", "run": run, "wait": wait,
                       "done": done, "chats": valid, "t": int(time.time())}
            return command(json.dumps(payload, separators=(",", ":")),
                           f"activity run={run} wait={wait} done={done} chats={int(valid)}")

        command("auto_theme off", "AUTO_THEME OFF")
        port.write_line("settings_close")
        command("theme classic_tasks", "THEME_OK")
        command("power", "usb_present=")
        for mode in ("token", "quota"):
            command("demo_token_usage" if mode == "token" else "demo_usage", "serial demo_")
            activity(4, 2, 7)
            time.sleep(0.3)
            capture(port, output / f"classic-tasks-{mode}.png")
        for count in (0, 99, 999, 1000):
            activity(count, count, count)
            time.sleep(0.2)
            capture(port, output / f"counts-{count}.png")
        activity(4, 2, 7, False)
        capture(port, output / "counts-unavailable.png")
        activity(4, 2, 7)
        time.sleep(16)
        capture(port, output / "counts-stale.png")
        for cycle in range(12):
            command("theme classic", "THEME_OK")
            command("theme classic_tasks", "THEME_OK")
            activity(cycle, cycle, cycle)
            heap = command("heap", "heap serial ")
            lvheap = command("lvheap", "lv_mem serial ")
            assert int(re.search(r" i=(\d+)", heap)[1]) >= 65000, heap
            assert int(re.search(r" f=(\d+)", lvheap)[1]) >= 16000, lvheap
            records.append({"cycle": cycle, "heap": heap, "lvheap": lvheap})
        for quadrant in range(4):
            command(f"rotate {quadrant}", f"ROTATION {quadrant}")
            activity(4, 2, 7)
            capture(port, output / f"rotation-{quadrant}.png")
        command("rotate auto", "orientation auto=1")
        health = command("health", "HEALTH ")
        assert "wdt=1" in health
        (output / "results.json").write_text(json.dumps({"cycles": records, "health": health}, indent=2))
        print("Classic Tasks captures, counts, staleness, 12 switches, four rotations and watchdog passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    validate(args.port, args.output)
