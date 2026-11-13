# Phase 1 identity and capability contract

Existing identity keys remain required: device_id, short_id, name. Existing identity characteristic and
service UUIDs remain unchanged. Device identity is not a model identifier or a transport address.

Optional flat fields, parsed by codexmeter/device_metadata.py:

| Field | Contract |
| --- | --- |
| model | ASCII identifier, 1–48 characters; e.g. spotpear_ball_v2 or waveshare_c6_amoled_216 |
| firmware | Printable ASCII release identifier, 1–48 characters; not a compatibility predicate |
| protocol | Positive integer; 1 is the existing payload protocol; missing means legacy |
| width, height | Paired integer dimensions, 1–4096 pixels |
| capabilities | Up to 16 identifiers, each lowercase ASCII token <=48 characters |

Missing capabilities means legacy behavior, not an empty capability set. An explicit empty list means none.
Unknown fields and unknown well-formed capability names are tolerated. Malformed declared metadata fails closed.
Protocol values other than 1 are incompatible, not legacy. Expose that device's state without blocking others.
Capabilities initially used: brightness, rotation, auto_rotation, touch, screen, themes, battery, charging, usb.
Ball initially declares brightness, rotation, touch and screen only. Unsupported controls are not sent.
Legacy devices retain the current control path without inventing a model or hardware capability list.

Identity value limit: 512 UTF-8 bytes (BLE attribute ceiling). GATT read uses long-read handling; metadata is not
put into advertising packets. Current firmware identity buffer is only 128 bytes: phase 3 must expand it to 513
and check snprintf output before publishing. Test maximum actual emitted identities, not only average samples.
Existing data payload limit remains 512 bytes with RX buffer 513; this work does not enlarge payloads.
The host parser must enforce the identity limit before JSON parsing when integrated in phase 2.

Registry matching: a known full device ID wins over name, alias, short ID or cached address. Two differing full
IDs never merge. Short IDs remain discovery hints for unresolved entries; validate the full identity before
sending state. Persist observed metadata without changing alias/enabled settings. Settings/commands target full IDs.
No device acknowledgement consumes another device's pending state or event. Do not replay expired events.

Hardware capabilities:

- Confirmed: S3 v0.2, 16 MB flash, 8 MB PSRAM; 4 MB memory pattern pass; GC9A01 LCD with correct RGB;
  CST816D contact reporting/IRQ; BOOT input; BLE connection/read/reconnect twice.
- ADC GPIO1 reports approximately 3.94 V after x2 scaling: voltage only, not validated battery state.
- USB/charging/battery presence and IMU remain unknown and are excluded from initial capabilities.
  Existing two-bus scan found 0x15 and 0x18 only; absence of an IMU is not claimed.
- Schematic download is retained at D:/build/CodexMeter/tmp/spotpear-box-schematic.pdf. Web PDF reader failed;
  signal-level inspection remains a bounded phase-1 follow-up, not grounds to enable guessed capabilities.
- Physical coordinate/edge/idle check pending. Rotation transforms will also be tested with the production driver.

Validation: 16 metadata contract tests pass, including legacy/empty distinction, future protocol/capabilities,
malformed values and representative C6/Ball identity sizes. Integration and worker-isolation tests are phase 2.

### Schematic inspection completed

Manufacturer schematic ESP32S3-1.28inch-BOX, sheet 1, dated 2025-05-16, was rendered and visually inspected.
PL4054 charger CH output drives LED L6 through CM-R1 from USB VCC, not an ESP32 GPIO. USB VCC feeds charger
and power selection; no dedicated MCU USB-presence input is shown. V_BAT reaches GPIO1 through equal 100k
R31/R32 resistors (x2 ADC scaling). No IMU appears on this sheet. Thus this documented board has voltage
sensing but no supported charging/USB-presence or auto-rotation telemetry. Do not infer battery presence or
percent from the USB-powered ADC measurement. Hardware revision differences remain possible; none observed.
The initial Ball capability list stays brightness/rotation/touch/screen, without battery/charging/usb/auto_rotation.
