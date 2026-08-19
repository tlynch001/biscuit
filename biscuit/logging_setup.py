"""Logging configuration.

Every run writes a log file under ``log_dir`` in addition to console
output, so a failed or surprising render can be traced without rerunning
the pipeline.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def configure_logging(log_dir: str | Path, story_id: str, *, verbose: bool = False) -> Path:
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    log_path = log_dir_path / f"biscuit-{story_id}.log"

    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return log_path
