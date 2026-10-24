import json
import sqlite3

import pytest

from codexmeter.chat_activity import ChatActivity, apply_change, count_chats, read_inventory


def snapshot(status="idle", unread=False, **extra):
    return {"type": "snapshot", "revision": 1, "conversationState": {
        "threadRuntimeStatus": {"type": status, "activeFlags": []},
        "hasUnreadTurn": unread, "source": "vscode", "parentThreadId": None,
        "turns": [{"text": "private chat content"}], **extra}}


@pytest.mark.parametrize("flag", ["waitingOnApproval", "waitingOnUserInput"])
def test_waiting_running_done_transitions(flag):
    states = {}
    apply_change(states, "a", snapshot("active"))
    assert count_chats({"a"}, {"a"}, states) == (1, 0, 0)
    apply_change(states, "a", {"type": "patches", "baseRevision": 1, "revision": 2,
        "patches": [{"op": "add", "path": ["threadRuntimeStatus", "activeFlags", 0], "value": flag}]})
    assert count_chats({"a"}, {"a"}, states) == (0, 1, 0)
    apply_change(states, "a", {"type": "patches", "baseRevision": 2, "revision": 3,
        "patches": [{"op": "replace", "path": ["threadRuntimeStatus"], "value": {"type": "idle"}},
                    {"op": "replace", "path": ["hasUnreadTurn"], "value": True}]})
    assert count_chats({"a"}, {"a"}, states) == (0, 0, 1)
    apply_change(states, "a", snapshot(unread=False))
    assert count_chats({"a"}, {"a"}, states) == (0, 0, 0)


def test_filter_archives_subagents_and_discard_text():
    states = {}
    apply_change(states, "root", snapshot("active"))
    apply_change(states, "child", snapshot("active", parentThreadId="root"))
    apply_change(states, "archived", snapshot("active"))
    assert count_chats({"root", "child"}, {"child", "archived"}, states) == (1, 0, 0)
    assert "turns" not in states["root"]["state"]
    apply_change(states, "root", {"type": "patches", "baseRevision": 1, "revision": 2,
        "patches": [{"op": "replace", "path": ["turns", 0, "text"], "value": "more private text"}]})
    assert "private" not in json.dumps(states)


def test_revision_gap_is_not_silently_counted():
    states = {}
    apply_change(states, "a", snapshot("active"))
    with pytest.raises(ValueError, match="revision gap"):
        apply_change(states, "a", {"type": "patches", "baseRevision": 2, "revision": 3, "patches": []})


def test_inventory_only_completed_unread_roots(tmp_path):
    with sqlite3.connect(tmp_path / "state_5.sqlite") as db:
        db.executescript("CREATE TABLE threads(id,archived,source); CREATE TABLE thread_spawn_edges(child_thread_id);")
        db.executemany("INSERT INTO threads VALUES(?,?,?)", [
            ("done", 0, "vscode"), ("read", 0, "vscode"), ("old-running", 0, "vscode"),
            ("interrupted", 0, "cli"), ("child", 0, "cli"), ("archive", 1, "vscode")])
        db.execute("INSERT INTO thread_spawn_edges VALUES('child')")
    with sqlite3.connect(tmp_path / "thread_history_1.sqlite") as db:
        db.execute("CREATE TABLE thread_turns(thread_id,status,rollout_ordinal)")
        db.executemany("INSERT INTO thread_turns VALUES(?,?,1)", [
            ("done", "completed"), ("read", "completed"), ("old-running", "inProgress"),
            ("interrupted", "interrupted"), ("child", "completed"), ("archive", "completed")])
    (tmp_path / ".codex-global-state.json").write_text(json.dumps({
        "electron-thread-read-state-v1": {"unreadByIdentity": {"account": {
            "local:host": ["done", "old-running", "interrupted", "child", "archive"],
            "durable:remote": ["read"]}}}}))
    roots, done = read_inventory(tmp_path)
    assert roots == {"done", "read", "old-running", "interrupted"}
    assert done == {"done"}
    assert count_chats(roots, done, {}) == (0, 0, 1)


def test_unavailable_payload_and_ble_size():
    tracker = ChatActivity()
    assert tracker.payload.data["chats"] is False
    assert tracker.status["running"] is None
    assert len(tracker._payload(True, (200, 300, 400)).to_json_bytes()) <= 512
