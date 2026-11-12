"""Read-only GitHub release discovery. Never fetch or execute release assets."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .persistence import atomic_write_json
from .settings import APP_DIR

REPOSITORY = "roel-v/CodexMeter-Windows-C6"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
# Advance this baseline when cutting a new dated Windows/C6 bundle.
CURRENT_RELEASE = "windows-c6-2026.11.01"
APP_VERSION = "3.12.2.6"
_LOCK = threading.RLock()


def release_key(tag):
    match = re.fullmatch(r"windows-c6-(\d{4})\.(\d{2})\.(\d{2})(?:\.(\d+))?", tag or "")
    if not match:
        raise ValueError("Unrecognized Windows/C6 release tag")
    year, month, day = map(int, match.groups()[:3])
    dt.date(year, month, day)
    return year, month, day, int(match[4] or 0)


def fetch_release():
    request = urllib.request.Request(API_URL, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "CodexMeter-release-check/1"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.url != API_URL:
                raise ValueError("Unexpected release API redirect")
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError("Release metadata is too large")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


class UpdateStore:
    def __init__(self, path: Path = APP_DIR / "updates.json", current=CURRENT_RELEASE):
        self.path = path
        self.current = current

    @property
    def preferences_path(self):
        return self.path.with_suffix(".preferences.json")

    def automatic_enabled(self):
        try:
            preferences = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            return isinstance(preferences, dict) and preferences.get("automatic_checks") is True
        except FileNotFoundError:
            return True
        except (OSError, ValueError):
            # A broken preference file must not silently re-enable network checks.
            return False

    def set_automatic(self, enabled: bool):
        # Separate from cached results so an in-flight request cannot overwrite
        # the user's choice, or hold the UI behind the network request lock.
        atomic_write_json(self.preferences_path, {"automatic_checks": bool(enabled)})

    def display_message(self):
        if not self.automatic_enabled():
            return "Automatic GitHub release checks and notifications are off. Check now still makes a manual request."
        return self.status()["message"]

    def status(self):
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(state, dict):
                return state
        except (OSError, ValueError):
            pass
        return {"state": "unchecked", "message": "Releases have not been checked yet."}

    def check(self, *, force=False, fetch=fetch_release, now=None):
        now = time.time() if now is None else now
        with _LOCK:
            if not force and not self.automatic_enabled():
                return {"state": "disabled", "message": self.display_message()}
            previous = self.status()
            interval = 3600 if previous.get("state") == "error" else 86400
            if (not force and previous.get("current") == self.current
                    and 0 <= now - previous.get("checked_at", 0) < interval):
                return previous
            state = {"current": self.current, "checked_at": now,
                     "notified_tag": previous.get("notified_tag")}
            try:
                release = fetch()
                if release is None:
                    state.update(state="current", message="No published stable release is available.")
                else:
                    if not isinstance(release, dict) or release.get("draft") is not False or release.get("prerelease") is not False:
                        raise ValueError("Expected a published stable release")
                    tag = release["tag_name"]
                    newer = release_key(tag) > release_key(self.current)
                    state.update(state="available" if newer else "current", tag=tag,
                                 message=(f"A newer Windows/C6 release is available: {tag}."
                                          if newer else "No newer Windows/C6 release is available."))
            except Exception as exc:
                state.update(state="error", message=f"Could not check GitHub releases. Try again later. ({type(exc).__name__})")
            atomic_write_json(self.path, state)
            return state

    def notify_once(self, desktop):
        with _LOCK:
            if not self.automatic_enabled():
                return
            state = self.status()
            if state.get("state") == "available" and state.get("notified_tag") != state.get("tag"):
                desktop.commands.put(("update_available", state["message"]))
                state["notified_tag"] = state["tag"]
                atomic_write_json(self.path, state)

    def release_url(self):
        state = self.status()
        if state.get("state") == "available":
            tag = state.get("tag")
            try:
                release_key(tag)
                return RELEASES_URL + "/tag/" + tag
            except (ValueError, TypeError):
                pass
        return RELEASES_URL


async def update_monitor_loop(stop_event, desktop=None):
    store = UpdateStore()
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(store.check)
            if desktop is not None:
                await asyncio.to_thread(store.notify_once, desktop)
        except Exception:
            logging.exception("Release check unavailable; bridge continues")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3600)
        except asyncio.TimeoutError:
            pass
