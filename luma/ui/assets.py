"""
Генерация растровых ресурсов интерфейса.

Qt не умеет брать иконки для QSS из памяти, поэтому галочку чекбокса
один раз рисуем в файл в кэше приложения и подставляем путь в стили.
"""

from __future__ import annotations

import logging

from luma.config import app_data_dir
from luma.ui import icons
from luma.ui.theme import COLORS

log = logging.getLogger("luma.assets")


def check_icon_path() -> str:
    """Путь к PNG с галочкой для QCheckBox. Пустая строка при неудаче."""
    try:
        cache = app_data_dir() / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        target = cache / "check.png"
        pixmap = icons.pixmap("check", 12, COLORS["on_accent"], width=2.4)
        if pixmap.isNull() or not pixmap.save(str(target), "PNG"):
            return ""
        return str(target)
    except Exception as exc:
        log.debug("Не удалось создать иконку чекбокса: %s", exc)
        return ""
