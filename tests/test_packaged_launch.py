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
