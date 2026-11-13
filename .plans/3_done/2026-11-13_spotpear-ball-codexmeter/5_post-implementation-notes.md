# Implementation history and release handoff

Current status: implementation and local validation complete; publication authorized by the user.
Earlier entries below are chronological records, not current blockers.

## Phase 1 — in progress

Implemented optional metadata value object and validation in codexmeter/device_metadata.py.
Added tests/test_device_metadata.py: 16 tests passed using the project environment; scratch on D:.
Recorded identity-contract.md, legacy behavior, 512-byte limits and truthful initial Ball capabilities.
No desktop runtime behavior is changed yet; integration follows in phase 2.
Original backup is intact. Ball remains probe v3. No C6 flash or app deployment performed.

Remaining before phase 2: physical coordinate/edge/idle confirmation and finish schematic capability review.
No commits made; phases 2–6 are not yet implemented. User authorized sequential implementation.
Schematic review complete: charger status is LED-only, VBAT divider is GPIO1, no MCU USB-presence net or IMU shown. Only physical idle/coordinate acceptance remains before phase 2.
Lane move attempted but Windows reported the directory in use. Verified no destination was created; all plan files remain together in 1_planning. Capture path retained. Retry the whole-directory move when the lock clears; no process was terminated.

## Phase 1 completed

User confirms touch responds after five minutes idle, Err remains zero, and X/Y increase in the expected
left-to-right/top-to-bottom directions. Together with confirmed display colors and BOOT, the physical baseline
passes. Schematic reviewed; unsupported power-source/charging/IMU capabilities excluded. Contract tests pass.
Production rotation transforms and gesture recognition remain phase 3/4 tests, not inferred from the probe.

## Phase 2 completed in source

Integrated metadata into BLE identity parsing, registry persistence and worker status. Strict full-ID matching
prevents two known IDs merging through a short-ID collision. Added targeted screen/brightness/rotation IPC
with capability validation and a Displays control-panel window. Existing legacy screen control remains supported.
Control queue coalescing is per command; late ACKs cannot overwrite newer desired state. Reconnect suppresses
superseded state and expires completion events after 60 seconds (explicit new bound; previously no host expiry).
Aliases/enabled state survive observed metadata updates and CLI rename/enable actions.

Validation: 81 focused tests, then 250 full desktop tests passed. New coverage includes four simulated identities,
mixed/repeated models, duplicate advertised names, malformed identity, incompatible protocol, full queues,
targeted settings, old ACKs and alert expiry. Physical two-display testing remains phase 5.
No installed desktop deployment or C6 flash yet. Phase 3 board target is now building.

## Phase 3 completed
Ball target builds with GC9A01/CST816D drivers, persisted manual rotation, no speculative battery/USB/IMU
capabilities, and compact extended identity. Flashed only COM9; factory image verified by esptool.
Actual 240x240 waiting screenshot reviewed. Two BLE connections verified the full identity and eight
brightness/rotation ACKs. C6 regression build passed (134 seconds); C6 was not flashed.
Evidence: D:\build\CodexMeter\tmp\ball-phase3-{build,flash}.log, ball-phase3-ble.json, ball-waiting.png,
c6-ball-regression-build.log. Original backup remains untouched.

## Phase 4 in progress
Native three-page UI implemented with shared dashboard/token formatting and shared C6 alert timing constants.
Waiting/alerts preserve selected page; touch/BOOT wrap peer pages. Per-category/total API estimates distinguish
unknown, unavailable and partial data; sum overflow is unavailable rather than wrapped. Unavailable task counts
show "--"; values over 999 show "999+". No false USB indicator. Hardware screenshot/boundary review pending.
Fixed shared reconnect policy: receiving data no longer wakes an explicitly powered-off display.

