"""Local process evidence. Never restarts the application or uploads reports."""
from __future__ import annotations

import asyncio
import ctypes
import faulthandler
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading
import time
import uuid

from .persistence import atomic_write_json


def windows_process_context() -> dict:
    if sys.platform != "win32":
        return {}
    from ctypes import wintypes as w

    class Basic(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                    ("flags", w.DWORD), ("min_ws", ctypes.c_size_t),
                    ("max_ws", ctypes.c_size_t), ("active", w.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", w.DWORD),
                    ("scheduling", w.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [("basic", Basic), ("io", ctypes.c_uint64 * 6),
                    ("process_mem", ctypes.c_size_t), ("job_mem", ctypes.c_size_t),
                    ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.IsProcessInJob.argtypes = [w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)]
    kernel.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                               w.DWORD, ctypes.c_void_p]
    member = w.BOOL()
    context = {}
    if kernel.IsProcessInJob(kernel.GetCurrentProcess(), None, ctypes.byref(member)):
        context["in_job"] = bool(member.value)
    limits = Extended()
    if member.value and kernel.QueryInformationJobObject(None, 9, ctypes.byref(limits),
                                                        ctypes.sizeof(limits), None):
        context["immediate_job_limit_flags"] = limits.basic.flags
        context["immediate_job_kill_on_close"] = bool(limits.basic.flags & 0x2000)
    processes = (w.DWORD * 128)()
    context["console_process_count"] = kernel.GetConsoleProcessList(processes, 128)
    return context


class RunDiagnostics:
    """Only enter after obtaining the daemon lock, so markers have one owner."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.state_path = directory / "last-run.json"
        self.state = {"run_id": uuid.uuid4().hex, "pid": os.getpid(),
                      "parent_pid": os.getppid(), "started_at": time.time(),
                      "entrypoint": sys.argv[0], "outcome": "running"}
        self.logger = logging.getLogger("codexmeter.lifecycle")

    def save(self):
        try:
            atomic_write_json(self.state_path, self.state)
        except OSError:
            self.logger.exception("Could not persist diagnostic state")

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.handler = RotatingFileHandler(self.directory / "lifecycle.log",
                                          maxBytes=2_000_000, backupCount=2, encoding="utf-8")
        self.handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        try:
            previous = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = None
        if isinstance(previous, dict) and previous.get("outcome") == "running":
            self.logger.error("PREVIOUS_UNCLEAN_EXIT %s", json.dumps(previous))
        self.state.update(windows_process_context())
        self.save()
        self.logger.info("START %s", json.dumps(self.state))
        # One native fault file per run; retain the newest ten, including empty files.
        for old in sorted(self.directory.glob("fault-*.log"), key=lambda p: p.stat().st_mtime)[:-9]:
            old.unlink()
        self.fault_file = (self.directory / f"fault-{self.state['run_id']}.log").open("a", encoding="utf-8")
        faulthandler.enable(self.fault_file, all_threads=True)
        self.old_thread_hook = threading.excepthook
        def thread_hook(args):
            self.logger.critical("UNCAUGHT_THREAD name=%s", args.thread.name if args.thread else None,
                                 exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        threading.excepthook = thread_hook
        return self

    async def heartbeat(self, stop_event: asyncio.Event, desktop=None):
        loop = asyncio.get_running_loop()
        old_handler = loop.get_exception_handler()
        def exception_handler(loop, context):
            exc = context.get("exception")
            self.logger.error("ASYNC_EXCEPTION %s", context.get("message"),
                              exc_info=(type(exc), exc, exc.__traceback__) if exc else None)
        loop.set_exception_handler(exception_handler)
        try:
            while not stop_event.is_set():
                self.state["last_bridge_heartbeat"] = time.time()
                if desktop is not None:
                    self.state["last_ui_heartbeat"] = desktop.last_poll_at
                self.save()
                try:
                    await asyncio.wait_for(stop_event.wait(), 30)
                except asyncio.TimeoutError:
                    pass
        finally:
            loop.set_exception_handler(old_handler)

    def __exit__(self, exc_type, exc, tb):
        self.state.update(outcome="exception" if exc_type else "clean_exit", ended_at=time.time())
        if exc_type:
            self.state["exception_type"] = exc_type.__name__
            self.logger.critical("EXIT_EXCEPTION", exc_info=(exc_type, exc, tb))
        else:
            self.logger.info("CLEAN_EXIT run_id=%s", self.state["run_id"])
        self.save()
        threading.excepthook = self.old_thread_hook
        faulthandler.disable()
        self.fault_file.close()
        self.logger.removeHandler(self.handler)
        self.handler.close()
