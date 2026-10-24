"""Run packaged-app checks without Python or the source directory on PATH."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def clean_environment():
    env = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"):
        env.pop(key, None)
    windows = env.get("SystemRoot", r"C:\Windows")
    env["PATH"] = os.pathsep.join((str(Path(windows) / "System32"), windows))
    return env


def validate(binary: Path, output: Path):
    binary = binary.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = clean_environment()
    with tempfile.TemporaryDirectory(prefix="codexmeter-package-") as working:
        report = output / "runtime-self-test.json"
        process = subprocess.run([str(binary), "--self-test", str(report)], cwd=working,
                                 env=env, capture_output=True, text=True, encoding="utf-8",
                                 timeout=150, creationflags=subprocess.CREATE_NO_WINDOW)
        if report.exists():
            result = json.loads(report.read_text(encoding="utf-8"))
        else:
            result = {"ok": False, "exit_code": process.returncode,
                      "stdout": process.stdout, "stderr": process.stderr}
            report.write_text(json.dumps(result, indent=2))
        assert result["ok"] and result["compiled"], result
        assert Path(result["child_command"][0]).resolve() == binary, result
        print("Packaged GUI, subprocess, WinRT and DPAPI checks passed.", flush=True)
        for args, name in [(["devices", "list"], "devices"), (["once"], "live-usage")]:
            process = subprocess.run([str(binary), "--cli", *args], cwd=working, env=env,
                                     capture_output=True, text=True, encoding="utf-8", timeout=120,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            assert process.returncode == 0, process.stderr or process.stdout
            data = json.loads(process.stdout)
            (output / f"{name}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"Packaged {name}: passed", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    validate(args.binary, args.output)
