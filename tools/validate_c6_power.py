"""Verify USB-only detection and capture each theme on a board without a battery."""
import argparse
import json
from pathlib import Path
import re
import time

from capture_c6_screen import capture
from serial_device import SerialSession, SerialToolError
from validate_c6_themes import THEMES


def validate(port_name: str, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    records = []
    with SerialSession(port_name) as port, (output / "serial.log").open("w", encoding="utf-8") as log:
        def command(text, marker):
            for _ in range(3):
                time.sleep(0.08)
                port.write_line(text)
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    try:
                        line = port.read_line(1).decode("utf-8", errors="replace")
                    except SerialToolError:
                        continue
                    log.write(line + "\n")
                    log.flush()
                    if " ERROR " in line or "Guru Meditation" in line or "panic" in line:
                        raise RuntimeError(line)
                    if marker in line:
                        return line
            raise RuntimeError(f"No response to {text}")

        initial = command("settings_state", "SETTINGS ")
        original_theme = re.search(r"theme=(\w+)", initial)[1]
        original_auto = re.search(r" auto=(\d)", initial)[1] == "1"
        try:
            command("auto_theme off", "AUTO_THEME OFF")
            port.write_line("settings_close")
            for theme in THEMES:
                command(f"theme {theme}", "THEME_OK")
                assert command("theme", "THEME ").startswith(f"THEME {theme} ")
                # Change from a numeric battery reading back to real hardware;
                # this also checks themes that cache their last battery state.
                command("demo_battery 50", "DEMO_BATTERY 50")
                if theme in ("classic", "nixie"):
                    capture(port, output / f"{theme}-battery-50-demo.png")
                power = command("power", "power ready=")
                assert "ready=1 battery_present=0 usb_present=1 percent=-2 charging=0" in power, power
                time.sleep(0.25)
                capture(port, output / f"{theme}-usb.png")
                health = command("health", "HEALTH ")
                assert "wdt=1" in health and "screen=1" in health
                records.append({"theme": theme, "power": power, "health": health})
                (output / "results.json").write_text(json.dumps(records, indent=2) + "\n")
                print(f"{theme}: verified USB-only power", flush=True)
        finally:
            command("power", "power ready=")
            command(f"theme {original_theme}", "THEME_OK")
            command(f"auto_theme {'on' if original_auto else 'off'}", "AUTO_THEME ")
            command("rotate auto", "orientation auto=1")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    validate(args.port, args.output)
