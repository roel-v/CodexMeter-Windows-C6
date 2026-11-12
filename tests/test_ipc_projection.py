import asyncio
import json
import struct
import tracemalloc
import pytest
from codexmeter.ipc_projection import receive_metadata, MAX_VALUE, CHUNK
from codexmeter.chat_activity import apply_change, count_chats

class Fragments:
    def __init__(self, pieces):
        self.pieces = iter(pieces)
        self.pending = b""
        self.max_read = 0
    async def read(self, n):
        self.max_read = max(self.max_read, n)
        if not self.pending:
            self.pending = next(self.pieces, b"")
        data, self.pending = self.pending[:n], self.pending[n:]
        return data
    async def readexactly(self, n):
        parts = bytearray()
        while len(parts) < n:
            data = await self.read(n-len(parts))
            if not data:
                raise asyncio.IncompleteReadError(bytes(parts), n)
            parts.extend(data)
        return bytes(parts)

def framed(message, chunk=13):
    body = json.dumps(message, ensure_ascii=False).encode()
    raw = struct.pack("<I", len(body)) + body
    return Fragments(raw[i:i+chunk] for i in range(0, len(raw), chunk))

def message(change):
    return {"method":"thread-stream-state-changed", "version":11,
            "params":{"conversationId":"a", "hostId":"local", "change":change}}

@pytest.mark.parametrize("chunk", [1,2,3,13,65536])
def test_projection_split_utf8_escapes_and_status(chunk):
    raw = message({"type":"snapshot","revision":1,"conversationState":{
        "turns":[{"text":'secret \" quote \\ newline\n café 😃 [ }'}],
        "threadRuntimeStatus":{"type":"active","activeFlags":["waitingOnApproval"]},
        "source":"vscode", "parentThreadId":None,"hasUnreadTurn":True}})
    decoded=asyncio.run(receive_metadata(framed(raw,chunk)))
    assert "secret" not in json.dumps(decoded)
    states={}
    apply_change(states,"a",decoded["params"]["change"])
    assert count_chats({"a"},set(),states)==(0,1,0)

@pytest.mark.parametrize("value_first", [True,False])
def test_large_irrelevant_patch_preserves_revision(value_first):
    patch={"value":"secret"*20000,"op":"replace","path":["turns",0,"text"]}
    if not value_first:
        patch={"path":patch["path"],"op":"replace","value":patch["value"]}
    decoded=asyncio.run(receive_metadata(framed(message({"type":"patches",
        "baseRevision":1,"revision":2,"patches":[patch]}),65536)))
    states={"a":{"revision":1,"state":{"source":"vscode"}}}
    apply_change(states,"a",decoded["params"]["change"])
    assert states["a"]["revision"]==2
    assert "secret" not in json.dumps(decoded)

def test_huge_snapshot_bounded_memory_and_next_frame_alignment():
    prefix=b'{"params":{"change":{"type":"snapshot","revision":1,"conversationState":{"turns":[{"text":"'
    suffix=b'"}],"source":"vscode","threadRuntimeStatus":{"type":"active"}}}}}'
    block=b'x'*CHUNK
    blocks=1400  # 87.5 MiB, larger than the failing real message.
    size=len(prefix)+len(suffix)+len(block)*blocks
    tail=json.dumps({"type":"client-discovery-request","requestId":"next"}).encode()
    def pieces():
        yield struct.pack("<I",size)
        yield prefix
        for _ in range(blocks): yield block
        yield suffix
        yield struct.pack("<I",len(tail))
        yield tail
    reader=Fragments(pieces())
    async def run():
        stats={}
        first=await receive_metadata(reader,stats)
        second=await receive_metadata(reader)
        return first,second,stats
    tracemalloc.start()
    first,second,stats=asyncio.run(run())
    _,peak=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 4*1024*1024
    assert stats["discarded_value_bytes"] > 80*1024*1024
    assert stats["metadata_bytes"] < 1024
    assert second["requestId"]=="next"
    assert first["params"]["change"]["conversationState"]["source"]=="vscode"
    assert reader.max_read<=CHUNK

@pytest.mark.parametrize("body", [b'{',b'{"params":', b'{"junk":"unfinished',
    b'{"junk":[}', b'{"type":"ok"}garbage',b'{"type": tru}'])
def test_malformed_or_truncated_frame_rejected(body):
    with pytest.raises((ValueError,asyncio.IncompleteReadError)):
        asyncio.run(receive_metadata(Fragments([struct.pack("<I",len(body)),body])))

def test_oversized_relevant_patch_is_not_silently_accepted():
    raw=message({"type":"patches","baseRevision":1,"revision":2,"patches":[
        {"value":"x"*(MAX_VALUE+1),"path":["source"],"op":"replace"}]})
    with pytest.raises(ValueError,match="status patch"):
        asyncio.run(receive_metadata(framed(raw,65536)))


def test_oversized_status_snapshot_is_rejected():
    raw=message({"type":"snapshot","revision":1,
                 "conversationState":{"source":"x"*(MAX_VALUE+1)}})
    with pytest.raises(ValueError,match="metadata value too large"):
        asyncio.run(receive_metadata(framed(raw,65536)))


def test_cancellation_can_interrupt_large_skipped_value():
    body=b'{"ignored":"' + b'x'*(4*CHUNK) + b'"}'
    async def run():
        task=asyncio.create_task(receive_metadata(Fragments([struct.pack("<I",len(body)),body])))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(run())
