"""Local event transport: Unix sockets on POSIX, authenticated loopback on Windows.

Windows endpoint secrets are encrypted with DPAPI for the current user. No
network listener or fixed port is exposed; each daemon gets a fresh secret.
"""
from __future__ import annotations

import asyncio
import base64
import ctypes
import json
import secrets
import socket
import sys
from pathlib import Path

from .persistence import atomic_write_json

WINDOWS = sys.platform == "win32"
MAX_EVENT_BYTES = 16384


def _dpapi(data: bytes, *, decrypt: bool = False) -> bytes:
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    # CRYPTPROTECT_UI_FORBIDDEN; no machine scope, so only this user can decrypt.
    if decrypt:
        ok = crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        ok = crypt.CryptProtectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


def read_endpoint(path: Path) -> tuple[int, str]:
    endpoint = json.loads(path.read_text(encoding="utf-8"))
    port = int(endpoint["port"])
    if not 0 < port < 65536:
        raise ValueError("Invalid local event port")
    token = _dpapi(base64.b64decode(endpoint["secret"]), decrypt=True).decode("ascii")
    return port, token


async def start_server(handler, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not WINDOWS:
        path.unlink(missing_ok=True)
        return await asyncio.start_unix_server(handler, path), None
    token = secrets.token_hex(32)
    server = await asyncio.start_server(handler, "127.0.0.1", 0, limit=MAX_EVENT_BYTES + 1)
    try:
        atomic_write_json(path, {
            "port": server.sockets[0].getsockname()[1],
            "secret": base64.b64encode(_dpapi(token.encode("ascii"))).decode("ascii"),
        })
    except BaseException:
        server.close()
        await server.wait_closed()
        raise
    return server, token


async def send(event: dict, path: Path) -> dict:
    if WINDOWS:
        port, token = read_endpoint(path)
        reader, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port, limit=MAX_EVENT_BYTES + 1), 2)
        event = {"token": token, "event": event}
    else:
        reader, writer = await asyncio.open_unix_connection(path, limit=MAX_EVENT_BYTES + 1)
    try:
        writer.write(json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n")
        await writer.drain()
        if not WINDOWS and writer.can_write_eof():
            writer.write_eof()
        raw = await asyncio.wait_for(reader.readline(), 3)
        if len(raw) > MAX_EVENT_BYTES:
            raise ValueError("Local event response is too large")
        result = json.loads(raw) if raw else {}
        return result if isinstance(result, dict) else {}
    finally:
        writer.close()
        await writer.wait_closed()


def send_hook(event: dict, path: Path) -> None:
    """Bounded synchronous Windows transport for short-lived hook processes."""
    port, token = read_endpoint(path)
    payload = json.dumps({"token": token, "event": event}, ensure_ascii=False).encode("utf-8") + b"\n"
    with socket.create_connection(("127.0.0.1", port), timeout=0.35) as client:
        client.sendall(payload)
        client.recv(4096)
