"""On-device theme capture and repeated switching/memory regression checks."""
import argparse
import json
from pathlib import Path
import re
import time

from capture_c6_screen import capture
from serial_device import SerialSession, SerialToolError

THEMES = ["classic", "cyberpunk", "famicom", "animal_crossing", "gundam",
          "gargantua", "nixie", "three_body", "walle", "walle_v10", "walle_blueprint"]


def validate(port_name, output, cycles, screenshots, alerts):
    output.mkdir(parents=True, exist_ok=True)
    records = []
    log = (output / "serial.log").open("a", encoding="utf-8")
    with SerialSession(port_name) as port:
        def command(cmd, marker, timeout=8):
            # Commands here are idempotent. USB CDC occasionally drops a response
            # while rendering; retries still require the expected device reply.
            for attempt in range(3):
                time.sleep(0.06)
                port.write_line(cmd)
                deadline = time.monotonic() + timeout / 3
                while time.monotonic() < deadline:
                    try:
                        line = port.read_line(deadline - time.monotonic()).decode("utf-8", errors="replace")
                    except SerialToolError:
                        break
                    log.write(line + "\n")
                    log.flush()
                    if " ERROR " in line or "panic" in line or "Guru Meditation" in line or "Asserted" in line:
                        raise RuntimeError(line)
                    if marker in line:
                        return line
                log.write(f"HOST retry={attempt+1} command={cmd}\n")
            raise RuntimeError(f"No response to {cmd}")

        command("auto_theme off", "AUTO_THEME OFF")
        port.write_line("settings_close")
        command("health", "HEALTH ")
        for cycle in range(cycles):
            for theme in THEMES:
                command(f"theme {theme}", "THEME_OK")
                assert command("theme", "THEME ").startswith(f"THEME {theme} ")
                for mode in ("token", "quota"):
                    command("demo_token_usage" if mode == "token" else "demo_usage", "serial demo_")
                    time.sleep(0.35)
                    if screenshots and cycle == 0:
                        capture(port, output / f"{theme}-{mode}.png")
                # Exercise changing masks and all battery segments on image themes.
                for percent in (0, 50, 100):
                    payload = {"v":1,"k":"usage","src":"codex","h5":None,"d7":percent,
                               "d7r":int(time.time())+86400,"td":999000000,"t7":5890000000,
                               "st":"ok","t":int(time.time())}
                    command(json.dumps(payload, separators=(",", ":")), "INFO usage ")
                    command(f"demo_battery {percent}", f"DEMO_BATTERY {percent}")
                if alerts:
                    command("demo_activity", "serial demo_activity")
                    command("demo_alert", "serial demo_alert")
                    command("health", "HEALTH ")
                    time.sleep(11)
                    command("demo_idle", "serial demo_idle")
                for quadrant in range(4):
                    command(f"rotate {quadrant}", f"ROTATION {quadrant}")
                    time.sleep(0.15)
                command("rotate auto", "orientation auto=1")
                heap = command("heap", "heap serial ")
                lvheap = command("lvheap", "lv_mem serial ")
                health = command("health", "HEALTH ")
                free = int(re.search(r" i=(\d+)", heap)[1])
                lvfree = int(re.search(r" f=(\d+)", lvheap)[1])
                largest = int(re.search(r" b=(\d+)", lvheap)[1])
                assert free >= 70000, (theme, heap)
                minimum = re.search(r" min=(\d+)", heap)
                if minimum:
                    assert int(minimum[1]) >= 48000, (theme, heap)
                assert lvfree >= 16000 and largest >= 8000, (theme, lvheap)
                assert "wdt=1" in health, health
                records.append({"cycle":cycle, "theme":theme,"heap":heap,"lvheap":lvheap,"health":health})
                (output / "results.json").write_text(json.dumps(records,indent=2), encoding="utf-8")
                print(f"cycle={cycle+1} theme={theme} internal_free={free} lvgl_free={lvfree}", flush=True)
        command("theme classic", "THEME_OK")
        command("rotate auto", "orientation auto=1")
        command("demo_idle", "serial demo_idle")
    log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port")
    parser.add_argument("output", type=Path)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--screenshots", action="store_true")
    parser.add_argument("--alerts", action="store_true")
    args = parser.parse_args()
    validate(args.port, args.output, args.cycles, args.screenshots, args.alerts)
