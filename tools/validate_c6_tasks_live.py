"""Verify the published bridge's real chat counts reach Classic Tasks over BLE."""
import argparse
import json
from pathlib import Path
import subprocess
import time

from capture_c6_screen import capture
from serial_device import SerialSession, SerialToolError
from validate_standalone import clean_environment


def validate(binary, port_name, output):
    output.mkdir(parents=True, exist_ok=True)
    result = {}
    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        process = subprocess.run([str(binary.resolve()), "--cli", "status"],
            env=clean_environment(), capture_output=True, text=True, encoding="utf-8",
            timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        assert process.returncode == 0, process.stderr
        status = json.loads(process.stdout)
        if (status["chat_activity"]["available"] and status["ble"]["connected"]
                and status["tray"]["state"] == "green"):
            result["status"] = status
            break
        time.sleep(1)
    else:
        raise AssertionError(status)

    with SerialSession(port_name) as port, (output / "live-serial.log").open("w", encoding="utf-8") as log:
        def wait(marker, command=None, timeout=15):
            deadline = time.monotonic() + timeout
            next_query = 0
            while time.monotonic() < deadline:
                if command and time.monotonic() >= next_query:
                    port.write_line(command)
                    next_query = time.monotonic() + 2
                try:
                    line = port.read_line(1).decode("utf-8", errors="replace")
                except SerialToolError:
                    continue
                log.write(line + "\n")
                log.flush()
                if "panic" in line or "Guru Meditation" in line or " ERROR " in line:
                    raise RuntimeError(line)
                if marker in line:
                    return line
            raise RuntimeError(f"Missing {marker}")

        result["theme"] = wait("THEME classic_tasks ", "theme")
        result["orientation"] = wait("orientation auto=1", "rotate auto")
        result["power"] = wait("battery_present=0 usb_present=1", "power")
        result["activity"] = wait("chats=1")
        result["health"] = wait("HEALTH screen=1 ble=1", "health")
        assert "wdt=1" in result["health"]
        result["heap"] = wait("heap serial ", "heap")
        result["lvheap"] = wait("lv_mem serial ", "lvheap")
        # A reconnect writes the remembered real usage sample immediately.
        capture(port, output / "classic-tasks-live.png")
    (output / "live-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Published app: live chat counts, BLE reconnect, persisted theme, auto-rotation, USB and watchdog passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("port")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    validate(args.binary, args.port, args.output)
