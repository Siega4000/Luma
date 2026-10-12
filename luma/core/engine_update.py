"""
Автообновление движка загрузки (yt-dlp).

Внутри собранного exe yt-dlp обновить нельзя — он упакован намертво.
Поэтому свежая версия хранится отдельным wheel-архивом в
%APPDATA%/Luma/engine/ и подключается в sys.path при запуске:
yt-dlp — чистый Python, поэтому импортируется прямо из архива.

bootstrap() вызывается в самом начале main.py — ДО первого импорта
yt_dlp, иначе подхватится встроенная версия.

Модуль использует только стандартную библиотеку: никаких новых
зависимостей и никакого pip на машине пользователя.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import urllib.request
from pathlib import Path

from luma.config import app_data_dir

log = logging.getLogger("luma.engine")

PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"
USER_AGENT = "Luma/1.0 (+desktop app)"
WHEEL_GLOB = "yt_dlp-*-py3-none-any.whl"


def engine_dir() -> Path:
    path = app_data_dir() / "engine"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _version_key(text: str) -> tuple:
    """Версии yt-dlp вида 2026.8.19 — сравниваем по числам."""
    return tuple(int(part) for part in re.findall(r"\d+", text))


def installed_wheel() -> Path | None:
    """Самый свежий скачанный wheel, если он есть."""
    wheels = sorted(
        engine_dir().glob(WHEEL_GLOB),
        key=lambda p: _version_key(p.stem),
    )
    return wheels[-1] if wheels else None


def bootstrap() -> None:
    """Подключает скачанный движок вместо встроенного. Вызывать до import yt_dlp."""
    wheel = installed_wheel()
    if wheel is None:
        return
    if "yt_dlp" in sys.modules:
        log.warning("yt_dlp уже импортирован — обновление вступит в силу после перезапуска.")
        return
    sys.path.insert(0, str(wheel))
    log.info("Движок загрузки подключён из %s", wheel.name)


def active_version() -> str:
    """Версия движка, работающая в этом запуске."""
    try:
        import yt_dlp

        return str(yt_dlp.version.__version__)
    except Exception:
        return "неизвестно"


def latest_version() -> tuple[str, str]:
    """Последняя версия в PyPI: (версия, ссылка на wheel)."""
    request = urllib.request.Request(PYPI_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)

    version = data["info"]["version"]
    for file_info in data["urls"]:
        if file_info["filename"].endswith("-py3-none-any.whl"):
            return version, file_info["url"]
    raise RuntimeError("В PyPI не найден подходящий файл движка")


def is_newer(latest: str, current: str) -> bool:
    try:
        return _version_key(latest) > _version_key(current)
    except Exception:
        return latest.replace("0", "") != current.replace("0", "")


def download(url: str) -> Path:
    """Скачивает wheel в %APPDATA%/Luma/engine и убирает старые версии."""
    target = engine_dir() / url.rsplit("/", 1)[-1]
    temp = target.with_suffix(target.suffix + ".part")

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response, temp.open("wb") as out:
        while chunk := response.read(262_144):
            out.write(chunk)
    temp.replace(target)

    for old in engine_dir().glob(WHEEL_GLOB):
        if old != target:
            try:
                old.unlink()
            except OSError:
                pass  # файл может быть занят текущим запуском — удалится позже

    return target


def check_and_update() -> dict:
    """
    Проверяет и при необходимости скачивает обновление.

    Возвращает {'status': ..., 'current': ..., 'latest': ...}, где status —
    один из: 'updated' (скачано, нужен перезапуск), 'current' (уже свежий),
    'error' (с текстом в 'message').
    """
    current = active_version()
    try:
        latest, url = latest_version()
    except Exception as exc:
        return {"status": "error", "message": str(exc), "current": current}

    if not is_newer(latest, current):
        return {"status": "current", "current": current, "latest": latest}

    try:
        download(url)
    except Exception as exc:
        return {"status": "error", "message": str(exc), "current": current}

    return {"status": "updated", "current": current, "latest": latest}
