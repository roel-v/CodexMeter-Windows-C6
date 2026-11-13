# Phase 4 — native round application UI

Requirements: R5–R19. Depends on phase 3; layouts already accepted as prototypes.

1. Implement Quota/tasks, Today and 7 days as peer pages using the approved native-size layouts and shared
   formatting/accounting. Use embedded fonts meeting readability targets; Segoe UI mockups are not font assets.
2. Preserve all required totals, three token categories and per-category API estimates. Show unknown, stale and
   partial/unpriced states truthfully. No second model-pricing engine or independent period computation on device.
3. Implement overall-plan swipe/BOOT rules, wrap order, page retention and per-device manual orientation.
   Taps do not open a hidden period selector. Keep one transition per gesture and reject invalid coordinates.
4. Reuse C6 waiting/screen policy and completion-event lifecycle/timing. Adapt alert text to circular bounds,
   preserve selected page and explicit screen-off intent, and do not mark chats read by showing an alert.
5. Generalize screenshot/capture dimensions for 240x240 without changing 480x480 C6 output. Mark fixtures as
   examples. Validate fonts and circle margins on actual hardware, not only the PNG preview.

Exit: physical review of all pages and orientations; 0/100%, reset boundary/expiry, missing data, 999 tasks,
large token/cost values, partial rates and long alert text remain readable. C6 semantic tests still pass.
Exercise waiting/reconnect and an alert from every page; verify selected page returns afterward.
