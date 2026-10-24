"""Generate fixed Latin fonts from the original theme TTFs; no runtime TTF heap."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import struct


def original_metrics(font: Path, size: int) -> tuple[int, int]:
    """Match TinyTTF's unhinted hhea line box, not the converter's glyph bounds."""
    data = font.read_bytes()
    count = struct.unpack_from(">H", data, 4)[0]
    tables = {}
    for index in range(count):
        tag, _, offset, length = struct.unpack_from(">4sIII", data, 12 + index * 16)
        if offset + length > len(data):
            raise ValueError(f"Invalid font table: {font}")
        tables[tag] = offset
    units = struct.unpack_from(">H", data, tables[b"head"] + 18)[0]
    ascent, descent, gap = struct.unpack_from(">hhh", data, tables[b"hhea"] + 4)
    return int(size * (ascent - descent + gap) / units), int(size * (gap - descent) / units)


def font_requests(source: Path) -> list[tuple[str, int]]:
    requests = set()
    for path in sorted(source.glob("*_theme.cpp")):
        text = path.read_text(encoding="utf-8")
        constants = dict(re.findall(r'constexpr char (\w+)\[\]\s*=\s*"S:/fonts/([^"\n]+)";', text))
        for key, size in re.findall(r'(?:lv_tiny_ttf_create_file_ex|create_font)\(\s*([A-Z_]+),\s*(\d+)', text):
            requests.add((constants[key], int(size)))
        if path.name == "nixie_theme.cpp":
            for size in re.findall(r'create_font\(\s*(\d+),', text):
                requests.add((constants["VALUE_FONT_PATH"], int(size)))
    return sorted(requests)


def build_fonts(project: Path, output: Path, converter: Path, node: str = "node") -> None:
    if not converter.is_file():
        raise RuntimeError("Missing lv_font_conv 1.5.3. Run build-windows.ps1 -Firmware to install it on D:.")
    output.mkdir(parents=True, exist_ok=True)
    declarations = []
    rows = []
    for index, (filename, size) in enumerate(font_requests(project / "src")):
        font = project / "data" / "fonts" / filename
        name = f"c6_theme_font_{index}"
        dest = output / f"{name}.c"
        digest = hashlib.sha256(font.read_bytes() + f"{size}:2:ascii:1.5.3:no-compress".encode()).hexdigest()
        stamp = dest.with_suffix(".sha256")
        if not dest.exists() or not stamp.exists() or stamp.read_text() != digest:
            subprocess.run([node, str(converter), "--font", str(font), "--size", str(size),
                            "--bpp", "2", "--format", "lvgl", "--no-compress", "-r", "32-126",
                            "--lv-font-name", name, "-o", str(dest)], check=True,
                           capture_output=True, text=True)
            stamp.write_text(digest)
        declarations.append(f"LV_FONT_DECLARE({name});")
        height, baseline = original_metrics(font, size)
        rows.append(f'  {{"{filename}", {size}, &{name}, {height}, {baseline}, {{}}, false}},')
    registry = '\n'.join([
        '#include "theme_fonts.h"', '#include "device_log.h"', '#include <string.h>',
        *declarations,
        'namespace {',
        'struct Entry { const char* name; int size; const lv_font_t* source; int height; int baseline; lv_font_t font; bool ready; };',
        'Entry entries[] = {', *rows, '};', '}',
        'lv_font_t* c6_font_get(const char* path, int size) {',
        "  const char* name = strrchr(path, '/'); name = name ? name + 1 : path;",
        '  for (auto& entry : entries) {',
        '    if (entry.size != size || strcmp(entry.name, name) != 0) continue;',
        '    if (!entry.ready) { entry.font = *entry.source; entry.font.line_height = entry.height; entry.font.base_line = entry.baseline; entry.ready = true; }',
        '    return &entry.font;', '  }',
        '  device_logf("ERROR", "C6 font missing %s size=%d", name, size);',
        '  return nullptr;', '}', ''])
    dest = output / 'c6_theme_fonts.cpp'
    if not dest.exists() or dest.read_text() != registry:
        dest.write_text(registry, encoding='utf-8')
    (output / 'fonts.json').write_text(json.dumps(font_requests(project / 'src'), indent=2), encoding='utf-8')
