import datetime as dt
import json
import os

from codexmeter.local_usage import LocalTokenUsageReader


TZ = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime(2026, 7, 17, 12, 0, tzinfo=TZ)


def token_event(timestamp: str, total: int, last: int | None = None) -> str:
    info = {"total_token_usage": {"total_tokens": total}}
    if last is not None:
        info["last_token_usage"] = {"total_tokens": last}
    return json.dumps(
        {
            "timestamp": timestamp,
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": info,
            },
        },
        separators=(",", ":"),
    )


def session_meta(timestamp: str, forked: bool = False, paginated: bool = False) -> str:
    payload = {"id": "current"}
    if forked:
        payload["forked_from_id"] = "parent"
    if paginated:
        payload["history_mode"] = "paginated"
        payload["history_base"] = {"thread_id": "parent", "end_ordinal_exclusive": 100}
    return json.dumps(
        {"timestamp": timestamp, "type": "session_meta", "payload": payload},
        separators=(",", ":"),
    )


def test_local_usage_sums_cumulative_deltas_and_ignores_duplicates(tmp_path):
    sessions = tmp_path / "sessions" / "2026" / "07" / "17"
    sessions.mkdir(parents=True)
    rollout = sessions / "rollout.jsonl"
    rollout.write_text(
        "\n".join(
            [
                token_event("2026-07-16T15:59:00Z", 100),
                token_event("2026-07-16T16:00:00Z", 150),
                token_event("2026-07-16T16:01:00Z", 150),
                token_event("2026-07-16T16:02:00Z", 220),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    os.utime(rollout, (NOW.timestamp(), NOW.timestamp()))

    reader = LocalTokenUsageReader(tmp_path)

    assert reader.read_today_tokens(NOW) == 120

    with rollout.open("a", encoding="utf-8") as handle:
        handle.write(token_event("2026-07-17T02:00:00Z", 260) + "\n")
    os.utime(rollout, (NOW.timestamp(), NOW.timestamp()))

    assert reader.read_today_tokens(NOW) == 160


def test_local_usage_returns_none_without_compatible_events(tmp_path):
    (tmp_path / "sessions").mkdir()

    assert LocalTokenUsageReader(tmp_path).read_today_tokens(NOW) is None


def test_local_usage_treats_forked_history_replay_as_baseline(tmp_path):
    sessions = tmp_path / "sessions" / "2026" / "07" / "17"
    sessions.mkdir(parents=True)
    rollout = sessions / "forked.jsonl"
    rollout.write_text(
        "\n".join(
            [
                session_meta("2026-07-16T16:00:00Z", forked=True),
                token_event("2026-07-16T16:00:00.100Z", 100),
                token_event("2026-07-16T16:00:00.200Z", 200),
                token_event("2026-07-16T16:00:02Z", 230),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    os.utime(rollout, (NOW.timestamp(), NOW.timestamp()))

    assert LocalTokenUsageReader(tmp_path).read_today_tokens(NOW) == 30


def usage_record(timestamp: str, total: int, response_id: str = "response-1") -> str:
    # Whitespace is intentional: JSON formatting must not affect detection.
    return json.dumps({
        "timestamp": timestamp,
        "type": "token_usage_record",
        "payload": {"response_id": response_id, "usage": {"total_tokens": total}},
    })


def write_rollout(tmp_path, name, rows):
    sessions = tmp_path / "sessions"
    sessions.mkdir(exist_ok=True)
    rollout = sessions / name
    rollout.write_text("\n".join(rows) + "\n", encoding="utf-8")
    os.utime(rollout, (NOW.timestamp(), NOW.timestamp()))
    return rollout


def test_paginated_resume_counts_requests_not_inherited_270m(tmp_path):
    write_rollout(tmp_path, "resume.jsonl", [
        session_meta("2026-07-17T01:46:03Z", forked=True, paginated=True),
        usage_record("2026-07-17T01:46:26Z", 140251),
        token_event("2026-07-17T01:46:26Z", 270676266, last=140251),
        token_event("2026-07-17T01:47:00Z", 270676266, last=140251),
        usage_record("2026-07-17T01:48:00Z", 200, "response-2"),
        token_event("2026-07-17T01:48:00Z", 270676466, last=200),
    ])
    assert LocalTokenUsageReader(tmp_path).read_today_tokens(NOW) == 140451


def test_usage_records_include_compaction_and_deduplicate_across_rollouts(tmp_path):
    rows = [
        usage_record("2026-07-17T01:00:00Z", 100),
        token_event("2026-07-17T01:00:00Z", 100),
        usage_record("2026-07-17T01:01:00Z", 40, "compact-response"),
        token_event("2026-07-17T01:01:00Z", 100),
    ]
    write_rollout(tmp_path, "original.jsonl", rows)
    write_rollout(tmp_path, "copy.jsonl", rows + [rows[0]])
    assert LocalTokenUsageReader(tmp_path).read_today_tokens(NOW) == 140


def test_usage_records_preserve_legacy_prefix_when_codex_upgrades(tmp_path):
    write_rollout(tmp_path, "mixed.jsonl", [
        token_event("2026-07-17T01:00:00Z", 100),
        usage_record("2026-07-17T01:01:00Z", 40),
        token_event("2026-07-17T01:01:00Z", 140),
    ])
    assert LocalTokenUsageReader(tmp_path).read_today_tokens(NOW) == 140


def test_usage_records_incremental_partial_line_and_day_rollover(tmp_path):
    path = write_rollout(tmp_path, "requests.jsonl", [
        usage_record("2026-07-16T15:59:59Z", 50, "yesterday"),
        usage_record("2026-07-16T16:00:00Z", 100),
    ])
    reader = LocalTokenUsageReader(tmp_path)
    assert reader.read_today_tokens(NOW) == 100
    assert reader.read_today_tokens(NOW) == 100
    with path.open("a") as handle:
        handle.write(usage_record("2026-07-17T01:00:00Z", 40, "response-2"))
    assert reader.read_today_tokens(NOW) == 100
    with path.open("a") as handle:
        handle.write("\n")
    assert reader.read_today_tokens(NOW) == 140
    with path.open("a") as handle:
        handle.write(usage_record("2026-07-17T16:00:00Z", 70, "tomorrow") + "\n")
    tomorrow = NOW + dt.timedelta(days=1)
    os.utime(path, (tomorrow.timestamp(), tomorrow.timestamp()))
    assert reader.read_today_tokens(tomorrow) == 70


def test_paginated_fallback_without_records_excludes_history_and_counts_fast_request(tmp_path):
    write_rollout(tmp_path, "fallback.jsonl", [
        session_meta("2026-07-17T01:00:00Z", forked=True, paginated=True),
        token_event("2026-07-17T01:00:00.100Z", 1000100, last=100),
        token_event("2026-07-17T01:01:00Z", 1000140, last=40),
    ])
    assert LocalTokenUsageReader(tmp_path).read_today_tokens(NOW) == 140


def test_paginated_fallback_missing_last_usage_does_not_count_history(tmp_path):
    write_rollout(tmp_path, "fallback.jsonl", [
        session_meta("2026-07-17T01:00:00Z", paginated=True),
        token_event("2026-07-17T01:01:00Z", 1000000),
        token_event("2026-07-17T01:02:00Z", 1000040),
    ])
    assert LocalTokenUsageReader(tmp_path).read_today_tokens(NOW) == 40


def test_invalid_usage_records_do_not_disable_legacy_counting(tmp_path):
    write_rollout(tmp_path, "invalid.jsonl", [
        '{"type":"token_usage_record",',
        usage_record("bad-timestamp", 40),
        usage_record("2026-07-17T01:00:00Z", True),
        usage_record("2026-07-17T01:00:00Z", -20),
        usage_record("2026-07-17T01:00:00Z", 40, ""),
        token_event("2026-07-17T01:00:00Z", 100),
    ])
    assert LocalTokenUsageReader(tmp_path).read_today_tokens(NOW) == 100


def test_week_uses_local_midnight_and_includes_exactly_seven_dates(tmp_path):
    write_rollout(tmp_path, "week.jsonl", [
        usage_record("2026-07-10T15:59:59Z", 999, "outside"),
        usage_record("2026-07-10T16:00:00Z", 10, "first"),
        usage_record("2026-07-16T15:59:59Z", 20, "yesterday"),
        usage_record("2026-07-16T16:00:00Z", 30, "today"),
    ])
    reader = LocalTokenUsageReader(tmp_path)
    daily = reader.read_daily_tokens(NOW)
    assert len(daily) == 7
    assert daily[dt.date(2026, 7, 11)] == 10
    assert daily[dt.date(2026, 7, 16)] == 20
    assert daily[NOW.date()] == 30
    assert daily[dt.date(2026, 7, 12)] == 0
    assert sum(daily.values()) == 60
    assert reader.read_daily_tokens(NOW) == daily
    # Next midnight the oldest day drops out; today's zero remains explicit.
    tomorrow = NOW + dt.timedelta(days=1)
    rolled = reader.read_daily_tokens(tomorrow)
    assert sum(rolled.values()) == 50
    assert rolled[tomorrow.date()] == 0


def test_week_keeps_archived_usage_and_deduplicates_moved_rollout(tmp_path):
    rows = [usage_record("2026-07-16T01:00:00Z", 100)]
    path = write_rollout(tmp_path, "original.jsonl", rows)
    archived = tmp_path / "archived_sessions"
    archived.mkdir()
    copy = archived / "archived.jsonl"
    copy.write_text(path.read_text())
    reader = LocalTokenUsageReader(tmp_path)
    assert sum(reader.read_daily_tokens(NOW).values()) == 100
    path.unlink()
    assert sum(reader.read_daily_tokens(NOW).values()) == 100


def test_week_legacy_cumulative_baseline_crosses_date_boundary(tmp_path):
    write_rollout(tmp_path, "legacy.jsonl", [
        token_event("2026-07-10T15:59:59Z", 1000),
        token_event("2026-07-10T16:00:00Z", 1100),
        token_event("2026-07-16T16:00:00Z", 1140),
    ])
    daily = LocalTokenUsageReader(tmp_path).read_daily_tokens(NOW)
    assert daily[dt.date(2026, 7, 11)] == 100
    assert daily[NOW.date()] == 40
    assert sum(daily.values()) == 140


def test_week_pagination_excludes_inherited_history_from_past_days(tmp_path):
    write_rollout(tmp_path, "past-resume.jsonl", [
        session_meta("2026-07-15T01:00:00Z", paginated=True),
        usage_record("2026-07-15T01:01:00Z", 100),
        token_event("2026-07-15T01:01:00Z", 270000100),
        usage_record("2026-07-17T01:00:00Z", 40, "new"),
        token_event("2026-07-17T01:00:00Z", 270000140),
    ])
    daily = LocalTokenUsageReader(tmp_path).read_daily_tokens(NOW)
    assert daily[dt.date(2026, 7, 15)] == 100
    assert daily[NOW.date()] == 40
    assert sum(daily.values()) == 140
