# Phase 2 — one desktop, multiple models

Requirements: R2–R4, R22–R23. Depends on phase 1 contract.

1. Extend BleIdentity and DeviceConfig/registry migration with optional metadata; preserve aliases and existing
   device IDs/settings. Unknown fields are tolerated. Duplicate names cannot merge different hardware IDs.
2. Extend the existing DeviceManager workers instead of adding a separate Ball manager. Share canonical data;
   keep delivery/acknowledgement, retry state and failures per device. Coalesce obsolete state in bounded queues.
3. Audit reconnect/configuration replay so current settings and snapshot are restored without old alerts or
   counters. Check actual cancellation, write/ack timeouts and fault handling rather than relying on class names.
4. Extend the existing control panel device list with alias, model/unknown, firmware/compatibility, connection
   and last-success/error state. Target controls to the selected device; show only supported capabilities.
   Keep existing add/remove/enable flow. Disabled/forgotten devices must not be silently re-enabled.
5. Keep tray summary understandable when some displays are connected and others are not; link to device details.
   Preserve existing privacy/update/pricing controls and diagnostics. Never expose credentials or chat text in logs.

Exit: tests for mixed models, repeated models/duplicate names, migration, unknown metadata and incompatible
protocol. A stalled/failing worker cannot prevent healthy-worker delivery within two configured update intervals.
Settings for one device cannot affect another. Reconnect tests verify latest state and no stale alert replay.
Physical proof waits for phase 5; simulated device counts are not advertised as tested hardware capacity.