### Phase 4 automated evidence
Actual Ball framebuffer captures show Quota/tasks, Today and 7 days. Completion overlay was exercised on
all three; restored captures are byte-identical to the respective pre-alert captures. Tested 0/100%, expired
reset, 999 and 999+ tasks, missing breakdown, uint64-max token/cost values, partial coverage, stale state,
and all four manual rotations. Visual review found no clipped required values in these cases.
The first exact-image comparison correctly caught the example's reset crossing from 4h to 3h; moved the
fixture 30 minutes away from a boundary. This was a fixture issue, not lost page state.
A disconnect capture initially preceded the five-second policy poll; corrected the test to wait six seconds.
The waiting view is verified. These captures are synthetic examples, not live account data.
Physical finger gestures, BOOT and readability in the assembled housing still require user confirmation.
Phases 5 and 6 are not complete; no four-hour soak or installed desktop deployment has occurred.

### Phase 4 final build / handoff
Final Ball firmware flashed and hash verified. Both targets build; 250 desktop tests pass after control-floor
alignment to 10%. Explicit screen-off survives disconnect/reconnect and an incoming completion event.
Turning the screen back on restores the same page byte-for-byte. Waiting is confirmed after disconnection.
The final UI fixture run completed all capture/assertion steps successfully.
Retained evidence: dist/windows/validation/ball-20261113-phase4 (ignored by Git).
No installed companion or C6 runtime was replaced.

For physical review, a bounded synthetic-data feeder serves Ball for 30 minutes after the capture checks;
it does not register or control C6, and exits to the waiting screen. Started 2026-11-13 ~21:40 local.
Tool session 6476; Python process pair 84368/98620, created 21:39:53, command tools/validate_ball_ui.py.
Identify again before ending this test for phase 5; never confuse it with CodexMeter.exe.
Pending user check: left/right swipe through all three pages including wrap, short BOOT advance,
readability in the circular housing, page retention while idle. Manual rotated finger tests remain physical
acceptance work, not inferred from transformed framebuffer captures.
Phase 5 coexistence/sleep/soak and phase 6 packaging remain outstanding.

## Phase 4 physical acceptance
User confirmed bidirectional swipe and wrap, short BOOT page advance, readable text, and selected-page
retention while idle. Proceeding to phase 5. Manual rotation framebuffer transforms passed; physical
gesture checks in rotated orientations remain an explicit coverage limitation until tested.

## Phase 5 started
Preparing a real DeviceManager test with both registered hardware identities, shared synthetic snapshots,
10 individual BLE disconnect/reconnect cycles per device, and an uninterrupted-peer ACK deadline of twice
the three-second fixture interval. This is actual BLE transport testing, not device power cycling or host
sleep evidence. No Bluetooth radio reset is used.

### Phase 5 coexistence/reconnect results
Both physical identities connected through the production DeviceManager in one Windows process, receiving
the same synthetic snapshots. Ten actual BLE disconnect/reconnect cycles per display passed (20 total).
Worst reconnection 16.656 seconds; unaffected peer ACK age stayed below 3 seconds throughout (limit 6 seconds
for the three-second fixture publisher). Some deliberately interrupted writes logged ACK timeouts; these
were target-link failures during injected disconnects, recovered within the bound, not healthy-peer failures.
No Bluetooth radio or hardware reset was used. Result passed=true in retained mixed-phase5/results.json.

Stopped the previous bounded Ball fixture after confirming its command/process identity. Gracefully shut down
the installed companion via authenticated IPC for the transport test and restored it afterward. Then backed
up devices.json to retained phase-5 evidence, registered the identity-verified Ball, and launched the full
updated companion from source for live integration tests. Both devices acknowledge real usage/activity.
Targeted Ball screen off/on leaves C6 on and connected; health/heap/RSS collector smoke test passes.
253 full desktop tests pass, including new soak-acceptance tests (coverage, gaps, RSS and device heap limits).

Current runtime is source companion daemon.py, run e7775963a1e04eac8bff6a7a6de30617,
PID 94072, launcher parent 95400, started 2026-11-13 ~21:51 local. Verify identity/time before operations.
Installed dist/windows/CodexMeter.exe and login startup were not replaced; C6 firmware unchanged.
The registry now contains Waveshare C6 and Spotpear Ball. The new Displays panel supports Ball controls.

