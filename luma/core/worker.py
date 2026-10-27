"""
Фоновый поток загрузки (Qt): очередь URL → сигналы прогресса в UI.

UI полностью отделён от логики: worker знает только про DownloadEngine
и общается с окном исключительно через сигналы.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from yt_dlp.utils import DownloadCancelled

from luma.core.downloader import DownloadEngine

log = logging.getLogger("luma.worker")


class DownloadWorker(QThread):
    """Обрабатывает список URL последовательно; ошибка одного не рушит очередь."""

    log_message = Signal(str, str)      # текст, уровень: info/success/warning/error
    content_resolved = Signal(dict)     # распознанный контент: плейлист и его треки
    track_started = Signal(dict)        # {id, title, artist, duration, url, source, thumbnail}
    track_progress = Signal(str, int, str, str)  # id, процент, название, скорость
    track_completed = Signal(dict)      # {id, title, filepath, cover_embedded, duration, url}
    url_failed = Signal(str, str)       # url, текст ошибки
    queue_progress = Signal(int, int)   # выполнено URL, всего URL
    status_changed = Signal(str)        # человекочитаемый статус
    finished_summary = Signal(dict)     # итоги очереди

    def __init__(
        self,
        urls: list[str],
        output_dir: Path,
        bitrate: str,
        archive_path: Path | None = None,
        force: bool = False,
        clean_titles: bool = True,
        strip_catalog: bool = True,
        force_320: bool = False,
    ) -> None:
        super().__init__()
        self._urls = urls
        self._engine = DownloadEngine(
            output_dir=output_dir,
            bitrate=bitrate,
            on_progress=self._emit_progress,
            on_log=self.log_message.emit,
            on_track=self._emit_track,
            on_track_start=self.track_started.emit,
            on_resolved=self._emit_resolved,
            archive_path=archive_path,
            force=force,
            clean_titles=clean_titles,
            strip_catalog=strip_catalog,
            force_320=force_320,
        )

    # ------------------------------------------------------------------ API

    def cancel(self) -> None:
        self._engine.cancel()
        self.status_changed.emit("Отмена…")

    # ------------------------------------------------------------------ run

    def run(self) -> None:
        total = len(self._urls)
        done_tracks = 0
        covers = 0
        failed_urls: list[str] = []
        cancelled = False

        self.queue_progress.emit(0, total)

        for index, url in enumerate(self._urls, start=1):
            if self._engine.cancelled:
                cancelled = True
                break

            # Сначала движок проверяет ссылку и забирает метаданные,
            # и только потом начинается собственно загрузка.
            self.status_changed.emit(f"Проверка ссылки {index} из {total}")
            self.log_message.emit(f"[{index}/{total}] {url}", "info")

            try:
                result = self._engine.process_url(url)
            except DownloadCancelled:
                cancelled = True
                self.log_message.emit("Загрузка отменена пользователем.", "warning")
                break
            except Exception as exc:  # страховка: очередь не должна падать
                log.exception("Необработанная ошибка для %s", url)
                self.log_message.emit(f"Ошибка: {exc}", "error")
                failed_urls.append(url)
                self.url_failed.emit(url, str(exc))
                self.queue_progress.emit(index, total)
                continue

            if result.error:
                failed_urls.append(url)
                self.url_failed.emit(url, result.error)
                self.log_message.emit(f"Не удалось обработать URL: {result.error}", "error")
            done_tracks += sum(1 for t in result.tracks if t.ok)
            covers += sum(1 for t in result.tracks if t.cover_embedded)

            self.queue_progress.emit(index, total)

        self.finished_summary.emit(
            {
                "cancelled": cancelled,
                "urls_total": total,
                "urls_failed": failed_urls,
                "tracks_done": done_tracks,
                "covers_embedded": covers,
            }
        )

    # ------------------------------------------------------------- internals

    def _emit_resolved(self, data: dict) -> None:
        """Ссылка распознана — сообщаем о переходе к загрузке."""
        self.content_resolved.emit(data)
        count = len(data.get("entries") or [])
        self.status_changed.emit(f"Загрузка · {count}" if count else "Загрузка")

    def _emit_progress(self, data: dict) -> None:
        self.track_progress.emit(
            data.get("id", ""),
            data.get("percent", 0),
            data.get("title", ""),
            data.get("speed", ""),
        )

    def _emit_track(self, track) -> None:
        self.track_completed.emit(
            {
                "id": track.track_id,
                "title": track.title,
                "filepath": str(track.filepath) if track.filepath else "",
                "cover_embedded": track.cover_embedded,
                "duration": track.duration,
                "url": track.url or "",
                "artist": track.artist,
                "source": track.source,
                "thumbnail": track.thumbnail,
                "quality": track.quality or {},
            }
        )
