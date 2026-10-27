"""
Чистка названий треков.

Площадки и промо-каналы дописывают к названию служебный мусор:
[FREE DL], OUT NOW, Premiere:, (Official Video), жанр в скобках,
каталожный номер релиза. В DJ-библиотеке это мешает искать и сортировать.

Правила:
  * версия трека остаётся всегда: (Original Mix), (Extended Mix),
    (Radio Edit), (X Remix), (feat. Y) и т.п. — это часть названия;
  * удаляется только то, что однозначно служебное;
  * каталожный номер ([IHT016], (KD-045)) убирается отдельной настройкой:
    кто-то ведёт по нему библиотеку;
  * если в названии нет исполнителя («charles»), он подставляется
    из метаданных площадки: «Ztrl - charles»;
  * если после чистки ничего не осталось, возвращается исходное название.
"""

from __future__ import annotations

import re

# Слова, которые означают версию трека: такие скобки не трогаем никогда.
_KEEP = re.compile(
    r"\b(?:mix|remix|edit|dub|vip|rework|re-?work|bootleg|version|instrumental|"
    r"extended|radio|club|original|feat|ft|featuring|remaster(?:ed)?|live|reprise|"
    r"acoustic|cover|flip|refix|mashup|rmx|interpretation|reshape|redux|intro|outro)\b",
    re.IGNORECASE,
)

# Служебные фразы. Скобка, где есть любая из них, удаляется целиком.
_JUNK = (
    r"free\s*(?:dl|d/l|download|downld|track)\b"
    r"|out\s+now\b"
    r"|available\s+now\b"
    r"|premi[eè]re?\b"
    r"|exclusive\b"
    r"|official\s+(?:music\s+)?(?:video|audio|visuali[sz]er|clip)\b"
    r"|(?:music|lyrics?)\s+video\b"
    r"|visuali[sz]er\b"
    r"|lyrics?\b"
    r"|full\s+(?:track|version\s+in\s+description)\b"
    r"|link\s+in\s+(?:bio|description)\b"
    r"|(?:hq|hd|4k)\b"
    r"|audio\b"
)
_JUNK_RE = re.compile(_JUNK, re.IGNORECASE)

# Технические пометки в скобках: битрейт, формат файла, площадка.
_TECH_RE = re.compile(
    r"\b\d{2,3}\s*kbps\b|\bkbps\b|^\s*(?:128|192|256|320)\s*$"
    r"|\b(?:wav|mp3|flac|aiff?|m4a|lossless)\b"
    r"|\b(?:bandcamp|soundcloud|youtube|beatport|spotify|traxsource|juno)\b",
    re.IGNORECASE,
)

# Расширение, попавшее внутрь названия: «Track. wav», «Track.mp3»
_EXT_INSIDE = re.compile(r"\s*\.\s*(?:wav|mp3|flac|aiff?|m4a)\b", re.IGNORECASE)
_EXT_TAIL = re.compile(r"\s+(?:wav|mp3|flac|aiff?)\s*$", re.IGNORECASE)

# Эмодзи и пиктограммы
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF\U0000FE0F\U0000200D\U000020E3]+"
)

# Жанр в скобках: «[Melodic Techno]», «(Deep House)».
_GENRES = (
    "techno", "melodic techno", "hard techno", "peak time techno", "industrial techno",
    "minimal", "minimal techno", "house", "deep house", "tech house", "progressive house",
    "afro house", "organic house", "melodic house", "indie dance", "nu disco", "disco",
    "trance", "psytrance", "progressive", "breaks", "breakbeat", "electro", "electronica",
    "electronic", "edm", "ambient", "downtempo", "drum & bass", "drum and bass", "dnb",
    "dubstep", "garage", "uk garage", "jungle", "hardstyle", "trap", "lo-fi", "lofi",
)
_GENRE_RE = re.compile(
    r"^\s*(?:" + "|".join(re.escape(g) for g in sorted(_GENRES, key=len, reverse=True))
    + r")(?:\s*[/,&]\s*(?:" + "|".join(re.escape(g) for g in _GENRES) + r"))*\s*$",
    re.IGNORECASE,
)

# Каталожный номер: 2–8 заглавных букв, необязательный разделитель, 2–5 цифр.
_CATALOG_RE = re.compile(r"^\s*[A-Z][A-Z0-9]{1,7}[\s\-_.]?\d{2,5}[A-Z]?\s*$")

# Скобки любых видов, без вложенности
_BRACKETS = re.compile(
    r"\(([^()]*)\)|\[([^\[\]]*)\]|\{([^{}]*)\}|【([^【】]*)】|「([^「」]*)」"
)
_STARRED = re.compile(r"\*+\s*([^*]*?)\s*\*+")

