"""
Конфигурация приложения Luma.

Хранит настройки в JSON-файле в директории пользователя
(%APPDATA%/Luma на Windows) и предоставляет пути по умолчанию.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_NAME = "Luma"
APP_VERSION = "1.0.0"


def app_data_dir() -> Path:
    """Директория для настроек и лог-файлов приложения."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_download_dir() -> Path:
    """Папка сохранения по умолчанию: Documents/Luma."""
    documents = Path.home() / "Documents"
    if sys.platform == "win32":
        # Пытаемся получить реальный путь к "Документам" через реестр
        # (на случай перемещённой папки Documents).
        try:
            import ctypes.wintypes

            CSIDL_PERSONAL = 5  # My Documents
            SHGFP_TYPE_CURRENT = 0
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(
                None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf
            )
            if buf.value:
                documents = Path(buf.value)
        except Exception:
            pass
    return documents / APP_NAME


class Settings:
    """Простое JSON-хранилище пользовательских настроек."""

    def __init__(self) -> None:
        self._path = app_data_dir() / "settings.json"
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            self._data = {}

    def save(self) -> None:
        try:
            self._path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    @property
    def download_dir(self) -> Path:
        raw = self._data.get("download_dir")
        if raw:
            return Path(raw)
        return default_download_dir()

    @download_dir.setter
    def download_dir(self, value: Path | str) -> None:
        self._data["download_dir"] = str(value)
        self.save()

    @property
    def audio_bitrate(self) -> str:
        """Битрейт MP3 (kbps) — по умолчанию 320 для DJ-качества."""
        return str(self._data.get("audio_bitrate", "320"))

    @property
    def auto_update_engine(self) -> bool:
        """Проверять обновления движка загрузки при запуске."""
        return bool(self._data.get("auto_update_engine", True))

    @auto_update_engine.setter
    def auto_update_engine(self, value: bool) -> None:
        self._data["auto_update_engine"] = bool(value)
        self.save()

    @property
    def skip_downloaded(self) -> bool:
        """Пропускать треки, уже скачанные ранее (реестр download archive)."""
        return bool(self._data.get("skip_downloaded", True))

    @skip_downloaded.setter
    def skip_downloaded(self, value: bool) -> None:
        self._data["skip_downloaded"] = bool(value)
        self.save()


def archive_file() -> Path:
    """Файл-реестр скачанных треков (для пропуска дубликатов)."""
    return app_data_dir() / "downloaded.txt"
