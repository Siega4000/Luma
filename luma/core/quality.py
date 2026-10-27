"""
Реальное качество скачанного трека.

Битрейт MP3-файла сам по себе ничего не говорит: файл 320 kbps,
перекодированный из потока 128 kbps, звучит как 128. Поэтому Luma
показывает качество источника — того, что на самом деле отдала площадка, —
а в подсказке объясняет, что стало с файлом.
"""

from __future__ import annotations

_LOSSY = {"mp3": "MP3", "opus": "Opus", "aac": "AAC", "vorbis": "Vorbis", "wmav2": "WMA"}
_LOSSLESS = {"flac": "FLAC", "alac": "ALAC", "wavpack": "WavPack"}

# С какого битрейта источник считаем «клубным» качеством
GOOD_KBPS = 256


def codec_name(codec: str | None, ext: str | None = None) -> tuple[str, bool]:
    """(человеческое имя кодека, без потерь ли он)."""
    codec = (codec or "").lower()
    ext = (ext or "").lower()
    if codec.startswith("pcm_"):
        return ("AIFF" if ext in ("aif", "aiff") or codec.endswith("be") else "WAV"), True
    if codec in _LOSSLESS:
        return _LOSSLESS[codec], True
    if codec in _LOSSY:
        return _LOSSY[codec], False
    return (codec.upper() if codec else ""), False


def describe(
    file_kbps: int | None,
    source_codec: str | None,
    source_ext: str | None,
    source_kbps: float | None,
    transcoded: bool,
) -> dict:
    """
    Возвращает {"label", "good", "tooltip"} для значка в очереди.
    label — качество источника, например «MP3 320», «Opus 130», «WAV».
    """
    name, lossless = codec_name(source_codec, source_ext)
    file_text = f"MP3 {file_kbps} kbps" if file_kbps else "MP3"

    if lossless:
        return {
            "label": name,
            "good": True,
            "tooltip": f"Источник без потерь ({name}), файл сохранён как {file_text}.",
        }

    if not transcoded and name in ("MP3", ""):
        # MP3 скопирован как есть — битрейт файла и есть битрейт источника
        kbps = file_kbps or (round(source_kbps) if source_kbps else None)
        return {
            "label": f"MP3 {kbps}" if kbps else "MP3",
            "good": bool(kbps and kbps >= GOOD_KBPS),
            "tooltip": (
                f"MP3 {kbps} kbps — файл сохранён как у источника, без перекодирования."
                if kbps else "MP3 — файл сохранён как у источника."
            ),
        }

    kbps = round(source_kbps) if source_kbps else None
    label = f"{name} {kbps}" if kbps else (name or "MP3")
    source_text = f"{name} {kbps} kbps" if kbps else (name or "неизвестного формата")
    return {
        "label": label,
        "good": bool(kbps and kbps >= GOOD_KBPS),
        "tooltip": (
            f"Источник — {source_text}, файл перекодирован в {file_text}. "
            "Качество звука остаётся на уровне источника."
        ),
    }
