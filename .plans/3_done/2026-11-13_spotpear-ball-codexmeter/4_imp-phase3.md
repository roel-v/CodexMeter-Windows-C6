# Phase 3 — production Ball board support

Requirements: R1, R4, R12, R15, R17, R20–R24. Depends on phase 1.

1. Add an explicit Spotpear Ball v2 BOX PlatformIO target: S3, 16 MB flash, 8 MB PSRAM, dedicated partitions
   sized from the actual build. Do not reuse the Waveshare S3 pin map or implicit non-C6 fallback.
2. Isolate board-specific panel, geometry, power, touch and sensor initialization from main.cpp/config.h.
   Preserve existing C6 and Waveshare target behavior. Share the application/protocol layer rather than copying it.
3. Bring up GC9A01 240x240 SPI and inverted backlight, CST816D input and BOOT using probe-confirmed pins.
   Match panel command polarity, not a different library's inversion boolean: Arduino_GC9A01 with ips=true
   uses invertDisplay(false) for INVON. Require physically correct RGB bars/black background before UI work.
   Allocate DMA-compatible transfer buffers; keep large UI allocations in PSRAM only where supported.
4. Implement manual rotation with matching touch transform, brightness and explicit screen-off semantics.
   Unsupported AXP2101/QMI8658 operations must never execute on Ball. Advertise only verified capabilities.
5. Add identity metadata and current compatible BLE payload handling. Show a minimal circle-safe waiting screen
   from boot, before companion data; connection alone does not clear the stale-data/waiting state.
6. Flash only the identity-verified new Ball with original recovery backup intact. Verify write hash and boot.

Exit: Ball/C6 build success; affected existing targets compile. Waiting, BLE identity/data, touch after idle,
brightness/rotation/screen-off controls and boot recovery path work. No production claim based on probe alone.
Document memory allocation/free-heap baseline and the correct board-specific flash offsets.
