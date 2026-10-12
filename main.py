"""Точка входа Luma. Запуск: python main.py"""

from __future__ import annotations

import os
import sys

from luma.config import APP_NAME
from luma.core.engine_update import bootstrap
from luma.utils.ffmpeg_locator import ensure_on_path
from luma.utils.logging_setup import setup_logging


def resource_path(name: str) -> str:
    """Путь к ресурсу: работает и в разработке, и внутри exe (PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def main() -> int:
    logger = setup_logging()
    logger.info("Запуск %s", APP_NAME)

    # ВАЖНО: подключаем обновлённый движок до первого импорта yt_dlp,
    # то есть до импорта модулей UI и загрузки.
    bootstrap()

    # Портативный режим: ffmpeg.exe рядом с Luma.exe подхватывается сам.
    ffmpeg = ensure_on_path()
    logger.info("ffmpeg: %s", ffmpeg or "не найден")

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from luma.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(resource_path("luma.ico")))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
