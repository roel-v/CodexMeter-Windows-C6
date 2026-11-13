# Phase 5 — coexistence, fault isolation and sustained run

Requirements: R2–R4, R6–R11, R17–R23. Depends on phases 2 and 4.

1. One Windows process drives C6 and Ball simultaneously from the same snapshot. Compare quota, task counts,
   periods and cost totals; verify aliases, compatibility status and independent page/settings behavior.
2. Disconnect/reconnect each display 10 times with the other left connected. Test companion exit/relaunch and
   three host sleep/resume cycles. User-driven power/sleep actions are coordinated without interrupting unrelated
   work. Reconnect must succeed within 60 seconds after the device/adapter is available and advertising.
3. Connected healthy devices must continue acknowledging updates within two configured update intervals while
   the other fails. Disconnected devices show waiting according to the existing stale threshold. Restore current
   state and settings after reconnect; never replay expired completion notifications.
4. Run a bounded 4-hour two-display soak after a 15-minute warm-up, with normal refreshes and controlled alert
   fixtures. Record host RSS, per-device free heap/largest block, resets, heartbeats, queue depth and delivery errors.
   No crashes, unexpected resets, hung workers, unbounded queues or unrecovered disconnects are acceptable.
   Compare medians in first/last 15-minute windows: host RSS growth <=max(20 MiB,10% baseline), device free-heap
   loss <=max(8 KiB,5% baseline). Investigate failures and trends before changing limits or declaring success.
5. Automated transport tests cover at least four identities, including repeated models and duplicate names,
   malformed identity, unsupported protocol and delayed/missing acknowledgement. State explicitly that physical
   Bluetooth capacity is certified only for the two tested displays/adapter, not four simulated identities.

Exit: retain compact dated results and gaps, all failures resolved or explicitly scoped out without violating
requirements. Do not call time spent with the PC asleep a completed soak. Do not add restart machinery.
Stop the test after the bounded interval; no indefinite monitoring promise. Record physical vs simulated evidence.