# Без скобок срезаем только однозначные фразы: слова вроде «audio»
# или «exclusive» могут оказаться частью настоящего названия.
_STRONG = (
    r"free\s*(?:dl|d/l|download|downld)\b"
    r"|out\s+now\b"
    r"|available\s+now\b"
    r"|premi[eè]re?\b"
    r"|official\s+(?:music\s+)?(?:video|audio|visuali[sz]er|clip)\b"
)
_TAIL = r"(?:\s+(?:on|in|at|via|from|@)\b[^()\[\]]*)?\W*"

_SEP = r"[|:/\\\-–—•·~]+"
_LEADING = re.compile(rf"^\s*(?:{_STRONG})\s*{_SEP}\s*", re.IGNORECASE)
_TRAILING = re.compile(rf"\s*{_SEP}\s*(?:{_STRONG}){_TAIL}$", re.IGNORECASE)
_TRAILING_BARE = re.compile(
    rf"\s+(?:free\s*(?:dl|d/l|download)|out\s+now){_TAIL}$", re.IGNORECASE
)


def _drop_bracket(content: str, strip_catalog: bool) -> bool:
    if not content.strip():
        return True
    if _KEEP.search(content):
        return False
    if _JUNK_RE.search(content) or _TECH_RE.search(content):
        return True
    if _GENRE_RE.match(content):
        return True
    if strip_catalog and _CATALOG_RE.match(content):
        return True
    return False


def _strip_brackets(title: str, strip_catalog: bool) -> str:
    def replace(match: re.Match) -> str:
        content = next(g for g in match.groups() if g is not None)
        return " " if _drop_bracket(content, strip_catalog) else match.group(0)

    previous = None
    while previous != title:  # повторяем: после удаления могут открыться новые
        previous = title
        title = _BRACKETS.sub(replace, title)
    return title


def _strip_starred(title: str) -> str:
    def replace(match: re.Match) -> str:
        content = match.group(1)
        if _JUNK_RE.search(content) and not _KEEP.search(content):
            return " "
        return match.group(0)

    return _STARRED.sub(replace, title)


def _tidy(title: str) -> str:
    # Единый вид разделителя «Артист - Название»
    title = re.sub(r"\s+[–—]\s+", " - ", title)
    title = re.sub(r"\s{2,}", " ", title)
    # Обрывки разделителей по краям
    title = re.sub(r"^[\s|:/\\\-–—•·~,]+", "", title)
    title = re.sub(r"[\s|:/\\\-–—•·~,]+$", "", title)
    title = re.sub(r"\s+-\s+-\s+", " - ", title)
    # Пробел перед закрывающей скобкой и после открывающей
    title = re.sub(r"\(\s+", "(", title)
    title = re.sub(r"\s+\)", ")", title)
    title = re.sub(r"\[\s+", "[", title)
    title = re.sub(r"\s+\]", "]", title)
    return title.strip()


def _norm(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower())


def _drop_trailing_handle(title: str, artist: str | None) -> str:
    """
    «Escu - Gisas Craisler - Escu_ro» → «Escu - Gisas Craisler».

    Последний кусок убирается, только если это ник одним словом,
    повторяющий исполнителя из начала названия или из метаданных.
    """
    parts = title.split(" - ")
    if len(parts) < 3:
        return title
    last = parts[-1].strip()
    if " " in last:
        return title
    first, tail = _norm(parts[0]), _norm(last)
    if not tail:
        return title
    same_as_first = len(first) >= 3 and tail.startswith(first)
    same_as_artist = bool(artist) and tail == _norm(artist)
    if same_as_first or same_as_artist:
        return " - ".join(parts[:-1])
    return title


def _add_artist(title: str, artist: str | None) -> str:
    """«charles» + исполнитель Ztrl → «Ztrl - charles»."""
    if not artist:
        return title
    artist = _tidy(_EMOJI.sub(" ", artist))
    if not artist or " - " in title or _norm(artist) in _norm(title):
        return title
    return f"{artist} - {title}"


def clean_title(title: str, strip_catalog: bool = True, artist: str | None = None) -> str:
    """
    Возвращает название без служебных пометок.

    artist — исполнитель из метаданных площадки; если передан, а в названии
    исполнителя нет, он подставляется в начало.
    """
    if not title:
        return title
    original = title.strip()

    result = _EMOJI.sub(" ", original)
    result = _strip_brackets(result, strip_catalog)
    result = _strip_starred(result)
    result = _EXT_INSIDE.sub("", result)

    previous = None
    while previous != result:
        previous = result
        result = _LEADING.sub("", result)
        result = _TRAILING.sub("", result)
        result = _TRAILING_BARE.sub("", result)
        result = _EXT_TAIL.sub("", result)
        result = _tidy(result)
        result = _drop_trailing_handle(result, artist)

    if not result:
        return original
    return _add_artist(result, artist)
