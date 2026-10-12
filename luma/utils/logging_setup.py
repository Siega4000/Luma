"""Настройка логирования Luma: файл + перехват в GUI-консоль."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from luma.config import app_data_dir

LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(message)s"


def setup_logging() -> logging.Logger:
    """Возвращает корневой логгер приложения с файловым хендлером."""
    logger = logging.getLogger("luma")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    log_file = app_data_dir() / "luma.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)

    return logger
