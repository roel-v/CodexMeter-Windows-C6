"""Read-only observer of the Windows Codex desktop chat stream.

This private, versioned IPC is deliberately isolated here. It only initializes
an observer and follows chat state; it never owns a chat, marks it read, or sends
agent requests. Chat text is discarded immediately after decoding each frame.
"""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
from pathlib import Path
import sqlite3
import struct
import time
import uuid

from .payloads import Payload, build_activity_payload

FIELDS = {"threadRuntimeStatus", "hasUnreadTurn", "parentThreadId", "source"}
MAX_FRAME = 64 * 1024 * 1024
WAIT_FLAGS = {"waitingOnApproval", "waitingOnUserInput"}


def read_inventory(home: Path) -> tuple[set[str], set[str]]:
    """Read indexed metadata only; no transcripts, credentials, or DB writes."""
    with sqlite3.connect((home / "state_5.sqlite").as_uri() + "?mode=ro", uri=True,
                         timeout=1) as db:
        roots = {row[0] for row in db.execute(
            "SELECT id FROM threads WHERE archived=0 AND source IN ('cli','vscode') "
            "AND id NOT IN (SELECT child_thread_id FROM thread_spawn_edges)")}
    state = json.loads((home / ".codex-global-state.json").read_text(encoding="utf-8"))
    identities = state["electron-thread-read-state-v1"]["unreadByIdentity"]
    if len(identities) != 1:
        raise ValueError("Cannot unambiguously select the Codex unread account")
    unread = set()
    for host, ids in next(iter(identities.values())).items():
        if host.startswith("local:"):
            unread.update(ids)
    completed = set()
    with sqlite3.connect((home / "thread_history_1.sqlite").as_uri() + "?mode=ro",
                         uri=True, timeout=1) as db:
        for tid in roots & unread:
            row = db.execute("SELECT status FROM thread_turns WHERE thread_id=? "
                             "ORDER BY rollout_ordinal DESC LIMIT 1", (tid,)).fetchone()
            if row and row[0] == "completed":
                completed.add(tid)
    return roots, completed


def apply_change(states: dict, tid: str, change: dict) -> None:
    if change["type"] == "snapshot":
        raw = change["conversationState"]
        states[tid] = {"revision": change["revision"],
                       "state": {k: copy.deepcopy(raw[k]) for k in FIELDS if k in raw}}
        return
    if change["type"] != "patches" or tid not in states:
        raise ValueError("Chat stream needs a fresh snapshot")
    entry = states[tid]
    if entry["revision"] != change["baseRevision"]:
        raise ValueError("Chat stream revision gap")
    for patch in change["patches"]:
        path = patch["path"]
        if not path:
            raise ValueError("Unexpected root replacement")
        if path[0] not in FIELDS:
            continue
        target = entry["state"]
        for key in path[:-1]:
            target = target[key]
        key = path[-1]
        op = patch["op"]
        if op == "remove":
            if isinstance(target, list):
                target.pop(key)
            else:
                target.pop(key, None)
        elif op in ("add", "replace"):
            value = copy.deepcopy(patch["value"])
            if isinstance(target, list) and op == "add":
                target.insert(key, value)
            else:
                target[key] = value
        else:
            raise ValueError("Unsupported chat patch")
    entry["revision"] = change["revision"]


def count_chats(roots: set[str], completed_unread: set[str], states: dict) -> tuple[int, int, int]:
    running = waiting = 0
    done = set(completed_unread) & roots
    for tid, entry in states.items():
        if tid not in roots:
            continue
        state = entry["state"]
        if state.get("parentThreadId") or state.get("source") not in ("cli", "vscode"):
            done.discard(tid)
            continue
        status = state.get("threadRuntimeStatus") or {}
        if status.get("type") == "active":
            if WAIT_FLAGS.intersection(status.get("activeFlags", [])):
                waiting += 1
            else:
                running += 1
            done.discard(tid)
        elif state.get("hasUnreadTurn") is False:
            done.discard(tid)
    return running, waiting, len(done)


