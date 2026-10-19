"""Application logging. Never log secrets or full resume content."""

from __future__ import annotations

import logging
import os

_CONFIGURED = False


def get_logger(name: str = "resumeai") -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        root = logging.getLogger("resumeai")
        root.addHandler(handler)
        root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
        root.propagate = False
        _CONFIGURED = True
    if name != "resumeai" and not name.startswith("resumeai."):
        name = f"resumeai.{name}"
    return logging.getLogger(name)
