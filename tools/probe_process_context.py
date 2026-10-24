"""One-shot launch investigation; records process context and exits (no restart)."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codexmeter.diagnostics import windows_process_context

Path(sys.argv[1]).write_text(json.dumps({"pid": os.getpid(), "parent_pid": os.getppid(),
                                      **windows_process_context()}, indent=2), encoding="utf-8")
