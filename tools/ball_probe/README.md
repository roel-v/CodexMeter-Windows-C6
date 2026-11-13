# Temporary Ball hardware probe

This is a diagnostic, not the CodexMeter Ball application. It uses documented
Spotpear Ball v2 BOX pins and an isolated BLE service (BallProbe-F46768).
Do not flash without a verified full original backup and matching USB identity.
The tested unit is 90:70:69:F4:67:68, currently COM9; do not assume COM numbers.

From repository root, source scripts/windows-env.ps1 and override
PLATFORMIO_BUILD_DIR to D:\build\CodexMeter\ball-probe-build and
PLATFORMIO_LIBDEPS_DIR to D:\build\CodexMeter\ball-probe-libdeps before using
PlatformIO with -d tools/ball_probe. capture.py collects only this diagnostic's
status over serial and BLE; it does not interact with CodexMeter's device registry.

Screen: RGB bars, touch coordinates, raw battery-divider voltage and BOOT count.
No battery percentage or USB/charging claim is made from ADC readings.
Touch/button samples are counted in RAM. No Wi-Fi credentials are configured.
Original backup and recovery instructions are privately retained outside Git.
