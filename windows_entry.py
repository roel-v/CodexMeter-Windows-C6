"""Nuitka entry point; avoid a filename matching the codexmeter package on Windows."""
from codexmeter.standalone import main

if __name__ == "__main__":
    raise SystemExit(main())
