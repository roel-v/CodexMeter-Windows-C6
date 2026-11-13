# CodexMeter Spotpear Ball — exploration

Date: 2026-11-13
Status: requirements/previews accepted; hardware probe completed through touch retest; phased plan written.
Production implementation has not started. Temporary probe flashing and verified private backup are documented
in hardware-probe.md; 3_overall-plan.md supersedes the preliminary stages below.

## Confirmed scope

The user wants a second CodexMeter firmware for another unit of the same Spotpear Ball v2 model
used by the earlier weather/temperature project. Keep the existing C6 working alongside it.
Only one theme is required: a round adaptation of the current Classic Tasks theme. Other themes
are explicitly out of scope.

First page: weekly percentage remaining, reset countdown, running / waiting / done counts — the
lower half of the C6 first screen. Waiting means awaiting input/approval; done means completed
but unread chats. Preserve all information from Classic Tasks across additional readable pages.
Confirmed navigation: three peer pages in a single swipe sequence:
1. Quota and tasks (initial page).
2. Today: total tokens, input/cached/output breakdown and corresponding API cost estimates.
3. 7 days: the same information for the seven-day period.
There is no separate token-summary page, nested detail navigation or Today/7-day selector.
Each period page is self-contained. Native-size layouts were accepted; gesture details are in 3_overall-plan.md.

Confirmed interaction and standby behavior:
- Keep the selected page until the user navigates again; no automatic page cycling or idle return
  to quota/tasks. Temporary alerts or the disconnected view must not reset the selected page.
- On companion disconnect/stale data, follow the C6 waiting-screen behavior: keep a visible
  CodexMeter / Waiting for companion app screen rather than automatically blanking. Preserve
  explicit screen-off behavior. Power indicators must reflect verified hardware capabilities.
- Show the same Codex task-completion notification as the C6, adapted to the round layout.
  Reuse the existing trigger, visual sequence, timing and dismissal semantics; no new sound feature.
  Return to the previously selected page after dismissal. A completion alert is a transient event,
  distinct from the persistent completed-but-unread chat count.
- C6 timing reference: CODEXMETER_ALERT_HOLD_MS=8000, FLASH_STEP_MS=180, FLASH_STEPS=6,
  ALERT_REVEAL_DELAY_MS=90 in firmware/include/config.h. Reuse shared constants/lifecycle rather
  than a separate Ball-specific interpretation of those timings.

## Device evidence

- USB inventory: C6 remains COM6, serial 20:6E:F1:16:E2:00.
- New ball: COM9, USB serial 90:70:69:F4:67:68, Espressif VID 303A / PID 1001.
- Previous ball: 90:70:69:F6:65:90. The user confirmed this is another unit of the same model.
- Prior project: E:/Dropbox/domotica/home-assistant/spotpear-ball; installed weather project
  documentation: E:/Dropbox/domotica/docs/spotpear-ball-esphome.md.
- That project's verified hardware: ESP32-S3, 16 MB flash, 8 MB PSRAM, 1.28-inch 240x240 round
  GC9A01A LCD, CST816 touch, battery, BOOT button. Confirm flash/PSRAM on this unit before build selection.
- Manufacturer BOX guide agrees with the retained hardware pin map. Older non-BOX balls use
  different pins and must not be substituted.
- LCD SPI: SCLK4, MOSI2, CS5, DC47, reset38; inverted backlight PWM42.
- Touch I2C: SDA11, SCL7, IRQ12, reset6. Battery ADC GPIO1, retained configuration uses x2 scaling.
- Existing reference exposes battery voltage; reliable USB/charging/battery-presence detection
  and an IMU are NOT established. Do not invent USB or auto-rotation telemetry.
- A passive three-second serial read (DTR/RTS false, no commands) produced no identity lines.
  This was the initial passive observation. Subsequent esptool and probe tests confirmed 16 MB flash and
  8 MB PSRAM; see hardware-probe.md for backup and physical touch/BOOT evidence.

Manufacturer reference:
https://spotpear.com/wiki/ESP32-S3-N16R8-AI-DeepSeek-XiaoZhi-XiaGe-Qwen-DouBao-1.28-inch-Round-LCD-BOX-TouchScreen.html

## Feasibility and architecture

Feasible as a new board target in the existing CodexMeter repository, sharing its application
model, BLE protocol, task semantics, formatting and diagnostics. Prefer Arduino/LVGL/NimBLE
already used here; reuse the old ESPHome project's verified hardware knowledge rather than
adding the full Home Assistant/voice/weather runtime to CodexMeter.

The 240px circle has about 19.6% of the visible pixels of the 480px square. Native round layouts,
circle-safe text bounds, suitable fonts and several pages are necessary; scaling/cropping the
C6 screen is not acceptable. Data parity does not require layout or hardware-feature parity.

Existing desktop support already has one worker/queue per display in codexmeter/multi_ble.py.
DeviceManager.broadcast remembers desired state per device and enqueues each payload. The new
ball can receive the same usage/activity data while the C6 stays connected. No duplicate quota
reader, pricing history or task observer is needed.

The current BLE identity contains device_id, short_id and name but no board/capability metadata.
Add backward-compatible optional model, firmware, display geometry and supported-capability data,
shown per device in the desktop. Old C6 identities must still work. Keep current names/UUIDs and
JSON fields compatible; reserve explicit unsupported-version handling for genuinely incompatible
protocol versions. Device status and firmware instructions must distinguish C6 from Ball S3.

Hardware-specific work is required: firmware/include/config.h fixes 480x480; main.cpp creates a
QSPI AMOLED; power.cpp assumes AXP2101; imu.cpp assumes QMI8658; touch_input.cpp only initializes
C6 CST9220 touch. Introduce explicit board adapters/capabilities, not another implicit S3 fallback.
The old Waveshare S3 build target is not a valid Ball target merely because both use ESP32-S3.
Screenshot tooling also assumes 480x480 and must support the reported dimensions.

