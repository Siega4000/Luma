"""
Поиск ffmpeg для портативного режима.

Порядок поиска:
  1. рядом с exe (или с main.py в режиме разработки)
  2. подпапки bin/ и ffmpeg/bin/ рядом с exe
  3. системный PATH

Благодаря этому Luma можно отдать одним архивом: положить
ffmpeg.exe рядом с Luma.exe — и ничего устанавливать не нужно.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_EXE_NAMES = ("ffmpeg.exe", "ffmpeg")


def app_dir() -> Path:
    """Папка, в которой лежит запущенный exe (или проект при разработке)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def find_ffmpeg() -> Path | None:
    """Путь к ffmpeg или None, если не найден."""
    base = app_dir()
    candidates = [base, base / "bin", base / "ffmpeg" / "bin"]
    for folder in candidates:
        for name in _EXE_NAMES:
            candidate = folder / name
            if candidate.is_file():
                return candidate

    found = shutil.which("ffmpeg")
    return Path(found) if found else None


def ensure_on_path() -> Path | None:
    """
    Добавляет папку с локальным ffmpeg в PATH процесса.

    yt-dlp и mutagen-тэггер вызывают ffmpeg как внешнюю команду,
    поэтому достаточно расширить PATH текущего процесса —
    системные настройки пользователя не трогаются.
    """
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        return None

    folder = str(ffmpeg.parent)
    current = os.environ.get("PATH", "")
    if folder not in current.split(os.pathsep):
        os.environ["PATH"] = folder + os.pathsep + current
    return ffmpeg
