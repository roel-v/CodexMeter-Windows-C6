import struct
import zlib
from pathlib import Path

import pytest

from scripts.c6_asset_pack import build_pack, MAGIC
from scripts.c6_fonts import font_requests, original_metrics


def test_pack_is_aligned_deterministic_and_integrity_checked(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "b.rgb565").write_bytes(bytes(range(100)))
    (source / "a.bin").write_bytes(b"mask-data")
    (source / "README.md").write_text("Not firmware data")
    output = tmp_path / "build"
    manifest = build_pack(source, output)
    packed = (output / "c6_assets.bin").read_bytes()
    assert struct.unpack_from("<8sIII", packed) == (
        MAGIC, len(packed), zlib.crc32(packed[32:]), 2)
    assert [entry["name"] for entry in manifest["files"]] == ["a.bin", "b.rgb565"]
    for entry in manifest["files"]:
        assert entry["offset"] % 16 == 0
        data = packed[entry["offset"]:entry["offset"] + entry["size"]]
        assert data == (source / entry["name"]).read_bytes()
        assert zlib.crc32(data) == entry["crc32"]
    assert build_pack(source, output) == manifest
    assert (output / "c6_assets.bin").read_bytes() == packed
    (source / "a.bin").write_bytes(b"changed!!")
    changed = build_pack(source, output)
    assert changed["crc32"] != manifest["crc32"]


def test_empty_pack_is_rejected(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError):
        build_pack(source, tmp_path / "build")


def test_actual_assets_fit_and_fonts_cover_large_original_styles(tmp_path):
    root = Path(__file__).resolve().parents[1] / "firmware"
    pack = build_pack(root / "data" / "themes", tmp_path)
    # C6's mapped address space must also accommodate the application.
    assert pack["bytes"] < 5 * 1024 * 1024
    requests = font_requests(root / "src")
    assert ("Jersey10-Regular.ttf", 160) in requests
    assert ("Teko-SemiBold.ttf", 120) in requests
    assert ("D-DINCondensed-Bold.ttf", 39) in requests
    assert len(requests) == len(set(requests))


def test_static_fonts_preserve_original_ttf_line_spacing():
    fonts = Path(__file__).resolve().parents[1] / "firmware" / "data" / "fonts"
    # These themes position headings in the original font's leading whitespace.
    assert original_metrics(fonts / "Jersey10-Regular.ttf", 160) == (171, 42)
    assert original_metrics(fonts / "Teko-SemiBold.ttf", 100) == (143, 47)