class ChatActivity:
    def __init__(self, home: Path | None = None):
        self.home = home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        self.status = {"available": False, "scope": "local non-archived Codex chats"}
        self.payload = self._payload(False)

    def _payload(self, available: bool, counts=(0, 0, 0)) -> Payload:
        payload = build_activity_payload(counts[0])
        payload.data.update(wait=counts[1], done=counts[2], chats=available)
        self.status.update(available=available, running=counts[0] if available else None,
                           waiting=counts[1] if available else None,
                           done=counts[2] if available else None)
        return payload

    async def run(self, sink, stop_event):
        while not stop_event.is_set():
            try:
                await self._observe(sink, stop_event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # An incompatible private protocol must never take down BLE,
                # quota sync, or the tray. Cancellation is handled above.
                logging.warning("Codex chat observer reconnecting: %s", type(exc).__name__)
            self.payload = self._payload(False)
            await sink(self.payload)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=5)
            except TimeoutError:
                pass

    async def _observe(self, sink, stop_event):
        reader = asyncio.StreamReader(limit=MAX_FRAME)
        protocol = asyncio.StreamReaderProtocol(reader)
        transport, _ = await asyncio.get_running_loop().create_pipe_connection(
            lambda: protocol, r"\\.\pipe\codex-ipc")

        def send(message):
            raw = json.dumps(message, separators=(",", ":")).encode()
            transport.write(struct.pack("<I", len(raw)) + raw)

        async def receive():
            size = struct.unpack("<I", await reader.readexactly(4))[0]
            if not 0 < size <= MAX_FRAME:
                raise ValueError("Invalid IPC frame size")
            return json.loads(await reader.readexactly(size))

        pending = None
        try:
            request = str(uuid.uuid4())
            send(dict(type="request", requestId=request, version=0, method="initialize",
                      params={"clientType": "codexmeter"}))
            async with asyncio.timeout(5):
                while True:
                    message = await receive()
                    if message.get("requestId") == request:
                        client = message["result"]["clientId"]
                        break
            states = {}
            owners = set()
            subscribed = set()
            roots, done = set(), set()
            next_inventory = 0
            ready_at = time.monotonic() + 3
            pending = asyncio.create_task(receive())
            while not stop_event.is_set():
                now = time.monotonic()
                if now >= next_inventory:
                    roots, done = await asyncio.to_thread(read_inventory, self.home)
                    for tid in subscribed ^ roots:
                        send(dict(type="broadcast", method="thread-stream-following-changed",
                                  version=1, sourceClientId=client,
                                  params=dict(conversationId=tid, hostId="local", following=tid in roots)))
                    for tid in subscribed - roots:
                        states.pop(tid, None)
                    subscribed = roots
                    next_inventory = now + 5
                finished, _ = await asyncio.wait({pending}, timeout=1)
                if finished:
                    message = pending.result()
                    pending = asyncio.create_task(receive())
                    method = message.get("method")
                    if message.get("type") == "client-discovery-request":
                        send(dict(type="client-discovery-response", requestId=message["requestId"],
                                  response={"canHandle": False}))
                    elif method == "ipc-connection-reset":
                        raise ValueError("Codex owner connection reset")
                    elif method == "thread-stream-following-status-requested":
                        params = message["params"]
                        if params.get("hostId") == "local" and params.get("conversationId") in roots:
                            send(dict(type="broadcast", method="thread-stream-following-changed",
                                      version=1, sourceClientId=client,
                                      targetClientIds=[message["sourceClientId"]],
                                      params={**params, "following": True}))
                    elif method == "client-status-changed":
                        params = message["params"]
                        if params.get("status") == "disconnected" and params.get("clientId") in owners:
                            raise ValueError("Codex chat owner disconnected")
                    elif method == "thread-stream-state-changed":
                        params = message["params"]
                        tid = params["conversationId"]
                        if params.get("hostId") == "local" and tid in roots:
                            if message.get("version") != 11:
                                raise ValueError("Unsupported Codex chat stream version")
                            apply_change(states, tid, params["change"])
                            owners.add(message.get("sourceClientId"))
                    # Drain queued patches before publishing; text deltas can be frequent.
                    if now < ready_at:
                        continue
                if now >= ready_at:
                    self.payload = self._payload(True, count_chats(roots, done, states))
                    await sink(self.payload)
                    ready_at = now + 2
        finally:
            if pending is not None:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            transport.close()
