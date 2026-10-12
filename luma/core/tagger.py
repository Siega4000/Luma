"""
Встраивание обложек в MP3 как ID3v2-метаданные (ключевое требование).

Правила:
  * обложка пишется в APIC frame, тип 3 — Cover (front);
  * предпочтительный формат — JPEG; PNG допустим как промежуточный
    и конвертируется в JPEG через ffmpeg (как и webp);
  * файл обложки на диске после встраивания удаляется;
  * отсутствие обложки или ошибка конвертации не прерывают процесс.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
from pathlib import Path

from mutagen.id3 import APIC, ID3, ID3NoHeaderError

from luma.utils.ffmpeg_locator import find_ffmpeg

log = logging.getLogger("luma.tagger")

_JPEG_EXTS = {".jpg", ".jpeg"}
_KNOWN_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _run_ffmpeg(args: list[str]) -> bool:
    """Тихий запуск ffmpeg. Возвращает True при успехе."""
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW  # без мигающей консоли

    binary = find_ffmpeg()
    if binary is None:
        log.warning("ffmpeg не найден — обложка не будет сконвертирована.")
        return False
    try:
        result = subprocess.run(
            [str(binary), "-y", "-hide_banner", "-loglevel", "error", *args],
            capture_output=True,
            creationflags=creationflags,
            timeout=60,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("ffmpeg недоступен или завершился с ошибкой: %s", exc)
        return False


def _to_jpeg(image_path: Path) -> tuple[bytes, str] | None:
    """
    Возвращает (данные изображения, mime).

    JPEG отдаётся как есть; PNG/WEBP конвертируются в JPEG через ffmpeg.
    Если конвертация не удалась, PNG допускается как fallback,
    WEBP без конвертации не встраивается (плохая совместимость с DJ-софтом).
    """
    suffix = image_path.suffix.lower()

    if suffix in _JPEG_EXTS:
        return image_path.read_bytes(), "image/jpeg"

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "cover.jpg"
        # Масштабируем до максимум 1000px по большей стороне —
        # разумный размер обложки для DJ-библиотеки.
        ok = _run_ffmpeg(
            [
                "-i", str(image_path),
                "-vf", "scale='min(1000,iw)':-2",
                "-q:v", "2",
                str(out),
            ]
        )
        if ok and out.exists():
            return out.read_bytes(), "image/jpeg"

    if suffix == ".png":
        log.info("Конвертация PNG→JPEG не удалась, встраиваю PNG как есть.")
        return image_path.read_bytes(), "image/png"

    log.warning("Не удалось подготовить обложку: %s", image_path.name)
    return None


def find_thumbnail(mp3_path: Path, info: dict | None = None) -> Path | None:
    """
    Ищет файл обложки, скачанный yt-dlp.

    Сначала — по метаданным yt-dlp (thumbnails[i]['filepath']),
    затем — рядом с mp3 по совпадению имени.
    """
    if info:
        for thumb in info.get("thumbnails") or []:
            fp = thumb.get("filepath")
            if fp and Path(fp).exists():
                return Path(fp)

    stem = mp3_path.with_suffix("")
    for ext in _KNOWN_EXTS:
        candidate = stem.with_suffix(ext)
        if candidate.exists():
            return candidate
    return None


def embed_cover(mp3_path: Path, image_path: Path) -> bool:
    """Встраивает обложку в MP3 (APIC, Cover front). True при успехе."""
    prepared = _to_jpeg(image_path)
    if prepared is None:
        return False
    data, mime = prepared

    try:
        try:
            tags = ID3(str(mp3_path))
        except ID3NoHeaderError:
            tags = ID3()

        tags.delall("APIC")  # не дублируем обложки при повторной загрузке
        tags.add(
            APIC(
                encoding=3,        # UTF-8
                mime=mime,
                type=3,            # 3 = Cover (front)
                desc="Cover",
                data=data,
            )
        )
        tags.save(str(mp3_path), v2_version=3)  # ID3v2.3 — макс. совместимость
        return True
    except Exception as exc:
        log.warning("Не удалось встроить обложку в %s: %s", mp3_path.name, exc)
        return False


def cleanup_thumbnails(mp3_path: Path, info: dict | None = None) -> None:
    """Удаляет файлы обложек с диска — они не должны храниться отдельно."""
    seen: set[Path] = set()
    if info:
        for thumb in info.get("thumbnails") or []:
            fp = thumb.get("filepath")
            if fp:
                seen.add(Path(fp))
    stem = mp3_path.with_suffix("")
    for ext in _KNOWN_EXTS:
        seen.add(stem.with_suffix(ext))

    for path in seen:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass


def process_track(mp3_path: Path, info: dict | None = None) -> bool:
    """
    Полный цикл: найти обложку → встроить в MP3 → удалить файл обложки.

    Возвращает True, если обложка встроена. Отсутствие обложки —
    не ошибка: MP3 остаётся без APIC, процесс продолжается.
    """
    if not mp3_path.exists():
        log.warning("MP3 не найден для тегирования: %s", mp3_path)
        return False

    thumb = find_thumbnail(mp3_path, info)
    embedded = False
    if thumb is None:
        log.info("Обложка недоступна для «%s» — сохраняю без неё.", mp3_path.stem)
    else:
        embedded = embed_cover(mp3_path, thumb)

    cleanup_thumbnails(mp3_path, info)
    return embedded
