# CodexMeter for Windows and Waveshare ESP32-C6

This local port adds a Windows control panel and background Bluetooth bridge to
[tomatoeggs/CodexMeter](https://github.com/tomatoeggs/CodexMeter), plus an English,
memory-conscious firmware target for **ESP32-C6-Touch-AMOLED-2.16(-EN)**.
The original firmware target is for the **S3**, not the C6.

## Requirements

- Windows 10/11 with Bluetooth LE enabled.
- Codex installed and signed in with the account whose limits you want to show.
  The bridge uses the local Codex app-server; no separate API key is needed.
- The standalone executable needs no Python installation. Building from source
  requires Python 3.11+ with Tk (the setup uses Python 3.12) and `uv` on PATH.
- A USB-C **data** cable for flashing; USB power is sufficient in normal use.
  The EN board is supplied without a battery.

## Locations

Source and retained deliverables belong under:

```text
E:\Dropbox\3D Printing\3rd party designs\20261017 CodexMeter\CodexMeter
```

The scripts explicitly put active builds, Python dependencies, PlatformIO
packages, download caches and temporary files in `D:\build\CodexMeter`.
They do not relocate unrelated software or repoint general user-data folders.
Small machine-local runtime files remain in `%USERPROFILE%\.codexmeter`;
Codex keeps its existing login and configuration directory.

## Set up the Windows app

For the standalone app, run `dist\windows\CodexMeter.exe`. It is a single
executable with the GUI, Bluetooth bridge and command-line tools bundled.
Codex must still be installed and signed in. No installer is required.

The Windows Startup shortcut runs the same executable with `--daemon` to
start the background bridge at login. Keep the executable at that location,
or update the shortcut after moving it. Codex's versioned executable path is
discovered automatically; leave the Codex executable field set to `codex`.

The background bridge shows a **CodexMeter system tray icon** at login. Green
means all registered displays are connected; amber means disconnected/reconnecting
or only some displays are connected; gray means no display is configured.
Hover for the connection status, or right-click for the status and menu.
Click the icon or choose **Open control panel** to open the panel. Opening the
executable again brings the same panel forward. Closing its window hides it;
**Quit CodexMeter** in the tray stops the bridge and closes the panel. Windows
may initially put the icon in the hidden-icons area beside the clock.

The onefile bundle extracts its private runtime into a temporary directory
while running and removes it when that process exits. This is not a system
Python installation. Logs and device registration stay in `.codexmeter`.

For development from source, open PowerShell in this project folder:


```powershell
.\build-windows.ps1 -Test
.\install-windows.ps1
.\Start-CodexMeter.ps1
```

You can then double-click **CodexMeter.lnk** in the project folder.
`Start-CodexMeter.ps1` prefers the published executable when present, and
otherwise launches the source version from the D: environment.

In the app, click **Read usage** first. The Codex executable is found on PATH or
in the desktop app's local binary directory. If needed, enter its full
`codex.exe` path. An npm `.cmd` wrapper is not accepted: use its underlying
native executable. No credentials are copied to the ESP32.

Click **Start bridge** to run the background process without a console window.
Closing the control panel leaves it running; **Stop bridge** stops it cleanly.
In the standalone tray app, stopping the bridge also closes its tray and panel.
**Status** reports task activity and device connectivity. **Open log** opens the
local rotating log. The log can include task summaries; it stays on this PC.

Build the onefile executable with `build-standalone.ps1`. Nuitka 4.3.1 and the
installed Visual C++ compiler build under `D:\build\CodexMeter\desktop-onefile`;
compiler caches and scratch also remain on D:. The final executable is copied
to `dist\windows` after validation. Diagnostic commands use
`CodexMeter.exe --cli status` or `--cli once`; `--self-test OUTPUT.json`
checks the bundled GUI, Windows Bluetooth imports, DPAPI and subprocess modes.
It also tests the native tray icon, click-to-open, hide/reopen, status changes
and the Quit menu callback without stopping the live bridge.

## Build and flash the C6

```powershell
.\build-windows.ps1 -Firmware
& D:\build\CodexMeter\venv\Scripts\python.exe -m serial.tools.list_ports -v
```

Identify your board's COM port from the USB device listing. Do not select a
Bluetooth virtual COM port or another device. For example, **only if COM6 is
your C6 board**:

```powershell
.\flash-windows.ps1 -Port COM6 -FirstFlash
```

The default target is `waveshare_c6_amoled_216`. Flashing replaces the existing
application. If the port is unavailable, hold **BOOT** while reconnecting USB,
then release it and retry with the port Windows assigned. Close any serial
monitor before uploading. Subsequent uploads omit `-FirstFlash` so the script
checks for a running CodexMeter identity. Esptool still checks the chip family
on first flash; the script never disables that check.

The normal C6 upload writes both firmware and the raw artwork pack at
`0x610000`. Do not run `uploadfs` for C6: that would replace the mapped artwork
with an incompatible filesystem. Do not flash the S3 binary onto this board.

## Connect the display

This board was flashed and registered on 17 October 2026 as
**CodexMeter-00E216**, alias **Waveshare C6**. Its complete original 16 MB flash
backup, verified against the board before flashing, is in
`../backups/20261017-COM6-original/`; that folder includes restore instructions.
Hardware test evidence is in `dist/c6/hardware-test-20261017/`.

1. Power the flashed board and enable Windows Bluetooth.
2. Click **Scan displays** in the app. Find `CodexMeter-XXXXXX`.
3. Enter that six-character display ID, give it a name, and click
   **Register display**.
4. Stop and start the bridge to reload the registered device list.
5. Click **Test alert**, then **Read usage** / **Status** to check both paths.

The bridge connects directly through Bluetooth LE. A Bluetooth COM port is not
used. It can reconnect to registered devices and handle multiple displays.

## Task alerts and optional startup

After the usage display works, install the two task hooks:

```powershell
.\install-windows.ps1 -InstallHooks
```

This merges `UserPromptSubmit` and `Stop` entries into the existing
`$CODEX_HOME\hooks.json` (or `%USERPROFILE%\.codex\hooks.json`) and backs up the
file before changing it. **Review and trust the new definitions in Codex
`/hooks`**; installing a hook does not bypass Codex's trust requirement. Open a
new Codex session after installation. Hook failures return successfully so an
offline display does not block Codex.

These hooks apply to supported local Codex sessions. Cloud-orchestrated Work
chats do not run local command hooks. Account limits and local token statistics
can still be read independently of hooks. See [official hook documentation](https://learn.chatgpt.com/docs/hooks).

For automatic startup after Windows sign-in:

```powershell
.\install-windows.ps1 -StartAtLogin
```

This creates a per-user Startup shortcut; no administrator account or Windows
service is needed. The device sleeps after the configured lock timeout and
wakes when the interactive desktop is available again. A secure desktop (for
example a long-lived UAC prompt) is treated as locked; an unavailable lock-state
query preserves the previous state.

## What the display shows

- When Codex returns both windows: remaining 5-hour and 7-day quota, with reset
  countdowns.
- When only a 7-day window exists: today's and the last seven calendar days'
  local token activity, plus the remaining 7-day quota.
- Running task indicators and an English **Task complete!** alert.
- Brightness/settings, battery state where a battery is installed, display
  sleep, and orientation changes using the IMU.

Token activity comes from this computer's local session logs and includes
cached input. It is **not** a percentage of subscription usage, and does not
include deleted logs, other computers or cloud-only chats. Daily boundaries
follow the computer's local timezone.

## C6 feature limits and hardware validation

All 11 original themes are included: Classic, Cyberpunk, Famicom,
Animal Crossing, Gundam, Gargantua, NIXIE RACK, Three Body, WALL-E,
WALL-E EARTH and WALL-E BLUEPRINT. Hold KEY or BOOT to browse backwards or
forwards. Auto theme cycling is available in Settings; it is independent of
the device's automatic screen orientation.

The C6 has no PSRAM. Its themes use flash-mapped artwork, static Latin fonts
generated from the original typefaces, partial LVGL buffers and small mutable
gauge overlays. Rotation uses a strip-sized buffer. The S3 target keeps its
original PSRAM and dynamic-font path. Arbitrary Unicode/Chinese glyphs are
not available on C6. Historical design documents remain in Chinese; the
runtime UI and this setup path are English.

The battery indicator shows **USB** when the AXP2101 detects USB power and no
connected battery. An attached battery still shows its percentage; an unknown
reading remains unknown. The `-EN` board is sold without a battery. All 12
themes support the USB indicator. Serial `power` refreshes the real hardware
reading and reports battery/USB detection for diagnostics.

Firmware builds require Node.js for the pinned LVGL font converter, installed
locally under `D:\build\CodexMeter\font-tools`. Generated fonts and artwork
packs also stay on D:. Screen captures use tiles rather than a device-sized
framebuffer; install the optional PC tooling with
`uv pip install --python D:\build\CodexMeter\venv\Scripts\python.exe -e '.[hardware]'`
after loading `scripts/windows-env.ps1`, then run
`python tools/capture_c6_screen.py COM6 capture.png` with that environment's Python.

Controls: **KEY/IO10** decreases brightness or moves left; **BOOT/IO9** increases
brightness or moves right; long presses select the previous/next theme.
The middle **PWR** button opens/confirms settings; a long press toggles the
display. Touch input and audio are not implemented by this port.

C6 auto-rotation reverses the sensor Y axis and applies a permanent 90-degree
counterclockwise correction for the IMU-to-panel alignment. The sideways
orientation was visually confirmed with the buttons on the left and USB-C port
on the right. After the Y correction, the user confirmed correct display in
all four orientations.
Auto-rotation is enabled at boot. Serial `rotate`
commands remain absolute manual overrides; `rotate auto` restores the sensor.

The pin map, ALDO3 display reset and SH8601-compatible initialization come from
[Waveshare's C6 Arduino demo](https://github.com/waveshareteam/ESP32-C6-Touch-AMOLED-2.16/tree/main/02_Example/Arduino-v3.3.3/09_LVGL_V9_Test).
The product page labels the panel CO5300, while the manufacturer's code uses
SH8601 commands. The physical C6 has passed boot, BLE identity/connection,
real usage delivery, alert/activity processing, screen controls, rotation and
memory checks. The user confirmed readable display output and the corrected
orientation on the board. Physical button operation remains untested.

## Classic Tasks theme

Select **Classic Tasks** in the display's theme settings (serial: `theme classic_tasks`).
This additional Classic variant puts Running, Waiting and Done in the lower-right
quarter, with a "Weekly quota" heading and the weekly reset below the remaining percentage in bright white
24-pixel text. Classic remains
available separately.

The Windows companion observes live local Codex desktop chat state:

- Running: an active chat that is not waiting for input or approval.
- Waiting: Codex reports a pending user-input or approval request.
- Done: the latest turn completed and the chat is still unread.

Archived chats, subagents and remote/cloud chats are excluded. A completed final
message that asks a question is a completed turn; only a live input/approval
request counts as Waiting. Reading a completed chat removes it from Done.
Updates normally arrive within five seconds. Missing data shows `--`, including
after 15 seconds without a desktop heartbeat. It is never treated as zero.

The observer uses Codex's local Windows named pipe, plus read-only metadata from
`CODEX_HOME` (default `%USERPROFILE%\.codex`). It follows state without marking
chats read or sending prompts/approvals, and discards chat text. It reconnects
automatically when Codex restarts. This is a private versioned desktop protocol:
a future incompatible Codex update may require updating the observer, but no
installed Codex executable path is hardcoded. Quota sync and the tray continue
working when the chat observer is unavailable. Multiple saved account identities
currently leave the counters unavailable rather than combine account totals.

## Automatic Bluetooth recovery on Windows

If a configured display remains disconnected and at least three completed scans
find **no Bluetooth LE devices of any kind** over two minutes, the app briefly
cycles the Windows Bluetooth radio and resumes discovery. This recovers the
stalled discovery observed overnight on 18 October 2026. The screen wakes and
receives current data through the existing reconnect path.

Recovery requires a single Bluetooth radio already switched on. It does not
turn Bluetooth on if you disabled it yourself. Any connected CodexMeter, any
nearby BLE advertisement, or an unsuccessful scan prevents the empty-scan
trigger. Other Bluetooth accessories may briefly disconnect during recovery.
Attempts are at least 30 minutes apart, with at most three per outage. The
attempt count clears after a display reconnects; the cooldown persists across
app restarts in `%USERPROFILE%\.codexmeter\bluetooth-recovery.json`.
`--cli status` includes `bluetooth_recovery` diagnostics, and attempts are logged.

## Local exit diagnostics

Version 3.12.1.5 records process evidence in
`%USERPROFILE%\.codexmeter\diagnostics`:

- `lifecycle.log`: startup PID/parent PID, Windows job/console context, explicit
  tray and authenticated IPC shutdown requests, UI-loop exit, and exception
  traces from the daemon, worker threads, Tk callbacks and asyncio callbacks.
  Two rotated backups keep this log bounded to approximately 6 MB.
- `last-run.json`: run identifier, startup time, outcome, and bridge/UI heartbeat
  timestamps, saved every 30 seconds. Only the daemon-lock owner writes it.
- `fault-<run-id>.log`: Python faulthandler output for supported native faults;
  the newest ten files are retained. Empty files are normal for healthy runs.

On the next manual or login launch, a previous run without an exit record is
reported as `PREVIOUS_UNCLEAN_EXIT`. This does not assume whether it was killed,
crashed, lost power, or was interrupted by Windows shutdown. Forced termination
can prevent any in-process crash handler from running. The existing
`codexmeter.log` and Windows Application event log remain useful alongside these
files. Reports remain local; no automatic uploading or process restarting was added.

The 18 October 2026 exit around 13:52 had no recorded shutdown, Python traceback,
matching Windows crash report, or reboot. The display logged BLE disconnection
and switched off after its normal five-minute host timeout. Launch probes found
kill-on-close jobs for directly invoked tool processes, but the actual packaged
app launched using Start-Process did **not** report that immediate-job flag.
Job membership alone therefore does not establish the cause. The historical
cause remains unconfirmed; diagnostic build 3.12.1.5 captures evidence for any
recurrence without changing the app's shutdown or recovery policy.

## Remove the installation

Stop the bridge and run `.\uninstall-windows.ps1`. It removes the local launcher
and optional Startup shortcut, preserving source, dependencies and data.
Disable installed CodexMeter hooks in `/hooks`, or remove just their entries
from `hooks.json`. Do not restore an old whole-file backup over later unrelated
hook changes.

### Powered-on waiting screen (24 October 2026)

The firmware now shows three centered lines at startup: blue `CodexMeter`,
USB/power status, and dim gray `Waiting for companion app`. The selected theme
returns when a valid usage, activity, or alert payload arrives. A BLE connection
alone does not dismiss the waiting screen. Disconnection returns to waiting;
a connected companion that sends no payloads for five minutes does so too.
These automatic conditions no longer blank the display. Explicit screen-off
commands, the power button, and the companion's Windows lock policy still work.
The waiting screen uses actual battery/USB status and existing OLED pixel drift.

Hardware checks: `tools/validate_c6_waiting.py COM6 OUTPUT --waiting --hold 310`
checks the waiting screen beyond the old timeout; omit `--waiting` after opening
the companion to verify the normal theme returns. Each check saves a screenshot
and health records. Firmware bundles and evidence are under
`dist/c6/waiting-screen-20261024/`.
