"""Bounded-memory projection of length-framed JSON chat messages.

Only the supplied metadata schema is decoded. Unselected values are scanned for
JSON boundaries in bounded chunks, never assembled into transcript objects.
"""
from __future__ import annotations
import asyncio
import json
import re
import struct

CHUNK = 64 * 1024
MAX_FRAME = 512 * 1024 * 1024
MAX_METADATA = 256 * 1024
MAX_VALUE = 64 * 1024
ALL = object()
OVERSIZED = object()
SPECIAL = re.compile(rb'["\\{}\[\]]')
DELIMITER = re.compile(rb'[\s,}\]]')

class ProjectionReader:
    def __init__(self, reader, size):
        self.reader, self.remaining = reader, size
        self.buffer = b""
        self.pos = 0
        self.retained = 0
        self.skipped = 0

    async def fill(self):
        if self.pos < len(self.buffer):
            return True
        if not self.remaining:
            return False
        # Long snapshots must not starve BLE, UI heartbeats or cancellation.
        await asyncio.sleep(0)
        self.buffer = await self.reader.read(min(CHUNK, self.remaining))
        if not self.buffer:
            raise ValueError("Truncated IPC frame")
        self.remaining -= len(self.buffer)
        self.pos = 0
        return True

    async def peek(self):
        return self.buffer[self.pos] if await self.fill() else None

    async def whitespace(self):
        while await self.fill():
            start = self.pos
            while self.pos < len(self.buffer) and self.buffer[self.pos] in b" \t\r\n":
                self.pos += 1
            if self.pos < len(self.buffer):
                break

    async def expect(self, byte):
        await self.whitespace()
        if await self.peek() != byte:
            raise ValueError("Malformed IPC metadata")
        self.pos += 1

    async def raw(self, retain):
        """Scan a complete value; cap retained scalar/patch bytes independently."""
        await self.whitespace()
        first = await self.peek()
        if first is None:
            raise ValueError("Missing IPC value")
        output = bytearray()
        total = 0
        overflow = False
        def consume(end):
            nonlocal total, overflow
            count = end - self.pos
            total += count
            if retain and not overflow:
                if len(output) + count <= MAX_VALUE:
                    output.extend(self.buffer[self.pos:end])
                else:
                    output.clear()
                    overflow = True
            self.pos = end
        if first not in (34, 123, 91):
            while await self.fill():
                match = DELIMITER.search(self.buffer, self.pos)
                consume(match.start() if match else len(self.buffer))
                if match:
                    break
            if not total:
                raise ValueError("Missing IPC scalar")
        else:
            stack = []
            string = False
            escaped = False
            complete = False
            while await self.fill():
                if escaped:
                    consume(self.pos + 1)
                    escaped = False
                    continue
                match = SPECIAL.search(self.buffer, self.pos)
                if not match:
                    consume(len(self.buffer))
                    continue
                byte = self.buffer[match.start()]
                consume(match.end())
                if string:
                    if byte == 92:
                        escaped = True
                    elif byte == 34:
                        string = False
                        if not stack:
                            complete = True
                            break
                    continue
                if byte == 34:
                    string = True
                elif byte in (123, 91):
                    stack.append(125 if byte == 123 else 93)
                    if len(stack) > 128:
                        raise ValueError("IPC nesting too deep")
                elif byte in (125, 93):
                    if not stack or stack.pop() != byte:
                        raise ValueError("Malformed IPC container")
                    if not stack:
                        complete = True
                        break
                else:
                    raise ValueError("Malformed IPC value")
            if not complete:
                raise ValueError("Truncated IPC value")
        if not retain:
            self.skipped += total
            return None
        if overflow:
            self.skipped += total
            return OVERSIZED
        self.retained += total
        if self.retained > MAX_METADATA:
            raise ValueError("IPC metadata budget exceeded")
        try:
            return json.loads(output)
        except (ValueError, UnicodeError):
            # Do not attach decoder exceptions containing source text.
            raise ValueError("Malformed IPC metadata") from None

    async def value(self, schema, depth=0):
        if depth > 32:
            raise ValueError("IPC metadata nesting too deep")
        if schema is None or schema is ALL:
            return await self.raw(schema is ALL)
        await self.whitespace()
        if isinstance(schema, list):
            await self.expect(91)
            values = []
            await self.whitespace()
            if await self.peek() == 93:
                self.pos += 1
                return values
            while True:
                values.append(await self.value(schema[0], depth + 1))
                if len(values) > 4096:
                    raise ValueError("Too many IPC metadata entries")
                await self.whitespace()
                byte = await self.peek()
                if byte == 93:
                    self.pos += 1
                    return values
                await self.expect(44)
        await self.expect(123)
        result = {}
        await self.whitespace()
        if await self.peek() == 125:
            self.pos += 1
            return result
        while True:
            key = await self.raw(True)
            if not isinstance(key, str):
                raise ValueError("Invalid IPC metadata key")
            await self.expect(58)
            selected = schema.get(key)
            # Usually path precedes value; avoid retaining even small text patches.
            if schema is PATCH and key == "value" and "path" in result:
                if not result["path"] or result["path"][0] not in FIELDS:
                    selected = None
            value = await self.value(selected, depth + 1)
            if selected is not None:
                result[key] = value
            await self.whitespace()
            byte = await self.peek()
            if byte == 125:
                self.pos += 1
                if schema is PATCH:
                    path = result.get("path")
                    if not isinstance(path, list) or not path or path[0] not in FIELDS:
                        result.pop("value", None)
                    elif result.get("value") is OVERSIZED:
                        raise ValueError("IPC status patch too large")
                return result
            await self.expect(44)

FIELDS = {"threadRuntimeStatus", "hasUnreadTurn", "parentThreadId", "source"}
PATCH = {"op": ALL, "path": ALL, "value": ALL}
SCHEMA = {"type": ALL, "requestId": ALL, "method": ALL, "version": ALL,
          "sourceClientId": ALL, "result": {"clientId": ALL},
          "params": {"hostId": ALL, "conversationId": ALL, "clientId": ALL,
                     "status": ALL, "change": {"type": ALL, "revision": ALL,
                     "baseRevision": ALL, "patches": [PATCH],
                     "conversationState": {key: ALL for key in FIELDS}}}}

async def receive_metadata(reader, stats=None):
    size = struct.unpack("<I", await reader.readexactly(4))[0]
    if not 0 < size <= MAX_FRAME:
        raise ValueError("Invalid IPC frame size")
    parser = ProjectionReader(reader, size)
    result = await parser.value(SCHEMA)
    await parser.whitespace()
    if await parser.peek() is not None:
        raise ValueError("Trailing IPC frame data")
    def validate(value):
        if value is OVERSIZED:
            raise ValueError("IPC metadata value too large")
        if isinstance(value, dict):
            for item in value.values():
                validate(item)
        elif isinstance(value, list):
            for item in value:
                validate(item)
    validate(result)
    if stats is not None:
        stats.update(frame_bytes=size, metadata_bytes=parser.retained,
                     discarded_value_bytes=parser.skipped)
    return result