## Preliminary stages (superseded by 3_overall-plan.md)

1. Hardware baseline and recovery
   Confirm this unit's chip/memory/board variant; back up its complete current flash before any
   replacement. Store device-specific full flash privately outside Dropbox/Git because it may
   contain credentials. The prior ball's backup is not this unit's backup. Record hash, identity
   and restore procedure. Identify actual touch, battery and power capabilities.

2. Board support and communication
   Add a dedicated Ball build target and driver adapters. Bring up native 240x240 LCD, backlight,
   touch/BOOT navigation, battery measurement and waiting-for-companion display. Validate BLE
   identity, usage/activity/alerts and reconnects. Keep C6 target compiling and behavior intact.

3. Classic Tasks round UI
   Preview first; then implement the three peer pages: quota/tasks, Today and 7 days. Each period
   page includes totals, breakdown and costs. Preserve reset precision, partial/unpriced indications, missing/stale
   states and alerts. Use large circular-safe controls, swipe navigation and a button fallback.
   Acceptance: actual LCD readability, long/large values, all page transitions and touch boundaries.

4. Desktop integration and coexistence
   Expose device model/capabilities, distinguish aliases/status, handle legacy C6 identity and
   unsupported features. Validate simultaneous Ball+C6 updates; unplug/reconnect either device
   without disrupting the other. Check sleep/resume, host exit, stale-data/standby and battery use.
   Stage 2 defines the identity contract used here; implementation can be planned independently
   of visual layout once that contract is stable.

5. Reliability and release
   Bounded memory/resource checks and sustained two-device run; recovery evidence; separate clearly
   named C6/Ball assets, checksums, documentation and desktop release. No mixed-board flashing.
   Do not promise C6-only automatic rotation or USB presence unless the Ball hardware supports it.

## Boundaries and remaining design decisions

- No other themes; no temperature/weather, voice assistant, audio or Home Assistant integration
  in the initial CodexMeter firmware. Existing weather project remains untouched.
- Three native-size page layouts are accepted. Final font/readability checks remain hardware acceptance work.
- Preserve all Classic Tasks information; no need to duplicate the C6's physical arrangement.
- Builds, dependency caches and scratch: D:/build/CodexMeter with distinct board output folders.
  Retained public bundles: existing E: dist/releases hierarchy. Private recovery images outside Dropbox.
- No commits, builds, firmware replacement, desktop deployment or publication authorized by this
  investigation. Move to requirements and phased implementation planning after review.

## Investigation outcome

A medium-sized hardware/UI feature, not a one-off theme resize. Existing shared telemetry and
multi-device transport substantially reduce desktop scope. The difficult parts are board adapters,
readable circular layout, truthful hardware telemetry and regression-free two-device behavior.
Initial investigation changed planning documents only. Subsequent diagnostic source is in tools/ball_probe;
the production application has not yet been changed for Ball support.
## Consistency and completeness review — 2026-11-13

Confirmed: one Classic Tasks adaptation, three peer pages, quota/tasks first, Today and 7 days
self-contained. No themes, nested details or period selector. The C6 remains supported.

Clarifications for requirements:
- Today and 7 days use the same desktop-generated periods, totals, price revisions and rounding
  semantics as the C6. Do not calculate a second set of windows or prices on the Ball.
- All three token categories and their estimates, the total and total estimate must be available
  on each period page. Do not silently remove fields to solve layout pressure. Demonstrate their
  readability at native 240px size before accepting the layout.
- Unknown quota/task counts are not zero; partial/unpriced costs remain distinguishable from
  complete estimates. Stale data must not look live. Copy existing accounting semantics.
- The current C6 automatically shows a powered waiting screen on disconnect/stale data, rather
  than blanking after five minutes. The user confirmed the same behavior for the Ball.
- Hardware investigation is a gate, not a user preference: confirm touch, buttons, actual memory,
  battery measurement, USB/charging sensing and IMU. Only advertise supported capabilities.
  If no IMU exists, automatic rotation is unavailable; use a fixed upright default and provide
  manual orientation if needed. If power-source sensing is unavailable, show unknown/omit the
  unsupported indicator rather than falsely claiming USB or charging.
- Hardware setup must preserve BOOT/download recovery. A new firmware installation replaces the
  new unit's existing application; the previous weather unit and its HA configuration are untouched.
- Model/capability metadata must remain optional for legacy C6 firmware. Board recognition alone
  does not make arbitrary firmware mixes compatible. Do not require a C6 reflash merely to add a Ball.
- New firmware release artifacts must identify board and flash offset. Publish Ball firmware and
  the updated desktop; include C6 firmware only if it changed or is explicitly needed in the bundle.
- Per-device queues must prevent a disconnected Ball from delaying C6 delivery. Tests must cover
  both connected, either disconnected, host sleep/resume and reconnect with current state restored.
- Before a public release, define and record a bounded sustained-run duration, memory stability,
  reconnect pass criteria and the physical readability/touch checks. Do not use an open-ended
  overnight-monitoring promise as an acceptance criterion.

Product decisions are now resolved: retain the selected page, follow C6 disconnected behavior,
and show C6-equivalent task-completion notifications. No unresolved exploration questions remain.
Requirements and initial native-size previews are in 2_requirements.md and previews/index.html. Exact pin/memory and
power capabilities remain hardware evidence gates; layout, gesture thresholds, button fallback
and bounded reliability test criteria must be specified before implementation. These are design
and verification tasks, not reasons to ask the user to choose low-level implementation details.
Firmware implementation is not yet ready or authorized by this planning review.
