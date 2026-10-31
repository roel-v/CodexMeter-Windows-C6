"""Read near-real-time token activity from local Codex session events."""

from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class _SessionFileState:
    inode: int
    offset: int = 0
    previous_total: int | None = None
    daily_tokens: dict[dt.date, int] = field(default_factory=dict)
    observed_dates: set[dt.date] = field(default_factory=set)
    replay_until: dt.datetime | None = None
    has_history_base: bool = False
    uses_usage_records: bool = False
    usage_records: dict[str, tuple[dt.date, int]] = field(default_factory=dict)
    turn_models: dict[str, str] = field(default_factory=dict)
    current_model: str | None = None
    detailed_records: dict[str, dict] = field(default_factory=dict)


class LocalTokenUsageReader:
    """Sum local daily request usage, with cumulative deltas for older logs."""

    def __init__(self, codex_home: Path | None = None) -> None:
        configured_home = os.environ.get("CODEX_HOME")
        self.codex_home = Path(
            codex_home
            if codex_home is not None
            else configured_home or Path.home() / ".codex"
        )
        self.sessions_root = self.codex_home / "sessions"
        self._window: tuple[dt.date, dt.date, dt.tzinfo] | None = None
        self._states: dict[Path, _SessionFileState] = {}

    def read_today_tokens(self, now: dt.datetime | None = None) -> int | None:
        daily = self.read_daily_tokens(now, days=1)
        return next(iter(daily.values())) if daily else None

    def read_daily_tokens(
        self, now: dt.datetime | None = None, days: int = 7
    ) -> dict[dt.date, int] | None:
        """Return recorded local usage for consecutive calendar days, inclusive.

        Missing dates within an available window contain zero recorded tokens.
        None means no compatible usage was found, not zero account usage.
        """
        if days < 1:
            raise ValueError("days must be positive")
        local_now = now if now is not None else dt.datetime.now().astimezone()
        if local_now.tzinfo is None:
            local_now = local_now.astimezone()
        target_date = local_now.date()
        first_date = target_date - dt.timedelta(days=days - 1)
        window = (first_date, target_date, local_now.tzinfo)
        if window != self._window:
            self._window = window
            self._states.clear()

        roots = (self.sessions_root, self.codex_home / "archived_sessions")
        if not any(root.is_dir() for root in roots):
            return None

        day_start = dt.datetime.combine(
            first_date,
            dt.time.min,
            tzinfo=local_now.tzinfo,
        ).timestamp()
        candidates: set[Path] = set()
        try:
            paths = (path for root in roots for path in root.rglob("*.jsonl"))
            for path in paths:
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if stat.st_mtime < day_start:
                    continue
                candidates.add(path)
                self._scan_file(path, stat.st_ino, first_date, target_date, local_now.tzinfo)
        except OSError:
            return None

        for path in tuple(self._states):
            if path not in candidates:
                del self._states[path]

        observed = [state for state in self._states.values() if state.observed_dates]
        if not observed:
            return None
        totals = {first_date + dt.timedelta(days=i): 0 for i in range(days)}
        # A response can appear in more than one rollout after a fork/resume.
        records: dict[str, tuple[dt.date, int]] = {}
        for state in observed:
            for day, tokens in state.daily_tokens.items():
                totals[day] += tokens
            records.update(state.usage_records)
        for day, tokens in records.values():
            totals[day] += tokens
        return totals

    def _scan_file(
        self,
        path: Path,
        inode: int,
        first_date: dt.date,
        target_date: dt.date,
        timezone: dt.tzinfo,
    ) -> None:
        state = self._states.get(path)
        try:
            size = path.stat().st_size
        except OSError:
            return
        if state is None or state.inode != inode or size < state.offset:
            state = _SessionFileState(inode=inode)
            self._states[path] = state

        try:
            with path.open(encoding="utf-8") as handle:
                handle.seek(state.offset)
                while True:
                    line_start = handle.tell()
                    line = handle.readline()
                    if not line:
                        break
                    if not line.endswith("\n"):
                        handle.seek(line_start)
                        break
                    state.offset = handle.tell()
                    self._capture_session_meta(line, state)
                    if '"turn_context"' in line:
                        self._capture_turn(line, state)
                    if '"token_usage_record"' in line:
                        self._apply_usage_record(line, state, first_date, target_date, timezone)
                    if '"token_count"' not in line:
                        continue
                    self._apply_token_event(line, state, first_date, target_date, timezone)
        except OSError:
            return

    @staticmethod
    def _capture_turn(line, state):
        try:
            row = json.loads(line)
            payload = row.get("payload", {})
            if row.get("type") == "turn_context":
                model = payload.get("model")
                state.current_model = model if isinstance(model, str) else None
                if isinstance(payload.get("turn_id"), str) and state.current_model:
                    state.turn_models[payload["turn_id"]] = state.current_model
        except (ValueError, TypeError, AttributeError):
            pass

    def read_breakdown(self, daily, pricing):
        """Reuse this scan's per-response records; never reattribute replayed history."""
        from decimal import Decimal
        records = {}
        for state in self._states.values():
            for key, record in state.detailed_records.items():
                if key not in records or (not records[key].get("model") and record.get("model")):
                    records[key] = record
        revisions = pricing.revisions()
        def summarize(days):
            result = {"tokens": [0, 0, 0], "cost_micro_usd": [0, 0, 0],
                      "unpriced_tokens": 0, "unknown_tokens": 0, "cache_write_tokens": 0,
                      "total_tokens": sum(daily[d] for d in days), "models": {}, "basis": "Standard API rates"}
            costs = [Decimal(0), Decimal(0), Decimal(0)]
            accounted = 0
            for record in records.values():
                if record["day"] not in days:
                    continue
                accounted += record["total"]
                model = record.get("model") or "Unknown model"
                entry = result["models"].setdefault(model, {"tokens": 0, "cost_usd": 0, "unpriced_tokens": 0, "reasons": []})
                entry["tokens"] += record["total"]
                if record.get("tokens") is None:
                    result["unknown_tokens"] += record["total"]
                    estimate, reason = None, "Token breakdown unavailable"
                else:
                    result["tokens"] = [a + b for a, b in zip(result["tokens"], record["tokens"])]
                    result["cache_write_tokens"] += record.get("cache_write", 0)
                    estimate, reason = pricing.cost(record, revisions)
                if estimate is None:
                    result["unpriced_tokens"] += record["total"]
                    entry["unpriced_tokens"] += record["total"]
                    if reason not in entry["reasons"]:
                        entry["reasons"].append(reason)
                else:
                    costs = [a + b for a, b in zip(costs, estimate)]
                    entry["cost_usd"] += float(sum(estimate) / 1_000_000)
            legacy = max(0, result["total_tokens"] - accounted)
            result["unknown_tokens"] += legacy
            result["unpriced_tokens"] += legacy
            result["cost_micro_usd"] = [int(v.to_integral_value()) for v in costs]
            return result
        return {"today": summarize({max(daily)}), "week": summarize(set(daily))}

    @staticmethod
    def _capture_session_meta(line: str, state: _SessionFileState) -> None:
        if '"session_meta"' not in line:
            return
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                return
            payload = row.get("payload")
            timestamp = row.get("timestamp")
            if row.get("type") != "session_meta" or not isinstance(payload, dict):
                return
            state.has_history_base = isinstance(payload.get("history_base"), dict)
            # Paginated rollouts reference history instead of replaying it.
            # Their first real request may arrive well after the file starts.
            if payload.get("history_mode") == "paginated":
                return
            if not payload.get("forked_from_id") or not isinstance(timestamp, str):
                return
            started_at = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=dt.timezone.utc)
        except (json.JSONDecodeError, TypeError, ValueError):
            return
        # Forked sessions replay the parent's token_count history immediately
        # after session_meta. Treat that burst as a baseline, not fresh usage.
        state.replay_until = started_at + dt.timedelta(seconds=1)

    @staticmethod
    def _apply_usage_record(
        line: str,
        state: _SessionFileState,
        first_date: dt.date,
        target_date: dt.date,
        timezone: dt.tzinfo,
    ) -> None:
        try:
            row = json.loads(line)
            if not isinstance(row, dict) or row.get("type") != "token_usage_record":
                return
            payload = row.get("payload")
            if not isinstance(payload, dict):
                return
            usage = payload.get("usage")
            response_id = payload.get("response_id")
            if (
                not isinstance(usage, dict)
                or not isinstance(response_id, str)
                or not response_id
            ):
                return
            total = usage.get("total_tokens")
            if isinstance(total, bool) or not isinstance(total, int) or total < 0:
                return
            timestamp = row.get("timestamp")
            if not isinstance(timestamp, str):
                return
            event_time = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=dt.timezone.utc)
        except (json.JSONDecodeError, TypeError, ValueError):
            return

        # New Codex emits a per-response record before its token_count snapshot.
        # Keep legacy usage before the transition, then stop counting snapshots:
        # they include inherited history and omit some compaction requests.
        state.uses_usage_records = True
        if state.replay_until is not None and event_time <= state.replay_until:
            return
        event_date = event_time.astimezone(timezone).date()
        if first_date <= event_date <= target_date:
            state.usage_records[response_id] = (event_date, total)
            state.observed_dates.add(event_date)
            counts = [usage.get(k) for k in ("input_tokens", "cached_input_tokens", "output_tokens")]
            valid = all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in counts)
            tokens = None
            if valid and counts[1] <= counts[0] and counts[0] + counts[2] == total:
                tokens = [counts[0] - counts[1], counts[1], counts[2]]
            turn_id = payload.get("turn_id")
            # A known turn id must not inherit a different turn's selected model.
            model = state.turn_models.get(turn_id) if turn_id else state.current_model
            cache_write = usage.get("cache_write_input_tokens", 0)
            if not isinstance(cache_write, int) or isinstance(cache_write, bool) or cache_write < 0:
                tokens = None
                cache_write = 0
            state.detailed_records[response_id] = {
                "time": event_time, "day": event_date, "total": total, "tokens": tokens,
                "model": model, "input": counts[0] if valid else 0, "cache_write": cache_write}

    @staticmethod
    def _apply_token_event(
        line: str,
        state: _SessionFileState,
        first_date: dt.date,
        target_date: dt.date,
        timezone: dt.tzinfo,
    ) -> None:
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                return
            payload = row.get("payload")
            if row.get("type") != "event_msg" or not isinstance(payload, dict):
                return
            if payload.get("type") != "token_count":
                return
            info = payload.get("info")
            if not isinstance(info, dict):
                return
            total_usage = info.get("total_token_usage")
            if not isinstance(total_usage, dict):
                return
            current_total = total_usage.get("total_tokens")
            timestamp = row.get("timestamp")
            if (
                isinstance(current_total, bool)
                or not isinstance(current_total, int)
                or current_total < 0
            ):
                return
            if not isinstance(timestamp, str):
                return
            event_time = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=dt.timezone.utc)
        except (json.JSONDecodeError, TypeError, ValueError):
            return

        is_replayed_baseline = (
            state.replay_until is not None and event_time <= state.replay_until
        )
        event_date = event_time.astimezone(timezone).date()
        if (
            not state.uses_usage_records
            and first_date <= event_date <= target_date
            and not is_replayed_baseline
        ):
            if state.previous_total is None and state.has_history_base:
                last_usage = info.get("last_token_usage")
                last_total = (
                    last_usage.get("total_tokens")
                    if isinstance(last_usage, dict)
                    else None
                )
                # Never attribute an inherited cumulative total to today, even
                # when an older paginated writer omits per-response records.
                delta = (
                    min(current_total, last_total)
                    if isinstance(last_total, int) and not isinstance(last_total, bool)
                    else 0
                )
            elif state.previous_total is None or current_total < state.previous_total:
                delta = current_total
            else:
                delta = current_total - state.previous_total
            state.daily_tokens[event_date] = state.daily_tokens.get(event_date, 0) + max(0, delta)
            state.observed_dates.add(event_date)
        state.previous_total = current_total
