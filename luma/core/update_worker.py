"""Фоновая проверка обновлений движка — чтобы интерфейс не подвисал."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from luma.core import engine_update


class EngineUpdateWorker(QThread):
    """Проверяет PyPI и при необходимости скачивает свежий yt-dlp."""

    finished_result = Signal(dict)

    def __init__(self, silent: bool = False) -> None:
        super().__init__()
        self.silent = silent  # автопроверка при старте — молчим, если всё свежее

    def run(self) -> None:
        result = engine_update.check_and_update()
        result["silent"] = self.silent
        self.finished_result.emit(result)
