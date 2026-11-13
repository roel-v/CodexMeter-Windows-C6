# Phase 1 — hardware closure and shared contract

Requirements: R1–R4, R20–R21. No production changes until implementation is requested.

1. Reconcile hardware-probe.md with physical color/orientation confirmation. Preserve backup hash/recovery notes.
2. Check touch coordinates at center and edges, all intended orientations, and after 5 minutes idle. Retain v2
   reset/wake, DisAutoSleep readback and interrupt handling. Do not infer which v2 change fixed the original issue.
3. Review the board schematic for power/charging/IMU signals. Record verified/unsupported/unknown separately.
   No battery disassembly required. Unknown capabilities stay disabled; do not block core functionality on them.
4. Inspect existing ble.py, payloads.py, device_registry.py, multi_ble.py and firmware identity/BLE limits.
   Specify optional identity field names, types, size limits, legacy fallback and compatibility outcomes.
   Separate render capability from transport compatibility. Define device settings scope and command targeting.
5. Create representative legacy C6, metadata-aware C6, Ball, duplicate-name/same-model and incompatible-device
   fixtures. Confirm maximum payload/identity sizes against the actual firmware and host buffers.

Exit: documented hardware capability matrix and executable contract tests; original backup remains recoverable.
Physical observations are labeled as such. No claim of full touch/UI validation from ID reads alone.
