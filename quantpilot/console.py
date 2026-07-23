"""Console helpers for cross-platform CLI scripts."""

from __future__ import annotations

import sys


def configure_stdio() -> None:
    """Use UTF-8 for stdout/stderr when the runtime supports it.

    Avoids ``UnicodeEncodeError`` on Windows consoles still using cp949.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
