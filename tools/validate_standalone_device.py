"""Check the running standalone bridge against a connected CodexMeter display."""
import argparse
import json
from pathlib import Path
import subprocess
import time

from serial_device import SerialSession, SerialToolError
from validate_standalone import clean_environment


def validate(binary: Path, port_name: str, output: Path):
    binary = binary.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = clean_environment()
    results = {}

    def cli(*args):
        proc = subprocess.run([str(binary), "--cli", *args], cwd=binary.parent, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=90,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        return json.loads(proc.stdout)

    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        status = cli("status")
        devices = status["ble"]["devices"]
        if any(d["connected"] and d["last_ack_age_sec"] is not None for d in devices):
            results["connected_status"] = status
            break
        time.sleep(2)
    else:
        raise RuntimeError(f"No acknowledged display connection: {status}")
    print("Standalone bridge connected and payloads acknowledged.", flush=True)
    results["scan"] = cli("devices", "scan", "--timeout", "4")
    with SerialSession(port_name) as port, (output / "device-serial.log").open("w", encoding="utf-8") as log:
        def wait_for(marker, timeout=12, command=None):
            deadline = time.monotonic() + timeout
            query_at = 0
            while time.monotonic() < deadline:
                if command and time.monotonic() >= query_at:
                    port.write_line(command)
                    query_at = time.monotonic() + 2
                try:
                    line = port.read_line(1).decode("utf-8", errors="replace")
                except SerialToolError:
                    continue
                log.write(line + "\n")
                log.flush()
                if marker in line:
                    return line
            raise RuntimeError(f"Missing device response: {marker}")

        try:
            results["screen_off_request"] = cli("screen-off")
            results["screen_off_device"] = wait_for("HEALTH screen=0", command="health")
            results["screen_on_request"] = cli("screen-on")
            results["screen_on_device"] = wait_for("HEALTH screen=1 ble=1", command="health")
            results["activity_request"] = cli("demo-activity", "--count", "2")
            results["activity_device"] = wait_for("activity run=2")
            results["alert_request"] = cli("demo-alert", "Standalone executable test")
            results["alert_device"] = wait_for("alert show")
            results["idle_request"] = cli("demo-activity", "--count", "0")
            results["idle_device"] = wait_for("activity run=0")
            results["power_device"] = wait_for("battery_present=0 usb_present=1", command="power")
        finally:
            cli("screen-on")
            cli("demo-activity", "--count", "0")
    results["final_status"] = cli("status")
    (output / "hardware-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("Standalone scan, screen controls, activity, alert and USB power checks passed.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("port")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    validate(args.binary, args.port, args.output)
