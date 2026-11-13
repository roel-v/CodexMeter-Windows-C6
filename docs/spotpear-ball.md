# Spotpear Ball and mixed displays

The **spotpear_ball_v2** target supports the tested **Spotpear ESP32-S3 1.28-inch
Ball/BOX V2** unit: 240 × 240 GC9A01 LCD, CST816D touch, 16 MB flash and 8 MB PSRAM.
A round screen or an ESP32-S3 chip alone does **not** establish compatibility.
Do not flash this target onto a different round-display board.

## Pages and controls

There is one Ball theme, adapted from C6 Classic Tasks, with three peer pages:

1. Weekly quota remaining, reset countdown, Running / Waiting / Done.
2. Today: total, uncached input, cached input, output and API-equivalent USD estimates.
3. Seven days: the same breakdown for the rolling seven-day period.

Swipe left/right to advance/go back, wrapping at either end. A short BOOT press
advances one page. Taps do not select another period. The selected page survives
data refreshes, waiting and completion notifications; reboot starts on quota.
Completion alerts use the C6 flash sequence and timing, then return to that page.

Unknown values show "--"; partial estimates use "+" and a coverage note. Input,
cached input and output are nonoverlapping. Rates and history live in the
companion; neither board calculates model pricing independently.

The Ball shows **CodexMeter / Waiting for companion app** before receiving data
and after disconnection. It does not invent USB, battery percentage or charging
indicators: those signals are not verified on this hardware. Audio and automatic
rotation are not supported. Manual rotation supports 0/90/180/270 degrees.

## One companion, multiple displays

Run one Windows companion. Register each display through the existing control
panel registration flow (or CLI devices commands), then restart the bridge
after changing registration. Give devices distinct aliases such as “Desk C6” and
“Ball”. They receive the same usage snapshot and completion events but keep their
own page and settings. Full hardware IDs distinguish devices, including repeated
models; do not identify them only by their friendly Bluetooth name.

Open **Displays** in the control panel to see individual connection status,
firmware/model metadata when advertised, and the last delivery result.
Select a row before changing brightness, manual rotation or screen power.
Unsupported controls are disabled. Brightness is 10–100%; screen off is separate.
The Ball persists brightness and rotation on the device.

Legacy C6 firmware continues to display data and supports screen control, but
appears as **Legacy / unknown** because it does not advertise model capabilities.
This does not indicate a broken connection. The new controls do not guess which
unsupported settings older firmware implements.

## Build and flash

Active build output/caches use D:\build\CodexMeter; retained release bundles
belong under dist/releases on E: in this checkout. See the Windows guide for
adapting these explicit locations on another machine.

~~~powershell
.\build-windows.ps1 -Firmware -Board spotpear_ball_v2
~~~

Before flashing, verify the physical board model and USB serial/device identity.
COM numbers can change. Preserve a full flash backup privately before replacing
unrelated firmware; such backups may contain credentials and must not be shared.

The release includes separate factory images for the Ball and C6. A **factory**
image contains bootloader, partition table and application (plus C6 artwork),
and is written at **0x0** using esptool with the correct chip:

~~~text
Ball: esptool --chip esp32s3 --port COMx write-flash 0x0 spotpear-ball-v2-factory.bin
C6:   esptool --chip esp32c6 --port COMx write-flash 0x0 waveshare-c6-amoled-216-factory.bin
~~~

Install esptool separately for flashing; the desktop executable requires no
Python installation. Never use --force to bypass a chip mismatch. A factory
image can overwrite settings in the gaps between image segments. Prefer the
source upload task for an upgrade that preserves NVS:

~~~powershell
.\flash-windows.ps1 -Port COMx -Board spotpear_ball_v2 -ExpectedDeviceId codexmeter-xxxxxxxxxxxx
~~~

For a first installation, independently verify the board and use -FirstFlash.
The ID check protects the selected unit, but cannot identify the PCB of a device
that is not yet running CodexMeter. The two S3 board targets are not interchangeable.
Recovery uses the original private full backup at offset 0, or the correct public
factory image. Hold BOOT while resetting/connecting if ROM download mode is needed.

## Compatibility and validation

| Companion / firmware | Result |
| --- | --- |
| 3.12.3.0 + new Ball | Three pages, identity/capability metadata and independent controls. |
| 3.12.3.0 + existing C6 | Normal usage/tasks/pricing and legacy screen control; unadvertised controls disabled. |
| Older companion + new Ball | Basic protocol-v1 messages remain readable, but new management/control behavior is not certified; use the matching companion. |
| New companion + explicitly unsupported protocol | That device is reported incompatible and receives no application payload; other workers continue. |
| Older firmware without protocol metadata | Treated as legacy, not automatically assumed to implement new features. |

Physical validation used **one C6 and one Ball simultaneously on one Windows
Bluetooth adapter**. Twenty BLE disconnect/reconnect cycles passed (10 per unit);
the slowest recovery was 16.7 seconds, while the healthy peer kept acknowledging
three-second fixture updates within three seconds. Four simulated identities,
including repeated models and duplicate names, are covered by automated tests;
this is not a claim that four physical displays were tested.

The user confirmed readable pages, both swipe directions/wrap, BOOT page advance
and page retention. Actual captures cover boundary values, waiting, alert
restoration and all manual display rotations. Finger gestures were physically
accepted in the default orientation; rotated finger gestures remain unverified.

**Host sleep/resume cycles and the four-hour soak were deferred to production at
the user's request.** They were not run or passed. Long-duration memory stability
and sleep recovery are therefore not certified by this release.
The existing local diagnostics remain available; there is no app restart watchdog.
