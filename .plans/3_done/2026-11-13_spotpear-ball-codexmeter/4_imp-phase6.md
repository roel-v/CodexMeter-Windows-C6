# Phase 6 — packaging and release candidate

Requirements: R16, R21, R24 and all acceptance evidence. Depends on phase 5 acceptance.

User exception (2026-11-13): proceed with packaging; sleep/resume and soak checks are deferred to production.
They must remain explicitly unverified in release notes.

1. Check D: headroom; explicitly configure Nuitka/PlatformIO/cache/temp outputs on D:. Build standalone Windows
   executable and board-specific firmware. Retain distributable bundles on E:; keep logs/build output out of Git.
2. Test the packaged executable, discovery, two-display updates, settings migration and shutdown. Preserve existing
   login-startup behavior; deploying/replacing the user's installed app is an explicit implementation step.
3. Document supported models, tested adapter/count, pairing, independent controls, legacy compatibility and genuine
   incompatibility behavior. Include safe board/identity checks, offsets and recovery instructions for public builds.
4. Add actual Ball three-page captures and mixed-device UI examples to README; identify example values. Update
   CHANGELOG.txt by date. Keep the original README link and existing C6 documentation intact.
5. Prepare Windows executable, Ball firmware, checksums and release notes. Include C6 firmware if shared code
   changed it; otherwise clearly link the tested existing C6 release. Never upload original full-flash backups,
   private device logs, provisioning data or prototype diagnostic images as production firmware.
6. Group commits by implemented phase/concern; document versions, validation and deviations in
   5_post-implementation-notes.md. Commit/push/publication follow the user's release authorization, not this plan.

Exit: reproducible release candidate with matching versions/checksums, compatibility matrix and evidence links.
Public release and installed-device deployment are not represented as completed merely because artifacts build.
