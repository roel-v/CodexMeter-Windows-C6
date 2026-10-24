# Windows port implementation

The host protocol and Codex usage reader remain shared with macOS. On Windows,
the bridge uses Bleak's WinRT backend. The optional Tk control panel runs each
BLE CLI operation in a child process, keeping the GUI thread and WinRT event
loop separate.

## Platform changes

- `daemon.DaemonLock` uses a nonblocking byte-range file lock on Windows and
  retains `flock` on POSIX. Closing the process releases the lock.
- `ipc` retains Unix sockets on POSIX. Windows uses an ephemeral TCP port bound
  exclusively to loopback. Every request carries a random per-run secret;
  Windows DPAPI encrypts that secret for the current account in the endpoint
  file. JSON is newline-framed, size-limited and timed out. Authentication is
  checked before dispatch, including shutdown requests.
- Hook processes use the same transport and keep their failure-tolerant
  contract. The install script preserves unrelated hook definitions and creates
  backups. Trust is reviewed by the user through Codex, not assigned by this app.
- `screen_policy.WindowsLockDetector` polls the input desktop using Win32 APIs.
  An inaccessible secure desktop counts as locked; errors preserve the previous
  state. Existing `mac_locked`/`mac_unlocked` wire reason strings are retained for
  protocol compatibility and do not select the detector.
- Codex app-server runs as a native executable with hidden console flags. The
  default resolver finds PATH installations or the Codex desktop binary
  directory. Explicit `.cmd` wrappers produce an actionable error.
- Serial tools use PySerial on Windows, with DTR/RTS initially disabled;
  POSIX serial behavior is preserved.

Runtime state is machine-local in `.codexmeter`, not Dropbox: event endpoint,
device registry, usage cache and logs. The source may live in Dropbox while all
active build products live on D: via `scripts/windows-env.ps1`.

## C6 target

`waveshare_c6_amoled_216` uses the manufacturer's QSPI/I2C pins, ALDO3 panel
power-cycle reset and SH8601-compatible command sequence. LVGL shares the
ESP-IDF internal heap, with real allocation/fragmentation monitoring, rather
than reserving an isolated pool. It uses two 20-row draw buffers and one
20-row rotation buffer.

The C6 build packs immutable RGB565 backgrounds and Nixie sprites into the
existing data partition at 0x610000. Assets are mapped read-only and checked
against build-specific sizes and CRCs. WALL-E gauges use cropped RAM image
overlays instead of writing to a full-screen image. Original TTF families and
sizes are converted to static 2-bit Latin fonts using lv_font_conv 1.5.3.
Their original TTF hhea line metrics are retained so labels keep the original
vertical spacing, including the leading used above large numeric readouts.
Generated sources and packs live under the configured D: build directory.
The S3 loaders and font lifecycle remain separate behind board guards.

USB screenshots stream CRC-checked tiles from an LVGL refresh; only the PC
assembles the full frame. The shared alert, screen-control and settings paths
remain in use. C6 fixed fonts cover Latin UI text; Unicode payloads remain
intact on the host for S3 clients, but unsupported glyphs cannot be rendered.

Power status uses the AXP2101 battery-present and VBUS status, independently
of charging. A verified USB supply with no battery uses `BATTERY_USB_POWER`
(-2); -1 remains unknown and 0..100 remains a battery percentage. All themes
render that state as USB. Battery insertion/removal interrupts refresh the
status, as do the existing polls and display-wake refresh. Serial `power`
refreshes the real reading and clears a simulated battery display. Hardware
validation for all 11 themes is retained in `dist/c6/usb-indicator-validation-final`;
an attached physical battery was not available for this test.

No touch or audio implementation was added. The firmware does not introduce a
new API key or authentication store on the device. See the Windows setup guide
for the limits of local token counts and supported hook environments.

## Verification

Run `build-windows.ps1 -Test -Firmware`. The Windows integration tests use real
local sockets, DPAPI and child hook processes. They check fragmented TCP input,
wrong-token rejection, task start/completion, clean shutdown and cross-process
singleton behavior. The GitHub workflow tests macOS and Windows; macOS CI still
needs to run remotely after these local changes.

