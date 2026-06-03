from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import AppConfig


SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD")


def redact(value: object) -> object:
    if not isinstance(value, str):
        return value
    upper = value.upper()
    if any(marker in upper for marker in SECRET_MARKERS):
        return "[redacted]"
    return value


def setup_logging(config: AppConfig) -> logging.Logger:
    logger = logging.getLogger("ospilot")
    logger.setLevel(logging.DEBUG if config.privacy.debug_mode else logging.INFO)
    logger.handlers.clear()

    handler = RotatingFileHandler(config.paths.log_file, maxBytes=1_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
