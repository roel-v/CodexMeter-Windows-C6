# CodexMeter Spotpear Ball — requirements

Date: 2026-11-13
Status: requirements and three native-size previews accepted on 2026-11-13; basic hardware probing validated; phased plan reviewed and ready to start phase 1.
Scope: dedicated firmware for the second Ball, plus compatible Windows companion improvements.
User authorized necessary hardware testing/probing on 2026-11-13, including a backed-up temporary diagnostic firmware. Full CodexMeter firmware implementation, commits and release remain separate next steps.

## 1. Devices and compatibility

R1. Support the confirmed Spotpear Ball v2 / ESP32-S3 BOX model, subject to verifying this unit's
flash, PSRAM and peripherals. Current USB identity is 90:70:69:F4:67:68 (COM9 at investigation).
Identify by hardware identity before operations, not by a permanently assumed COM number.
R2. One Windows companion instance must support multiple displays simultaneously, including
multiple units of the same model and a mixture of supported models. C6 + Ball is the first
physical acceptance case, not a hard-coded two-device limit. Preserve the old weather
Ball, its firmware project and its Home Assistant setup.
R3. Reuse desktop quota, token, price-history and task calculations. All connected displays receive the
same data and accounting periods; the Ball must not run a separate billing or quota calculation.
R4. Extend identity/status with optional board, firmware and capability information. Legacy C6
identities remain valid. Unsupported controls must not be presented as supported. A C6 firmware
update must not be required solely to connect a Ball.
Identify each display by its device identity, not its model or advertised name alone. Track
connection, firmware compatibility and supported controls per device. Page selection and
device-specific settings remain independent; changing one display must not change another.
The desktop device list must distinguish each unit and show its own connection status.
Do not promise an unlimited connection count: document the tested count and adapter limitations.

## 2. Three peer pages

R5. Provide one Classic Tasks-inspired theme, with these pages in order:

| Page | Required information |
| --- | --- |
| Quota & tasks | Weekly percentage remaining; reset countdown; running, waiting and done counts |
| Today | Total tokens and total API estimate; uncached input, cached input and output tokens and their costs |
| 7 days | The same totals and breakdown, for the desktop's existing seven-day period |

R6. Start on Quota & tasks on a fresh boot. Keep the selected page during normal runtime until
manual navigation. Do not cycle pages or return to quota on an inactivity timer. Retain page
selection across temporary alerts and reconnect/waiting views; reboot persistence is not required.
R7. Horizontal swipes navigate directly between the three pages. No period selector, separate
summary page or nested detail page. Proposed wrapping and button fallback will be specified in
the implementation plan; the hardware BOOT/recovery function must remain available.
Use the physically verified CST816D wake/auto-sleep configuration and interrupt handling
from probe v2. Validate touch after idle periods, coordinate mapping, and full swipe recognition
in the production UI; basic probe contact detection alone is not sufficient.
R8. Running means actively processing and not waiting. Waiting means awaiting user input/approval.
Done means completed but unread chats. Use the same validity/expiry rules as the C6; unavailable
counts must not be presented as valid zero counts.
R9. Reset countdown retains the C6 precision: days and hours when at least a day remains,
hours and minutes below a day, with the existing C6 handling near and after reset.
R10. Costs are Standard API-equivalent USD estimates, not subscription charges. Preserve cached
input accounting, model attribution and historical pricing. Mark partial/unpriced estimates,
and unavailable data, as such. Never make missing values appear to be zero usage or free usage.
R11. Preserve overflow-safe compact-token formatting and unit carries. Large values must fit
without clipping significant digits or units. Do not silently remove fields to solve layout pressure.

## 3. Round display and readability

