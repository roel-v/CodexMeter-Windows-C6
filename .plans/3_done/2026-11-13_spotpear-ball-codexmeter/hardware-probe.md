# Ball hardware investigation — 2026-11-13

Scope: user accepted the three previews and authorized necessary hardware probing.
Only the new Ball (USB serial 90:70:69:F4:67:68, currently COM9) is tested.
C6 COM6 and the earlier weather Ball are excluded.

## Confirmed before flashing

- ESP32-S3 QFN56 revision v0.2, 240 MHz, 40 MHz crystal.
- 16 MB flash, manufacturer 20 / device 4018.
- Embedded 8 MB PSRAM AP_3v3 (runtime test pending).
- Secure boot and flash encryption disabled; no efuse modifications.
- Complete 16,777,216-byte original flash saved privately under
  `E:\DeviceBackups\Spotpear-Ball-907069f46768\2026-11-13\original-full.bin`.
- SHA256 `3CDFB8C9624D507651826C768846F59C5A2FFC33CCF6002A21BF41D89D415F9E`.
- Full esptool verify-flash digest matched before original application reboot.
  Recovery instructions and tool logs are beside the private backup.

## Temporary diagnostic

Source: `tools/ball_probe`; separate PlatformIO target and isolated BLE service.
Build/cache/scratch are on D:, not in the source checkout. Firmware tests a 4 MB
PSRAM pattern, documented I2C buses, LCD initialization, battery-divider ADC,
touch coordinates and BOOT input. BLE advertises as BallProbe-F46768, with a
read-only status characteristic unrelated to the CodexMeter service.

Physical display/colors, touch direction and BOOT operation require observation.
ADC voltage alone does not establish USB power, charging or battery presence.
No IMU or trustworthy USB/charging detection is confirmed yet.

The Ball remains on a temporary probe while physical checks are pending; this
is not the final CodexMeter firmware. Preserve the backup for restoration.

## Automated probe results

Temporary firmware flashed with esptool hash verification. Runtime reported
16,777,216 bytes flash and 8,388,608 bytes PSRAM; a 4 MB write/read pattern passed.
15 serial status samples progressed from 2.941 s to 31.009 s uptime without reset.
Touch register 0xA7 responded with 0xB6 on address 0x15. This establishes controller
communication, not correct touch mapping; physical gestures remain to be tested.
The host discovered the isolated BLE service, connected/read/disconnected twice,
and received advancing valid JSON status on both connections.
Battery-divider ADC x2 was around 3.94 V while USB-powered; battery presence,
charging and USB detection remain unverified.

Evidence: hardware/probe-result.json; full serial capture is a local ignored log.
Source is tools/ball_probe. Build output remains under D:/build/CodexMeter.
Physical checks pending: red/green/blue bars, readable orientation, touch coordinates
and BOOT count. Diagnostic screen remains running for those checks.
Startup capture also confirms LCD initialization returned success, touch-bus
address 0x15 and audio-bus address 0x18. Neither documented bus scan found an IMU
address. This is not proof that no IMU exists on another bus or behind power gating.
LCD driver success is not a substitute for physically checking the displayed image.

## Touch investigation follow-up

User confirms BOOT increments, but touch/swipes did not update the first probe.
Do not treat touch as validated from controller-ID reads alone. Probe v2 explicitly
resets/wakes CST816D and writes DisAutoSleep (0xFE=1), matching the installed
SensorLib TouchClassCST816::disableAutoSleep implementation. It services GPIO12
falling-edge events as well as 10 ms polling, rejects invalid contact counts, and
shows IRQ and I2C-error counters. This tests a plausible sleep/event-handling cause;
it is not yet a confirmed root cause or physical touch pass.
Reference: https://api-docs.esphome.io/cst816__touchscreen_8h_source
Capture helper now creates timestamped subfolders so earlier evidence is retained.
Probe v2 flashed with hash verification. Controller acknowledged the sleep-disable
write and readback was 1. Runtime PSRAM test and two BLE read/reconnect checks still
pass. Physical touch retest remains pending; no contacts occurred in the capture.

## Physical retest confirmed by user

The user reports that touch works on probe v2: coordinates and IRQ count change
while swiping, with Err remaining zero. BOOT operation was confirmed earlier.
Basic touch acquisition and BOOT input therefore pass physical testing. This does
not yet validate coordinate orientation, full-edge coverage or production swipe
recognition. Those remain acceptance checks for the final UI.

The v2 combination resolves the observed probe failure. Because sleep configuration,
interrupt servicing and polling interval changed together, the individual cause
has not been isolated. Carry the known-working configuration into the driver:
reset/wake CST816D, disable auto sleep with readback, and service GPIO12 interrupts
with bounded polling. Verify again after idle periods and in the final UI.

Remaining hardware uncertainties: explicit color/orientation confirmation, battery
presence and reliable USB/charging telemetry, and IMU availability. Do not advertise
unverified power or rotation capabilities. The Ball is still running temporary
probe v2; original firmware backup remains intact. C6 was not modified.

## Color correction — probe v3

User reports readable text but cyan / purple / yellow instead of red / green / blue.
These are complementary colors. Local Arduino_GC9A01 1.6.6 source confirms that
ips=true reverses the invertDisplay argument: false sends INVON, true sends INVOFF.
The probe incorrectly called invertDisplay(true) after constructing an IPS panel.
V3 changes this to false (panel INVON), retaining the confirmed v2 touch setup.
Do not copy an ESPHome invert_colors boolean verbatim into a different driver's API.
Physical corrected-color confirmation remains required before marking this check passed.
Probe v3 built successfully and flashed to identity-verified COM9; esptool write hash verified. Physical color check pending.

## Baseline review closed

User confirms probe v3 now has correct red/green/blue bars and white text on black.
Readable display output, basic touch acquisition (v2 physical retest) and BOOT are confirmed.
The driver polarity correction is physically validated. Production firmware must retain the
v2 touch configuration and v3 display polarity. The device remains on temporary probe v3.
No unresolved user decision remains. Coordinate mapping, idle touch, production UI, power/IMU
capability classification and multi-device reliability remain explicit phase acceptance work.
