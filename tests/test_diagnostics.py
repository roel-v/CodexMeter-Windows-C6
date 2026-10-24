"""Exercise diagnostics in real child processes, including hard termination."""
import json
import os
from pathlib import Path
import subprocess
import sys


def run_child(directory: Path, body: str):
    script = (
        "import os, threading, asyncio\n"
        "from pathlib import Path\n"
        "from codexmeter.diagnostics import RunDiagnostics\n"
        f"with RunDiagnostics(Path({str(directory)!r})) as diagnostic:\n"
        + "\n".join("    " + line for line in body.splitlines())
    )
    return subprocess.run([sys.executable, "-c", script], capture_output=True,
                          timeout=30, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})


def test_clean_exit_and_heartbeat(tmp_path):
    result = run_child(tmp_path, "async def exercise():\n"
                      "    stop = asyncio.Event()\n"
                      "    task = asyncio.create_task(diagnostic.heartbeat(stop))\n"
                      "    await asyncio.sleep(.05)\n"
                      "    stop.set()\n"
                      "    await task\n"
                      "asyncio.run(exercise())")
    assert result.returncode == 0, result.stderr
    state = json.loads((tmp_path / "last-run.json").read_text())
    assert state["outcome"] == "clean_exit"
    assert state["last_bridge_heartbeat"] >= state["started_at"]
    assert "CLEAN_EXIT" in (tmp_path / "lifecycle.log").read_text()


def test_exception_retains_traceback(tmp_path):
    assert run_child(tmp_path, "raise RuntimeError('injected failure')").returncode != 0
    state = json.loads((tmp_path / "last-run.json").read_text())
    assert state["outcome"] == "exception"
    log = (tmp_path / "lifecycle.log").read_text()
    assert "Traceback" in log and "injected failure" in log


def test_hard_exit_detected_on_next_launch(tmp_path):
    assert run_child(tmp_path, "os._exit(23)").returncode == 23
    old = json.loads((tmp_path / "last-run.json").read_text())
    assert old["outcome"] == "running"
    assert run_child(tmp_path, "pass").returncode == 0
    log = (tmp_path / "lifecycle.log").read_text()
    assert "PREVIOUS_UNCLEAN_EXIT" in log and old["run_id"] in log


def test_thread_exception_recorded(tmp_path):
    result = run_child(tmp_path, "def fail():\n"
                      "    raise ValueError('injected thread failure')\n"
                      "thread = threading.Thread(target=fail, name='test worker')\n"
                      "thread.start()\nthread.join()")
    assert result.returncode == 0, result.stderr
    log = (tmp_path / "lifecycle.log").read_text()
    assert "UNCAUGHT_THREAD name=test worker" in log
    assert "injected thread failure" in log


def test_async_exception_recorded_and_handler_restored(tmp_path):
    result = run_child(tmp_path, "async def exercise():\n"
                      "    loop = asyncio.get_running_loop()\n"
                      "    old = loop.get_exception_handler()\n"
                      "    stop = asyncio.Event()\n"
                      "    task = asyncio.create_task(diagnostic.heartbeat(stop))\n"
                      "    await asyncio.sleep(.05)\n"
                      "    loop.call_exception_handler({'message': 'injected async failure'})\n"
                      "    stop.set()\n"
                      "    await task\n"
                      "    assert loop.get_exception_handler() is old\n"
                      "asyncio.run(exercise())")
    assert result.returncode == 0, result.stderr
    assert "ASYNC_EXCEPTION injected async failure" in (tmp_path / "lifecycle.log").read_text()
