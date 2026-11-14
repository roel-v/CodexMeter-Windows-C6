# Repository rename

On 2026-11-14, the project name changes from CodexMeter-Windows-C6 to
CodexMeter-Companion, with main as the maintained branch.
Repository: https://github.com/roel-v/CodexMeter-Companion
GitHub repository ID: 1432451927.

Release checks use the repository-ID API endpoint, so future repository renames
will not affect discovery. The updater continues to reject unexpected redirects.
Older packaged executables still contain the previous name-based endpoint and
reject GitHub redirects. Install a new build to restore their update checks after
renaming; normal display operation is unaffected. The owner confirmed that no
external-user migration or transition release is needed.

The local checkout is named CodexMeter-Companion. Update local origin, startup
shortcuts and editable Python references to that checkout. The parent project
folder also contains enclosure designs and backups and is not a Git repository.
Keep upstream pointing to tomatoeggs/CodexMeter.

The app remains CodexMeter.exe, the Python package remains codexmeter and settings
stay in .codexmeter. Hardware identities, firmware filenames, build storage and
historical windows-c6 release tags remain stable. No firmware flash is required.
Old repository URLs in historical records are retained as history.

GitHub preserves web and Git redirects after renaming. Do not reuse the old
repository name for a different repository, as that would remove the redirects.
https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository
