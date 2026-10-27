"""Проверка чистки названий: python -m pytest tests"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Консоль Windows по умолчанию не выводит кириллицу (cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from luma.core.names import clean_title  # noqa: E402

CASES = [
    # промо-пометки
    ("Onefalov - This Turn [FREE DL]", "Onefalov - This Turn"),
    ("[FREE DOWNLOAD] Artist - Track (Original Mix)", "Artist - Track (Original Mix)"),
    ("Artist - Track (Free Download)", "Artist - Track"),
    ("Artist - Track [FREE DL in description]", "Artist - Track"),
    ("Artist - Track (Click Buy For Free Download)", "Artist - Track"),
    ("Artist - Track [BUY = FREE DL]", "Artist - Track"),
    ("Artist - Track | FREE DL", "Artist - Track"),
    ("Artist - Track *FREE DOWNLOAD*", "Artist - Track"),
    ("Artist - Track FREE DL", "Artist - Track"),
    ("Artist - Track (Extended Mix) FREE DOWNLOAD", "Artist - Track (Extended Mix)"),
    ("Artist - Track [OUT NOW ON DRUMCODE]", "Artist - Track"),
    ("Artist - Track (Out Now)", "Artist - Track"),
    ("Artist - Track (Bob Remix) | OUT NOW on Afterlife", "Artist - Track (Bob Remix)"),
    ("PREMIERE: Artist - Track", "Artist - Track"),
    ("Premiere | Artist - Track (Bob Remix)", "Artist - Track (Bob Remix)"),
    ("Artist - Track [Premiere]", "Artist - Track"),
    ("Artist - Track (Official Video)", "Artist - Track"),
    ("Artist - Track [Official Audio]", "Artist - Track"),
    ("Artist - Track (Visualizer)", "Artist - Track"),
    ("Artist - Track [HD]", "Artist - Track"),
    ("Artist - Track 【Official Music Video】", "Artist - Track"),
    # жанр
    ("Artist - Track [Melodic Techno]", "Artist - Track"),
    ("Artist - Track (Deep House / Organic House)", "Artist - Track"),
    # каталожные номера
    ("Artist - Track (Extended Mix) [IHT016]", "Artist - Track (Extended Mix)"),
    ("Artist - Track (KD-045)", "Artist - Track"),
    ("Artist - Track [SNKR012] [FREE DL]", "Artist - Track"),
    # версии трека остаются
    ("Artist - Track (Original Mix)", "Artist - Track (Original Mix)"),
    ("Artist - Track (Radio Edit)", "Artist - Track (Radio Edit)"),
    ("Artist - Track (feat. Singer)", "Artist - Track (feat. Singer)"),
    ("Artist - Track (Someone Remix)", "Artist - Track (Someone Remix)"),
    ("Artist - Track (Live at Awakenings)", "Artist - Track (Live at Awakenings)"),
    ("Artist - Track (Lyric Edit)", "Artist - Track (Lyric Edit)"),
    ("Artist - Track (VIP)", "Artist - Track (VIP)"),
    # слова, похожие на мусор, но часть названия
    ("Artist - Free Love", "Artist - Free Love"),
    ("Artist - Download", "Artist - Download"),
    ("Artist - Audio Track", "Artist - Audio Track"),
    ("Exclusive Love - Track", "Exclusive Love - Track"),
    ("Artist - Track [Afterlife]", "Artist - Track [Afterlife]"),
    ("Artist - Out Now Baby", "Artist - Out Now Baby"),
    # оформление
    ("Artist – Track", "Artist - Track"),
    ("  Artist  —  Track  ", "Artist - Track"),
    # случаи с сайта Valuma
    ("Escu - Gisas Craisler. wav - Escu_ro", "Escu - Gisas Craisler"),
    ("Escu - Gisas Craisler. wav", "Escu - Gisas Craisler"),
    ("Artist - Track.mp3", "Artist - Track"),
    ("Artist - Track WAV", "Artist - Track"),
    ("Specter [Bandcamp Exclusive]", "Specter"),
    ("Bigmouth (bandcamp)", "Bigmouth"),
    ("Forbidden Path 532 🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍", "Forbidden Path 532"),
    ("🔥 Artist - Track 🔥", "Artist - Track"),
    ("Dawn Razor & ArcheTech - Elect Row (Original Mix) (128 kbps)",
     "Dawn Razor & ArcheTech - Elect Row (Original Mix)"),
    ("Decal - Literal Vibes (128 kbps)", "Decal - Literal Vibes"),
    ("Artist - Track [320]", "Artist - Track"),
    ("Artist - Track [WAV]", "Artist - Track"),
    ("Premiere : Denis Kostitsyn - Hipushit Happens (OTD008)",
     "Denis Kostitsyn - Hipushit Happens"),
    ("Dubrunner - Destination Unknown (An Avrin Remix)",
     "Dubrunner - Destination Unknown (An Avrin Remix)"),
    ("Dryspirit, Cici - Deadly Vision (Ri：thm Reinterpretation)",
     "Dryspirit, Cici - Deadly Vision (Ri：thm Reinterpretation)"),
    ("Artist - Wave Rider (Wave Remix)", "Artist - Wave Rider (Wave Remix)"),
    ("Artist - Track - Part Two", "Artist - Track - Part Two"),
    # нечего оставлять — возвращаем как было
    ("FREE DL", "FREE DL"),
    ("Без названия", "Без названия"),
]


def test_cases():
    failed = []
    for raw, expected in CASES:
        got = clean_title(raw)
        if got != expected:
            failed.append(f"{raw!r}\n    ожидалось {expected!r}\n    получено  {got!r}")
    assert not failed, "\n".join(failed)


def test_catalog_kept_when_disabled():
    assert (
        clean_title("Artist - Track (Extended Mix) [IHT016]", strip_catalog=False)
        == "Artist - Track (Extended Mix) [IHT016]"
    )
    assert (
        clean_title("Artist - Track [IHT016] [FREE DL]", strip_catalog=False)
        == "Artist - Track [IHT016]"
    )


ARTIST_CASES = [
    # (название, исполнитель из метаданных, ожидаемое)
    ("charles", "Ztrl", "Ztrl - charles"),
    ("Electronic Composition", "ri thm", "ri thm - Electronic Composition"),
    ("Bigmouth (bandcamp)", "Loopdeville", "Loopdeville - Bigmouth"),
    ("Specter [Bandcamp Exclusive]", "LUAR", "LUAR - Specter"),
    ("Artist - Track", "Label Channel", "Artist - Track"),
    ("Ztrl - charles", "Ztrl", "Ztrl - charles"),
    ("Charles by Ztrl", "Ztrl", "Charles by Ztrl"),
    ("Gisas Craisler - Escu_ro - Escu_ro", "Escu_ro", "Gisas Craisler - Escu_ro"),
    ("Track 🔥", "🔥 Artist 🔥", "Artist - Track"),
    ("charles", None, "charles"),
]


def test_artist_added():
    failed = []
    for raw, artist, expected in ARTIST_CASES:
        got = clean_title(raw, artist=artist)
        if got != expected:
            failed.append(f"{raw!r} + {artist!r}\n    ожидалось {expected!r}\n    получено  {got!r}")
    assert not failed, "\n".join(failed)


if __name__ == "__main__":
    test_cases()
    test_catalog_kept_when_disabled()
    test_artist_added()
    print(f"OK: {len(CASES) + len(ARTIST_CASES) + 2} проверок")
