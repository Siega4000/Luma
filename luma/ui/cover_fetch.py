"""
Фоновая подгрузка обложек для карточек очереди.

Обложка берётся по ссылке, которую отдаёт yt-dlp вместе с метаданными,
чтобы карточка выглядела как элемент музыкального приложения ещё до
окончания загрузки. Готовый MP3 позже отдаёт обложку из ID3-тега.

Работает в отдельном потоке: интерфейс не ждёт сеть.
"""

from __future__ import annotations

import logging
import queue
import urllib.request

from PySide6.QtCore import QThread, Signal

log = logging.getLogger("luma.covers")

_TIMEOUT = 12
_MAX_BYTES = 4_000_000


class CoverFetcher(QThread):
    """Очередь запросов «ключ → ссылка на обложку»."""

    cover_ready = Signal(str, bytes)  # ключ карточки, данные изображения

    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue[tuple[str, str] | None] = queue.Queue()
        self._seen: set[str] = set()

    def request(self, key: str, url: str) -> None:
        if not key or not url or key in self._seen:
            return
        self._seen.add(key)
        self._queue.put((key, url))

    def stop(self) -> None:
        self._queue.put(None)

    def run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            key, url = item
            try:
                request = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0 Luma"}
                )
                with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
                    data = response.read(_MAX_BYTES)
                if data:
                    self.cover_ready.emit(key, data)
            except Exception as exc:
                log.debug("Обложка не загрузилась (%s): %s", url, exc)