Prepared tools/observe_mixed_soak.py: read-only, bounded 15-minute warm-up plus four-hour observation,
30-second metrics, heartbeat/process/queue/ACK health, per-device heap/uptime, sleep-gap detection and
first/last 15-minute median acceptance. Stores no task text or transcripts, never restarts anything.
Do not claim a soak: it has NOT started. Three manually coordinated host sleep/resume cycles also remain.
Need user coordination before sleep checks; after they reply, investigate Windows resume events and app
logs, then run the bounded awake soak. No phase-6 package/release candidate is built yet.
Evidence retained under dist/windows/validation/ball-20261113-phase5 (ignored by Git).

## User-authorized acceptance change
User explicitly deferred the sleep/resume cycles and four-hour soak to production and instructed continuation.
Phase 5 is accepted for packaging with these checks NOT RUN, not passed. No monitor/soak is started.
Observed two-display operation, 20 real BLE reconnects, independent controls and 253 automated tests stand.
Rotated finger gestures remain unverified beyond the accepted default orientation. Phase 6 proceeds with
these limitations stated in the documentation and candidate release notes.

## Phase 6 complete — local release candidate
Built and deployed Nuitka onefile Windows 3.12.3.0 at the existing dist/windows/CodexMeter.exe location.
Built matching Ball and C6 factory images; verified each connected full identity before flashing only its
application segment at 0x10000, preserving NVS/settings and existing matching partitions/assets.
Ball advertises firmware 3.12.3.0. Both displays receive live data from the packaged companion.

253 regression tests pass. Packaged self-test passed with Python/source paths removed: GUI including Displays,
WinRT, DPAPI, bundled pricing, subprocess CLI, native tray tests; device listing and live usage passed.
Manually inspected the actual packaged Displays panel through Computer Use. Both rows connected; selected
Ball screen off/on controlled only Ball, confirmed by serial health. Closed panel to tray successfully.
Graceful packaged shutdown and relaunch through the unchanged Windows login shortcut passed with both
devices acknowledged. Current runtime is the standalone executable, not the temporary source daemon.

README now includes three actual Ball example captures and the packaged mixed-display panel. Added safe
board/identity flashing instructions, compatibility table, validation limitations and candidate release notes;
original upstream README link and C6 documentation remain. Public factory images were compiled from source.
No private original full flash, credentials, device logs or runtime diagnostics are in the release bundle.

Retained bundle: dist/releases/windows-c6-2026.11.13.1
Includes executable, Ball/C6 factory images, release/setup notes, changelog/license, manifest and SHA256SUMS.
Rollback executable/old manifest: dist/windows/previous-before-ball-3.12.3.0
Private validation evidence: dist/windows/validation/ball-20261113-phase6 (Git ignored).
All build/compiler/cache output stayed on D:. D: had ~154 GiB headroom; no existing data was moved.

Accepted limitations: sleep/resume cycles and four-hour soak NOT RUN by explicit user decision; rotated
finger gestures and >2 physical displays not certified. No ongoing soak or restart monitor was installed.
Implementation/deployment/local candidate are complete under that revised acceptance. Changes remain
uncommitted and no public GitHub release/push was performed; those follow separate release authorization.
Suggested commit groups: (1) identity/desktop multi-display and transport tests; (2) Ball hardware/UI and
shared screen policy; (3) validation tools/requirements evidence; (4) version/build/docs/screenshots.
Final post-deployment framebuffer review passed on both boards: quota/reset and all three task counts agree; C6 theme and USB indicator retained. Plan moved as a whole into 3_done after its earlier directory lock cleared. Public publication remains a separate action.

## Publication handoff — 2026-11-13
User authorized all Ball/multi-display commits, push and public release with both firmware images.
Fresh regression run: 253 passed in 11.24 seconds. All three retained binary hashes match the build manifest.
Desktop: 7c135b5. Ball firmware/build/flash: 8476de4. Validation tooling is committed separately.
README includes the user's cropped physical Ball photo; the original photograph is unchanged.
Raw probe observations and build/runtime evidence remain ignored. No additional hardware soak is claimed.
Release documentation is finalized for windows-c6-2026.11.13.1 (Windows 3.12.3.0).