R12. Render natively for a 240x240 circular LCD. Keep text, indicators and touch targets inside
circle-safe bounds with margin; do not crop or simply scale the C6's square layout.
R13. Use the C6 Classic Tasks palette: dark background, blue accents, white primary values,
muted but readable secondary labels, and distinguishable task colors. Labels must convey meaning
without relying on color alone.
R14. First-page percentage and task counts take priority. Each period page is self-contained,
with consistent row order and column alignment. Initial target: 12px or larger labels, 14px or
larger token/cost values, with only minor page indicators permitted smaller. Actual LCD readability
must pass before accepting the design; preserving a screenshot's coordinates is not the goal.
R15. A compact title/status area identifies CodexMeter and connection state. Show power/charging
information only when the hardware supports it reliably; do not infer USB presence from battery
voltage. Unknown hardware telemetry must remain unknown or omitted.
R16. Native-resolution previews must clearly identify sample data and prototype fonts. Their
appearance is a design proposal, not proof of firmware rendering or physical readability.

## 4. Waiting, alerts and power

R17. Follow current C6 disconnect/stale-data behavior: show CodexMeter and Waiting for companion
app instead of automatically blanking the display. Valid companion data restores the selected page;
a BLE connection alone must not make old numbers look fresh. Preserve explicit screen-off intent
according to the existing C6 screen policy. Do not introduce battery-specific automatic blanking.
R18. Show completion alerts from the same desktop events as the C6. Reuse its visual sequence,
hold/reveal timing, replacement and dismissal semantics, adapting text to circular bounds.
Return to the selected page afterward; an alert does not mark a chat read or reset its done count.
R19. Do not add sound, microphone, voice, weather or Home Assistant functionality. Long alert text
must use a defined safe wrapping/truncation policy rather than overflow; specify it during UI design.
R20. Verify battery, charging/USB detection and IMU before enabling related controls. If an IMU
is absent, do not advertise automatic rotation. Use an upright default; manual orientation and
brightness controls must be defined with available hardware during implementation planning.

## 5. Reliability and recovery

R21. Back up this unit's full current flash privately before replacement, with identity, hash and
restore procedure. The prior Ball backup is not a backup of this unit. Keep credentials and raw
flash outside Dropbox, Git and public release assets.
R22. A disconnected/reconnecting device must not block updates to the other display. Reconnect
must restore current data rather than replay obsolete counters or notifications.
R23. Maintain diagnosis of connection state and errors. Do not add an app restart watchdog.
R24. Build outputs, dependency caches and compiler scratch stay on D:. Retain release bundles on
E:. Publish separately named board-specific firmware, verified checksums and clear compatibility
instructions. Public artifacts must not contain device provisioning data.

## 6. Acceptance evidence required before release

- Verify chip/memory, LCD, touch, buttons, power telemetry and recovery for this unit.
- Build Ball and C6 targets; run relevant shared protocol/accounting/formatting tests.
- Inspect all three pages on the actual LCD: ordinary values, 0/100% quota, reset boundaries,
  unavailable/stale data, three-digit task counts, large tokens/costs and partial estimates.
- Verify swipes, selected-page retention, waiting/reconnect restoration, explicit screen controls,
  and completion alerts while on each page. Review circular edges and touch rejection.
- Exercise one companion with C6 and Ball simultaneously, unplug/reconnect each independently,
  and test host sleep/resume. Cover multiple same-model identities in automated tests; label
  same-model physical validation separately if enough hardware is not available.
  Confirm fresh acknowledgements and restored current data without disturbing the other display.
- Specify a bounded sustained-run duration and memory/reconnect criteria in the implementation
  plan, then record actual results. Separate simulation results from physical-device evidence.
- Validate standalone Windows packaging, new/legacy identity handling and device-specific controls.

## 7. Preview package and next step

See [previews/index.html](previews/index.html) and the three 240x240 PNG files beside it.
The repeatable renderer uses Windows Segoe UI as a prototype; implementation font selection must
match its readability and be checked on the real LCD. Preview values are illustrative, not live.
No power icon is drawn yet because power-source sensing for this unit is not verified.

Native-size layouts were accepted. Next: finish hardware probing, then write the technical plan and phase acceptance
criteria. Do not treat these requirements or mockups as completed firmware implementation.
