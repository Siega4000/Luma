"""
Построение волновой формы готового MP3.

После загрузки файл лежит на диске, поэтому можно прочитать реальную
огибающую амплитуды: видно вступление, брейк и основную часть трека.

Волна цветная, как в DJ-софте: каждый столбик окрашен по частотному
составу этого участка — низ (бас и бочка), середина (вокал, синтезаторы)
и верх (хэты, перкуссия). Для разделения по полосам используется ffmpeg,
который уже нужен программе для конвертации; дополнительных библиотек
не требуется.

Разбор трёхминутного трека занимает около двух секунд, поэтому его
выполняет фоновый поток (см. wave_worker.py).
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from luma.utils.ffmpeg_locator import find_ffmpeg

log = logging.getLogger("luma.waveform")

BARS = 320             # плотность волны: тонкие полосы, как в DJ-софте
_SAMPLE_RATE = 22050   # нужно не меньше 16 кГц, иначе верхней полосы
                       # просто нет в данных (предел — половина частоты)
_TIMEOUT = 40

# Полосы: низ / середина / верх. Частоты подобраны так, чтобы бочка
# и бас попадали в низ, а хэты и перкуссия — в верх.
# poles=2 и повтор фильтра дают более крутой срез: без этого низ
# «протекает» в соседние полосы и цвет получается одинаковым.
_BANDS = (
    ("low", ["lowpass=f=200:poles=2", "lowpass=f=200:poles=2"]),
    ("mid", ["highpass=f=250:poles=2", "highpass=f=250:poles=2",
             "lowpass=f=2500:poles=2", "lowpass=f=2500:poles=2"]),
    ("high", ["highpass=f=2500:poles=2", "highpass=f=2500:poles=2"]),
)


# Каналы выравниваются по восприятию: по чистой энергии бас всегда
# подавил бы остальные, и волна вышла бы сплошь красной.
_WEIGHTS = {"low": 1.0, "mid": 1.5, "high": 7.0}


@dataclass
class WaveBar:
    """Один столбик волны: высота и доли частотных полос."""

    level: float   # 0..1 — общая громкость участка
    low: float     # 0..1 — доля низа
    mid: float     # 0..1 — доля середины
    high: float    # 0..1 — доля верха


def _decode(path: Path, filters: list[str] | None) -> bytes | None:
    """Прогоняет файл через ffmpeg и отдаёт моно-отсчёты (unsigned 8 bit)."""
    binary = find_ffmpeg()
    if binary is None:
        return None

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    command = [str(binary), "-v", "error", "-i", str(path), "-ac", "1"]
    if filters:
        command += ["-af", ",".join(filters)]
    command += ["-ar", str(_SAMPLE_RATE), "-f", "u8", "-"]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            creationflags=creationflags,
            timeout=_TIMEOUT,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        return result.stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.debug("Не удалось разобрать аудио (%s): %s", path.name, exc)
        return None


def _peaks(data: bytes, bars: int) -> list[float] | None:
    """Пики громкости по участкам: 128 — тишина для unsigned 8 bit."""
    if len(data) < bars:
        return None
    chunk = len(data) // bars
    return [
        max(abs(sample - 128) for sample in data[i * chunk:(i + 1) * chunk]) / 128
        for i in range(bars)
    ]


def _energy(data: bytes, bars: int) -> list[float] | None:
    """
    Средняя энергия участков (RMS).

    Для долей частотных полос важна именно средняя энергия: пик реагирует
    на одиночный щелчок и завышает долю полосы, которой в участке почти нет.
    """
    if len(data) < bars:
        return None
    chunk = len(data) // bars
    result = []
    for index in range(bars):
        window = data[index * chunk:(index + 1) * chunk]
        total = sum((sample - 128) ** 2 for sample in window)
        result.append((total / len(window)) ** 0.5 / 128)
    return result


def build(path: Path, bars: int = BARS) -> list[WaveBar] | None:
    """
    Возвращает список столбиков волны или None, если файл не читается.

    Отсутствие волны не считается ошибкой: интерфейс просто её не покажет.
    """
    path = Path(path)
    overall = _decode(path, None)
    if not overall:
        return None

    total = _energy(overall, bars)
    if total is None:
        return None

    # Разбираем те же участки по частотным полосам
    band_peaks: dict[str, list[float]] = {}
    for name, filters in _BANDS:
        data = _decode(path, filters)
        values = _energy(data, bars) if data else None
        band_peaks[name] = values or [0.0] * bars

    loudest = max(total) or 1.0
    result: list[WaveBar] = []
    for index in range(bars):
        # У сведённого трека разница между тихим и громким невелика,
        # поэтому растягиваем динамику: тихое опускаем, громкое поднимаем.
        raw = total[index] / loudest
        level = min(1.0, max(0.04, raw ** 1.7))

        # Ухо чувствительнее к середине и верху, а по чистой энергии бас
        # всегда подавляет остальное — волна вышла бы целиком синей.
        # Поэтому полосы взвешиваются, как это делает DJ-софт.
        low = band_peaks["low"][index] * _WEIGHTS["low"]
        mid = band_peaks["mid"][index] * _WEIGHTS["mid"]
        high = band_peaks["high"][index] * _WEIGHTS["high"]

        # Каждая полоса управляет своим каналом цвета: низ → R, середина → G,
        # верх → B. Масштаб общий для всего трека, а не для каждой полосы:
        # иначе тихие участки раскрашиваются так же ярко, как громкие,
        # и волна превращается в набор чистых «светофорных» цветов.
        result.append(WaveBar(level=level, low=low, mid=mid, high=high))

    # Общая нормировка каналов по всему треку
    peak = max(
        max(bar.low for bar in result),
        max(bar.mid for bar in result),
        max(bar.high for bar in result),
    ) or 1.0
    for bar in result:
        bar.low = min(1.0, bar.low / peak)
        bar.mid = min(1.0, bar.mid / peak)
        bar.high = min(1.0, bar.high / peak)

    return result
