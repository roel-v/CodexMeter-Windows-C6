"""PlatformIO integration; all generated assets stay in the configured build dir."""
Import("env")
from pathlib import Path
import sys
import os

project = Path(env.subst("$PROJECT_DIR"))
sys.path.insert(0, str(project.parent / "scripts"))
from c6_asset_pack import build_pack
from c6_fonts import build_fonts

output = Path(env.subst("$BUILD_DIR")) / "c6_assets"
build_pack(project / "data" / "themes", output)
fonts = Path(env.subst("$BUILD_DIR")) / "c6_fonts"
converter = Path(os.environ.get("CODEXMETER_FONT_CONVERTER",
    r"D:\build\CodexMeter\font-tools\node_modules\lv_font_conv\lv_font_conv.js"))
build_fonts(project, fonts, converter)
libraries = Path(env.subst("$PROJECT_LIBDEPS_DIR")) / env.subst("$PIOENV")
env.Append(CPPPATH=[str(output), str(project / "src"), str(libraries), str(libraries / "lvgl")])
env.Append(FLASH_EXTRA_IMAGES=[("0x610000", str(output / "c6_assets.bin"))])
env.BuildSources(str(Path(env.subst("$BUILD_DIR")) / "c6_font_objects"), str(fonts))
