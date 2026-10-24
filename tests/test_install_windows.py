import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_windows_hook_installer_preserves_existing_hooks_and_quotes_spaces(tmp_path):
    target = tmp_path / "hooks.json"
    existing = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "unrelated-tool"}]}]}}
    target.write_text(json.dumps(existing), encoding="utf-8")
    args = [sys.executable, str(ROOT / "scripts/install_hook.py"),
            "--hooks-json", str(target), "--event", "Stop",
            "--windows-python", r"D:\build tools\python.exe", "--script", r"E:\My Projects\stop.py"]
    for _ in range(2):
        result = subprocess.run(args, capture_output=True, text=True, timeout=5, env=os.environ)
        assert result.returncode == 0, result.stderr
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert len(saved["hooks"]["Stop"]) == 2
    assert saved["hooks"]["Stop"][0] == existing["hooks"]["Stop"][0]
    hook = saved["hooks"]["Stop"][1]["hooks"][0]
    assert hook["commandWindows"] == '"D:\\build tools\\python.exe" "E:\\My Projects\\stop.py"'
    assert len(list(tmp_path.glob("hooks.json.bak.*"))) == 1
