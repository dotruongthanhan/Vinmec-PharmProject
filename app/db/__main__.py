"""Điểm vào python -m app.db."""

import sys

from app.db.cli import main

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")

raise SystemExit(main())
