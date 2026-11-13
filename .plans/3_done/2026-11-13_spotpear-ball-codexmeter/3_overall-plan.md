# Ball and mixed-model displays — overall implementation plan

Date: 2026-11-13. Status: phases 1–6 complete under revised acceptance; see 5_post-implementation-notes.md.
The completed feature is in 3_done. The user has separately authorized commits, push and release publication.
Hardware probing is authorized and partly complete; production implementation was subsequently authorized by the user.

## Architecture and scope

One companion computes one canonical quota/usage/pricing/task snapshot. DeviceManager distributes it to
independent device workers, each with its own connection, bounded queue, acknowledgements, retries and settings.
Do not create a reader or pricing history per display. Do not key devices by model, display name or COM port.
Stable device identity selects the registry entry; BLE address is a discoverable transport endpoint.
Support any configured collection of supported models, subject to Bluetooth adapter resources. Initially certify
C6 + Ball physically; test repeated model identities with simulated transports. Do not claim unlimited capacity.

Extend optional identity metadata with board/model, firmware, protocol version, dimensions and capabilities.
Keep existing UUIDs, identity fields and payload semantics. Parse unknown optional fields defensively.
Missing metadata selects the existing legacy behavior; it must not imply Ball capabilities or break old C6.
Use the existing compatibility checks where available; version labels alone must not determine compatibility.
An unsupported protocol puts that device in an explanatory incompatible state without blocking other workers.
Validate identity length/MTU and all transport buffers before finalizing field names and schema in phase 1.

Board adapters own panel, geometry, backlight, touch, button, power telemetry and optional rotation sensors.
Shared code owns data semantics, protocol, formatting, waiting policy and alert lifecycle. A Ball-specific native
layout owns the three pages; preserve C6 visuals and navigation. No additional Ball themes or audio features.

## Decisions for implementation

- Swipe left goes to the next page, right to the previous; wrap Quota -> Today -> 7 days -> Quota.
- Commit one transition on release: displacement >=40 native pixels, horizontal >=1.5 times vertical,
  duration <=1000 ms. Reject out-of-bounds samples and require a fresh contact for another transition.
  Adjust thresholds only if physical evidence requires it, preserving the same navigation semantics.
- Debounced short BOOT press (50–800 ms, action on release) advances one page as an accessibility fallback.
  Longer holds perform no application action; ROM BOOT/download recovery stays available.
- Keep page in RAM across data refresh, waiting and alerts; reboot starts Quota. Do not synchronize pages
  between devices. During alerts use existing dismissal semantics, without also changing the underlying page.
- Brightness and manual rotation (0/90/180/270 degrees) are per-device settings, persisted using existing
  device-settings conventions. Rotate touch coordinates with the panel. Apply a brightness floor while on;
  explicit screen off remains a distinct control. Do not invent automatic rotation without a verified IMU.
- Battery voltage alone cannot distinguish absent battery, charging or USB power. Initially omit unsupported
  indicators and controls. Add truthful telemetry only if hardware evidence establishes the necessary signals.
  The visible CodexMeter waiting screen establishes that the device is powered even without a USB icon.
- Completion alerts use shared C6 timing/state behavior. Within circle-safe bounds, wrap text on word boundaries
  and ellipsize the final visible line when necessary; preserve readable fonts instead of shrinking to fit.
- On reconnect send fresh desired state, never replay old completion events. Preserve existing event-expiry and
  deduplication semantics per device. One device acknowledgement must not acknowledge another device's delivery.

## Phases and dependency order

| Phase | Deliverable | Prerequisite |
| --- | --- | --- |
| 1 | Hardware closure, compatibility contract and fixtures | Accepted requirements and probe evidence |
| 2 | Mixed-model desktop device management | Phase 1 contract |
| 3 | Production Ball board target and shared firmware boundaries | Phase 1 contract |
| 4 | Three-page round UI, navigation, waiting and alerts | Phase 3 |
| 5 | End-to-end coexistence and reliability evidence | Phases 2 and 4 |
| 6 | Packaging, documentation and release candidate | Phase 5 passes |

See 4_imp-phase1.md through 4_imp-phase6.md for work and exit criteria.
Phases 2 and 3 have no dependency on each other's implementation after the contract is settled.
Execution may be sequential; this plan does not request sub-agents.

## Validation and release boundaries

Run meaningful protocol/registry/queue/formatting tests; do not substitute mocks for hardware evidence.
Build the C6 and Ball targets with distinct D: output directories. Regression-check supported existing targets
when touched by shared adapters. Keep original Ball full flash private and untouched; never flash by COM alone.
Before large builds check D: headroom and cold-storage candidates; no unapproved relocation or C: fallback.
No app restart watchdog, automatic updates, telemetry collection or new cloud service is part of this feature.
Record deviations, commits and results in 5_post-implementation-notes.md during implementation.

## Readiness and unresolved evidence

No unresolved user decision remains. User confirmed readable text and correct RGB/white-on-black output in probe v3.
Power/IMU investigation can finish in phase 1 with a documented unsupported result; it need not block the base UI.
Touch acquisition and BOOT are physically confirmed, but coordinate direction, edge coverage, idle wake behavior
and production gesture recognition remain explicit hardware acceptance work. The Ball now runs the production-target application UI; see 5_post-implementation-notes.md for validation evidence and remaining physical acceptance.
