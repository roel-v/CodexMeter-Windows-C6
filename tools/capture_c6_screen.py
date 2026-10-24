"""Capture an upright LVGL frame from C6 tiles without a device framebuffer."""
from pathlib import Path
import argparse
import struct
import time
import zlib
from serial_device import SerialSession


def capture(port: SerialSession, output: Path) -> None:
    port.write_line("screenshot")
    deadline = time.monotonic() + 20
    while True:
        line = port.read_line(max(0.1, deadline - time.monotonic())).decode()
        if line.startswith("TILED_SCREENSHOT_START "):
            _, width, height = line.split()
            width, height = int(width), int(height)
            break
        if line.startswith("SCREENSHOT_"):
            raise RuntimeError(line)
    assert (width, height) == (480, 480)
    pixels = bytearray(width * height * 2)
    covered = bytearray(width * height)
    while True:
        line = port.read_line(max(0.1, deadline - time.monotonic())).decode()
        if line == "TILED_SCREENSHOT_END":
            break
        if not line or line.startswith("LOG "):
            continue
        if not line.startswith("TILE "):
            raise RuntimeError(f"Unexpected capture response: {line}")
        x, y, w, h, size, crc = map(int, line.split()[1:])
        assert 0 <= x < width and 0 <= y < height and x + w <= width and y + h <= height
        assert size == w * h * 2
        tile = port.read_exact(size, max(0.1, deadline - time.monotonic()))
        assert zlib.crc32(tile) == crc, "Serial image CRC mismatch"
        for row in range(h):
            offset = (y + row) * width + x
            pixels[offset * 2:(offset + w) * 2] = tile[row * w * 2:(row + 1) * w * 2]
            covered[offset:offset + w] = b"\x01" * w
    assert all(covered), "Incomplete screenshot"
    # Standard PNG output; Pillow runs on the PC, never on the microcontroller.
    from PIL import Image
    rgb = bytearray()
    for (pixel,) in struct.iter_unpack("<H", pixels):
        r, g, b = (pixel >> 11) & 31, (pixel >> 5) & 63, pixel & 31
        rgb.extend(((r * 255 + 15) // 31, (g * 255 + 31) // 63, (b * 255 + 15) // 31))
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.frombytes("RGB", (width, height), bytes(rgb)).save(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with SerialSession(args.port) as serial:
        capture(serial, args.output)
    print(args.output)
