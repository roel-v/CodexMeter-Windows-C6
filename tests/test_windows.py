"""Exercise the real Windows transport and process boundaries, not just mocks."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from codexmeter import ipc
from codexmeter.daemon import DaemonLock
from codexmeter.events import EventServer, send_event

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Native Windows integration")
ROOT = Path(__file__).resolve().parents[1]


def test_windows_events_hooks_authentication_and_cleanup(tmp_path):
    async def run():
        received = []
        async def sink(payload):
            received.append(payload)
        endpoint = tmp_path / "events.sock"
        stop = asyncio.Event()
        server = EventServer(sink, socket_path=endpoint, transcript_root=tmp_path)
        task = asyncio.create_task(server.run(stop))
        try:
            for _ in range(100):
                if endpoint.exists():
                    break
                await asyncio.sleep(0.01)
            assert (await send_event({"type": "ping"}, endpoint))["ok"]
            port, token = ipc.read_endpoint(endpoint)
            assert token not in endpoint.read_text()
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b'{"token":"wrong","event":{"type":"shutdown"}}\n')
            await writer.drain()
            assert not json.loads(await reader.read(4096))["ok"]
            writer.close()
            await writer.wait_closed()
            assert not stop.is_set()

            # TCP can split a JSON event at any byte boundary.
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            packet = json.dumps({"token": token, "event": {"type": "ping"}}).encode() + b"\n"
            writer.write(packet[:15])
            await writer.drain()
            await asyncio.sleep(0.02)
            writer.write(packet[15:])
            await writer.drain()
            assert json.loads(await reader.read(4096))["ok"]
            writer.close()
            await writer.wait_closed()

            async def hook(name, payload):
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, str(ROOT / "hooks" / name),
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={**os.environ, "CODEXMETER_SOCKET": str(endpoint)},
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                output, error = await asyncio.wait_for(proc.communicate(json.dumps(payload).encode()), 5)
                assert proc.returncode == 0, error
                assert json.loads(output) == {"continue": True}

            await hook("codexmeter_start_hook.py", {"turn_id": "win-test"})
            assert server.activity.count == 1
            await hook("codexmeter_stop_hook.py", {"turn_id": "win-test", "last_assistant_message": "Build passed."})
            assert server.activity.count == 0
            assert received[-1].kind == "alert"
            assert received[-1].data["title"] == "Task complete!"
            assert (await send_event({"type": "shutdown"}, endpoint))["ok"]
            await asyncio.wait_for(task, 3)
            assert not endpoint.exists()
        finally:
            stop.set()
            await asyncio.wait_for(task, 3)
    asyncio.run(run())


def test_windows_daemon_lock_across_processes(tmp_path):
    path = tmp_path / "daemon.lock"
    script = (
        "from pathlib import Path; import sys; "
        "from codexmeter.daemon import DaemonLock, DaemonAlreadyRunning\n"
        "try:\n with DaemonLock(Path(sys.argv[1])): pass\n"
        "except DaemonAlreadyRunning: sys.exit(42)\n"
    )
    def child():
        return subprocess.run([sys.executable, "-c", script, str(path)], timeout=5,
                              capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    with DaemonLock(path):
        assert child().returncode == 42
    assert child().returncode == 0


def test_windows_dpapi_rejects_tampering():
    protected = ipc._dpapi(b"local-secret")
    assert ipc._dpapi(protected, decrypt=True) == b"local-secret"
    with pytest.raises(OSError):
        ipc._dpapi(protected[:-10] + b"corruption", decrypt=True)