Firmware compilation and Python tests do not establish hardware correctness.
Hardware acceptance requires flash/boot, readable screen, all three buttons,
orientation, BLE identity and reconnect, real usage, completion alert and
lock/unlock sleep/wake tests on the intended board.

The 17 October 2026 C6 theme acceptance run covers all 11 themes in both token
and quota modes, 0/50/100 percent quota and battery values, activity and
completion alerts, and all four software rotations. CRC-checked on-device
screenshots and serial memory/watchdog results are retained in
`dist/c6/theme-validation/acceptance`. The static-font spacing was visually
checked against the original layouts. This is a bounded hardware test, not a
claim of long-term soak testing. Physical button behavior is a separate check.
Three additional complete switching cycles passed without crashes or watchdog
resets. Final per-theme free memory remained within 2 KiB of the first cycle;
the lowest internal-heap watermark was 68,704 bytes (about 67 KiB). Results are
in `dist/c6/theme-validation/repeat-switching` and `summary.json`.

The final application uses about 76% of its 3 MiB partition. The 4.05 MiB
artwork pack is separate; the combined factory image includes it at 0x610000.
When flashing individual retained files, use the matching app and asset pack;
an app-only first installation cannot provide the artwork. Normal PlatformIO
upload includes both. The original factory backup and the previously confirmed
Classic-only build remain available in the parent folder's `backups` directory.

## Standalone Windows executable

`windows_entry.py` dispatches the GUI (no arguments), background bridge (`--daemon`)
and command-line client (`--cli`). Nuitka 4.3.1 bundles Python, Tk, Bleak/WinRT
and application modules into one executable. Child roles use the outer onefile
path from `sys.argv[0]`, rather than treating the embedded runtime as a Python
interpreter. The GUI leaves the Codex setting as `codex` so automatic discovery
continues across Codex updates.

`build-standalone.ps1` uses the installed Visual C++ compiler and keeps build
output, Nuitka caches and temporary files under `D:\build\CodexMeter`. The
published executable is `dist/windows/CodexMeter.exe`; it needs no Python
installation or installer. Codex and Windows Bluetooth remain prerequisites.
The current-user login shortcut runs this executable with `--daemon`.

Packaging acceptance on 17 October 2026 passed 153 Python tests. The published
executable also passed GUI construction and GUI-to-CLI subprocess checks,
WinRT imports, DPAPI, registered-device reads and fresh Codex usage retrieval,
with Python removed from PATH and an independent working directory. These
checks do not constitute a clean-machine VM test. Live C6 checks cover usage
acknowledgements, screen controls, activity, completion alerts and USB power.
Evidence and the previous shortcuts are retained in `dist/windows/validation`.

Launching the actual login shortcut with Python absent from PATH and restarting
the C6 both passed the same live checks. The bridge reconnected automatically.
No firmware update was needed for packaging. See the published manifest for the
executable checksum and exact validation report locations.

## Windows tray lifecycle

The Windows daemon owns one tray icon and one lazily created control panel.
Tk runs on the main thread, the native pystray backend runs its Windows message
loop, and the existing asyncio/BLE bridge runs on a worker thread. Queues deliver
menu actions and one-second connection snapshots to Tk; shutdown is posted to
the asyncio loop with `call_soon_threadsafe`. The daemon lock prevents duplicate
icons. Launching the standalone executable again requests the existing panel
through the authenticated local event endpoint.

The tooltip and menu distinguish connected, partially connected, reconnecting
and unconfigured displays. Closing the window withdraws it. Quit requests a
graceful bridge shutdown, then removes the tray icon and destroys the panel.
The pinned pystray Win32 backend restores its icon after Explorer restarts.
The entry point is named `windows_entry.py` to avoid shadowing the `codexmeter`
package in Windows setuptools discovery. Runtime dependencies are bundled in
the same onefile executable, including Pillow for the generated status icons.

Tray acceptance passed all 160 regression tests and native source/onefile
checks: icon creation, connected/disconnected tooltip and menu, native left
click, menu opening, panel reuse, close-to-tray and the Quit callback stopping
the worker and removing the icon. The published executable was launched from
the existing login shortcut with Python removed from PATH. Repeated launches
opened one panel, and a native WM_CLOSE hid it while BLE remained connected.
Reports are in `dist/windows/validation/tray-build` and `tray-published`.
