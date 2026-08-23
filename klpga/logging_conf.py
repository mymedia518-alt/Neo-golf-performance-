"""Logging setup shared by every CLI entry point."""
from __future__ import annotations

import logging
import logging.handlers

from . import config


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger("klpga")
    if root.handlers:
        return
    root.setLevel(level)

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        config.LOG_DIR / "klpga.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)
