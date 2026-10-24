"""Validate onefile activation, native panel close and the live tray status."""
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import time

from validate_standalone import clean_environment


def validate(binary: Path, output: Path):
    binary = binary.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = clean_environment()
    results = {}

    def status():
        process = subprocess.run([str(binary), "--cli", "status"], env=env, cwd=binary.parent,
                                 capture_output=True, text=True, encoding="utf-8", timeout=30,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        if process.returncode:
            raise RuntimeError(process.stderr)
        return json.loads(process.stdout)

    deadline = time.monotonic() + 75
    current = {}
    while time.monotonic() < deadline:
        try:
            current = status()
        except RuntimeError as exc:
            current = {"startup_error": str(exc)}
            time.sleep(1)
            continue
        if current.get("tray", {}).get("state") == "green":
            break
        time.sleep(1)
    else:
        raise AssertionError(current)
    assert current["ble"]["connected"] and current["tray"]["visible"]
    results["connected_status"] = current

    # No arguments must request the existing panel and exit, rather than create
    # a second daemon/icon or keep a second control-panel process running.
    for _ in range(2):
        process = subprocess.run([str(binary)], env=env, cwd=binary.parent,
                                 timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        assert process.returncode == 0
    current = status()
    assert current["tray"]["panel_open"]
    results["repeated_launch_reuses_panel"] = True

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [enum_proc, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    panels = []

    @enum_proc
    def find_panel(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, len(title))
        if title.value == "CodexMeter":
            handle = kernel32.OpenProcess(0x1000, False, pid.value)
            if handle:
                try:
                    image = ctypes.create_unicode_buffer(32768)
                    size = wintypes.DWORD(len(image))
                    if kernel32.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
                        if Path(image.value).resolve() == binary:
                            panels.append(hwnd)
                finally:
                    kernel32.CloseHandle(handle)
        return True

    user32.EnumWindows(find_panel, 0)
    assert len(panels) == 1, panels
    assert user32.PostMessageW(panels[0], 0x0010, 0, 0)  # WM_CLOSE, same as window X
    time.sleep(0.5)
    current = status()
    assert not current["tray"]["panel_open"]
    assert current["tray"]["visible"] and current["ble"]["connected"]
    results["window_close_preserves_bridge"] = True
    results["final_status"] = current
    (output / "tray-live.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("Live tray status, repeat launch, single panel and close-to-tray passed.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    validate(args.binary, args.output)
