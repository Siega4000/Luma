"""
Движок загрузки Luma поверх yt-dlp.

Отвечает за:
  * скачивание аудио из публичных источников (YouTube, SoundCloud, Bandcamp);
  * конвертацию в MP3 через ffmpeg;
  * запись базовых ID3-тегов (title/artist) через ffmpeg-metadata;
  * встраивание обложек через mutagen (см. tagger.py);
  * структуру хранения: треки — в корень библиотеки,
    плейлисты — в подпапку с названием плейлиста;
  * реестр скачанного (download archive) для докачки плейлистов;
  * события для таблицы треков: старт, прогресс, завершение;
  * поддержку отмены и устойчивость к ошибкам отдельных треков.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yt_dlp
from yt_dlp.postprocessor import PostProcessor
from yt_dlp.utils import DownloadCancelled, DownloadError, sanitize_filename

from luma.core import tagger
from luma.utils.ffmpeg_locator import find_ffmpeg

log = logging.getLogger("luma.downloader")

ProgressCallback = Callable[[dict], None]
TrackStartCallback = Callable[[dict], None]
LogCallback = Callable[[str, str], None]  # (message, level)


@dataclass
class TrackResult:
    track_id: str
    title: str
    filepath: Path | None
    cover_embedded: bool
    duration: float | None = None
    url: str | None = None
    artist: str = ""
    source: str = ""
    thumbnail: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class UrlResult:
    url: str
    playlist_title: str | None = None
    tracks: list[TrackResult] = field(default_factory=list)
    error: str | None = None


def _meta(info: dict) -> dict:
    """Единый разбор метаданных трека из info_dict yt-dlp."""
    thumbnails = info.get("thumbnails") or []
    thumbnail = info.get("thumbnail") or ""
    if not thumbnail and thumbnails:
        # Берём средний по размеру вариант — его быстро отдаёт CDN.
        thumbnail = (thumbnails[len(thumbnails) // 2] or {}).get("url", "")
    return {
        "id": str(info.get("id") or ""),
        "title": info.get("title") or "Без названия",
        "artist": info.get("artist") or info.get("uploader") or info.get("creator") or "",
        "duration": info.get("duration"),
        "url": info.get("webpage_url") or info.get("original_url") or "",
        "source": info.get("extractor_key") or info.get("extractor") or "",
        "thumbnail": thumbnail,
    }


class _ThumbnailFilterPP(PostProcessor):
    """
    Убирает из списка обложек вариант «original» (полноразмерный исходник):
    у SoundCloud он раздаётся с отдельного медленного хранилища и часто
    обрывается (таймауты, сброс соединения). Остальные размеры — например,
    t500x500 — грузятся стабильно и для DJ-библиотеки достаточны.
    Работает только если есть альтернативные варианты.
    """

    def run(self, info):  # noqa: D102 (интерфейс yt-dlp)
        thumbs = info.get("thumbnails")
        if thumbs and len(thumbs) > 1:
            filtered = [t for t in thumbs if t.get("id") != "original"]
            if filtered:
                info["thumbnails"] = filtered
        return [], info


class _CoverEmbedPP(PostProcessor):
    """
    Финальный постпроцессор yt-dlp: после конвертации в MP3
    встраивает обложку, удаляет её файл с диска и сообщает движку
    полные данные о готовом треке.
    """

    def __init__(self, engine: "DownloadEngine") -> None:
        super().__init__()
        self._engine = engine

    def run(self, info):  # noqa: D102 (интерфейс yt-dlp)
        filepath = info.get("filepath")
        embedded = False
        if filepath:
            embedded = tagger.process_track(Path(filepath), info)
        data = _meta(info)
        self._engine._register_track(
            TrackResult(
                track_id=data["id"],
                title=data["title"],
                filepath=Path(filepath) if filepath else None,
                cover_embedded=embedded,
                duration=data["duration"],
                url=data["url"],
                artist=data["artist"],
                source=data["source"],
                thumbnail=data["thumbnail"],
            )
        )
        return [], info


class DownloadEngine:
    """Последовательная обработка очереди URL с возможностью отмены."""

    def __init__(
        self,
        output_dir: Path,
        bitrate: str = "320",
        on_progress: ProgressCallback | None = None,
        on_log: LogCallback | None = None,
        on_track: Callable[[TrackResult], None] | None = None,
        on_track_start: TrackStartCallback | None = None,
        on_resolved: Callable[[dict], None] | None = None,
        archive_path: Path | None = None,
        force: bool = False,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.bitrate = bitrate
        self.archive_path = archive_path
        self.force = force
        self._on_progress = on_progress or (lambda _: None)
        self._on_log = on_log or (lambda *_: None)
        self._on_track = on_track or (lambda _: None)
        self._on_track_start = on_track_start or (lambda _: None)
        self._on_resolved = on_resolved or (lambda _: None)
        self._cancelled = False
        self._current_tracks: list[TrackResult] = []
        self._started_ids: set[str] = set()

    # ------------------------------------------------------------------ API

    def cancel(self) -> None:
        """Запрос отмены: текущая загрузка прерывается, очередь останавливается."""
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @staticmethod
    def ffmpeg_available() -> bool:
        return find_ffmpeg() is not None

    def process_url(self, url: str) -> UrlResult:
        """Скачивает один URL (трек или плейлист). Ошибки не выбрасываются наружу."""
        result = UrlResult(url=url)
        self._current_tracks = []

        try:
            probe = self._probe(url)
        except DownloadCancelled:
            raise
        except Exception as exc:
            result.error = self._short_error(exc)
            return result

        # Контент распознан — UI показывает карточки до начала загрузки.
        self._on_resolved(
            {
                "url": url,
                "is_playlist": probe["is_playlist"],
                "playlist_title": probe.get("title"),
                "entries": probe.get("entries") or [],
                "source": probe.get("source", ""),
            }
        )

        target_dir = self.output_dir
        if probe["is_playlist"] and probe["title"]:
            result.playlist_title = probe["title"]
            target_dir = self.output_dir / sanitize_filename(probe["title"])
            self._on_log(
                f"Плейлист «{probe['title']}» ({probe['count'] or '?'} трек(ов)) → "
                f"папка {target_dir.name}/",
                "info",
            )

        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            with yt_dlp.YoutubeDL(self._build_options(target_dir)) as ydl:
                ydl.add_post_processor(_ThumbnailFilterPP(), when="pre_process")
                ydl.add_post_processor(_CoverEmbedPP(self), when="post_process")
                ydl.download([url])
        except DownloadCancelled:
            result.tracks = self._current_tracks
            raise
        except DownloadError as exc:
            # Частичные ошибки внутри плейлиста уже проигнорированы
            # (ignoreerrors=True); сюда попадают только фатальные.
            result.error = self._short_error(exc)
        except Exception as exc:
            result.error = self._short_error(exc)

        result.tracks = self._current_tracks
        return result

    # ------------------------------------------------------------- internals

    def _register_track(self, track: TrackResult) -> None:
        self._current_tracks.append(track)
        self._on_track(track)
        cover_note = "обложка встроена" if track.cover_embedded else "без обложки"
        self._on_log(f"Готово: {track.title}  ·  {cover_note}", "success")

    def _probe(self, url: str) -> dict:
        """Быстрая проверка: одиночный трек или плейлист."""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "noplaylist": False,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        entries = info.get("entries")
        is_playlist = info.get("_type") == "playlist" or entries is not None

        items: list[dict] = []
        if entries is not None:
            try:
                items = [_meta(e) for e in entries if isinstance(e, dict)]
            except TypeError:
                items = []
        else:
            items = [_meta(info)]

        return {
            "is_playlist": is_playlist,
            "title": info.get("title") if is_playlist else None,
            "count": len(items) if items else info.get("playlist_count"),
            "entries": items,
            "source": info.get("extractor_key") or info.get("extractor") or "",
        }

    def _build_options(self, target_dir: Path) -> dict:
        options = {
            # Предпочитаем прогрессивный поток (один файл) фрагментному HLS:
            # на SoundCloud HLS-фрагменты часто обрываются при нестабильной сети.
            "format": "bestaudio[protocol!*=m3u8]/bestaudio/best",
            "outtmpl": str(target_dir / "%(title)s.%(ext)s"),
            "windowsfilenames": True,
            "ignoreerrors": True,          # ошибка трека не рушит плейлист
            "noplaylist": False,
            "writethumbnail": True,        # обложка нужна как временный файл
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "retries": 10,
            "fragment_retries": 10,
            "socket_timeout": 60,
            "source_address": "0.0.0.0",   # принудительный IPv4 (лечит WinError 10054)
            "progress_hooks": [self._progress_hook],
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": self.bitrate,
                },
                {"key": "FFmpegMetadata"},  # title/artist → ID3
            ],
            "logger": _YdlLogger(self._on_log),
        }
        if self.archive_path is not None:
            # Реестр скачанного: повторная загрузка того же плейлиста
            # докачивает только новые треки.
            options["download_archive"] = str(self.archive_path)
        if self.force:
            # Точечная перекачка: игнорируем существующий файл.
            options["overwrites"] = True
        return options

    def _progress_hook(self, d: dict) -> None:
        if self._cancelled:
            raise DownloadCancelled("Загрузка отменена пользователем")

        info = d.get("info_dict") or {}
        track_id = str(info.get("id") or "")

        if track_id and track_id not in self._started_ids:
            self._started_ids.add(track_id)
            self._on_track_start(_meta(info))

        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            percent = int(done * 100 / total) if total else 0
            self._on_progress(
                {
                    "id": track_id,
                    "percent": percent,
                    "title": info.get("title", ""),
                    "speed": d.get("_speed_str", "").strip(),
                }
            )
        elif d.get("status") == "finished":
            self._on_progress(
                {"id": track_id, "percent": 100, "title": "", "speed": ""}
            )

    @staticmethod
    def _short_error(exc: Exception) -> str:
        text = str(exc).replace("ERROR: ", "").strip()
        return text.splitlines()[0][:200] if text else exc.__class__.__name__


class _YdlLogger:
    """Мост логов yt-dlp → GUI-консоль и лог-файл."""

    def __init__(self, on_log: LogCallback) -> None:
        self._on_log = on_log

    def debug(self, msg: str) -> None:
        log.debug(msg)

    def info(self, msg: str) -> None:
        log.info(msg)

    def warning(self, msg: str) -> None:
        log.warning(msg)
        self._on_log(msg.replace("WARNING: ", ""), "warning")

    def error(self, msg: str) -> None:
        log.error(msg)
        self._on_log(msg.replace("ERROR: ", ""), "error")
