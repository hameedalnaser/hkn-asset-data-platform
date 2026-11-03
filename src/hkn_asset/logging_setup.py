"""Logging configuration shared across pipeline and API.

JD standard: pipelines must be "logged" so that every run is traceable and
data-quality issues can be investigated. One place sets format + level.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from hkn_asset.config import PROJECT_ROOT

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO, to_file: bool = True) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if to_file:
        logs_dir = PROJECT_ROOT / "logs"
        logs_dir.mkdir(exist_ok=True)
        handlers.append(logging.FileHandler(logs_dir / "pipeline.log"))
    logging.basicConfig(level=level, format=_LOG_FORMAT, handlers=handlers)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
