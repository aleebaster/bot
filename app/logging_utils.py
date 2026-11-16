"""Logging configuration. Tokens and secrets are never logged."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO", log_to_file: bool = True) -> logging.Logger:
    """Configure root logging with console and optional file output."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    log_fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    formatter = logging.Formatter(log_fmt)

    root = logging.getLogger()
    root.setLevel(numeric)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_to_file:
        Path("logs").mkdir(exist_ok=True)
        file_handler = logging.FileHandler("logs/bot.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    logging.getLogger("ccxt").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    return root
