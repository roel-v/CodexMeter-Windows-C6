import sys
from pathlib import Path

import pytest

from codexmeter import launch


def test_source_mode_launches_python_modules(monkeypatch):
    monkeypatch.delattr(launch, "__compiled__", raising=False)
    assert launch.app_command("cli", "status") == [sys.executable, "-m", "codexmeter.cli", "status"]


def test_packaged_child_uses_outer_executable_not_python(monkeypatch, tmp_path):
    outer = tmp_path / "app folder" / "CodexMeter.exe"
    monkeypatch.setattr(launch, "__compiled__", object(), raising=False)
    monkeypatch.setattr(sys, "argv", [str(outer), "--daemon"])
    monkeypatch.setattr(sys, "executable", str(tmp_path / "extracted" / "inner.exe"))
    assert launch.app_command("daemon", "--codex-bin", "codex") == [str(outer.resolve()), "--daemon", "--codex-bin", "codex"]


def test_unrecognized_role_rejected():
    with pytest.raises(ValueError):
        launch.app_command("arbitrary_module")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows lifetime isolation")
def test_background_child_survives_launching_job_close(tmp_path):
    import subprocess
    import time
    marker = tmp_path / "survived.txt"
    parent = tmp_path / "parent.py"
    parent.write_text(r"""
import ctypes, os, sys, time
from ctypes import wintypes as w
from pathlib import Path
from codexmeter.launch import launch_background
class Basic(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", w.DWORD), ("min_ws", ctypes.c_size_t),
                ("max_ws", ctypes.c_size_t), ("active", w.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
class Extended(ctypes.Structure):
    _fields_ = [("basic", Basic), ("io", ctypes.c_uint64 * 6),
                ("process_mem", ctypes.c_size_t), ("job_mem", ctypes.c_size_t),
                ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]
k = ctypes.WinDLL("kernel32", use_last_error=True)
k.CreateJobObjectW.restype = w.HANDLE
k.GetCurrentProcess.restype = w.HANDLE
k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
k.CloseHandle.argtypes = [w.HANDLE]
job = k.CreateJobObjectW(None, None)
limits = Extended()
limits.basic.flags = 0x2000 | 0x800  # kill on close, allow breakaway
assert k.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))
assert k.AssignProcessToJobObject(job, k.GetCurrentProcess())
code = "import time; from pathlib import Path; from codexmeter.diagnostics import windows_process_context; from codexmeter.launch import detach_background_daemon; detach_background_daemon([]); time.sleep(1); c=windows_process_context(); Path(" + repr(sys.argv[1]) + ").write_text(repr(c))"
launch_background([sys.executable, "-c", code])
# Closing the owning job kills this launcher, but must not kill the detached child.
k.CloseHandle(job)
""")
    process = subprocess.Popen([sys.executable, str(parent), str(marker)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    _, error = process.communicate(timeout=15)
    deadline = time.monotonic() + 10
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(.1)
    assert marker.exists(), error.decode(errors="replace")
    import ast
    context = ast.literal_eval(marker.read_text())
    # The venv launcher may own a new job; survival proves the old job is gone.
    assert not context.get("console_process_count"), context


def test_foreground_is_not_detached(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert launch.detach_background_daemon(["--foreground"]) is False


def test_already_independent_daemon_does_not_relaunch(monkeypatch):
    from codexmeter import diagnostics
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(diagnostics, "windows_process_context",
                        lambda: {"in_job": False, "console_process_count": 0})
    assert launch.detach_background_daemon([]) is False
