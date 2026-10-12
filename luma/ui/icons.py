"""
Иконки Luma — единый тонкоштриховый набор (SVG, обводка 1.5px).

Иконки рисуются из встроенных SVG-путей: никаких эмодзи и внешних
файлов. Цвет задаётся при запросе, поэтому одна и та же иконка
работает в обычном и акцентном состоянии.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from luma.ui.theme import COLORS

# Пути в системе координат 24x24, обводка — как у Lucide.
_PATHS: dict[str, str] = {
    "minimize": '<path d="M5 12h14"/>',
    "maximize": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "restore": '<rect x="8" y="8" width="11" height="11" rx="2"/>'
                '<path d="M5 15V6a1 1 0 0 1 1-1h9"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "settings": '<circle cx="12" cy="12" r="3"/>'
                '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06'
                'a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09'
                'a1.65 1.65 0 0 0-1.08-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83'
                'l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09'
                'A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83'
                'l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09'
                'a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83'
                'l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09'
                'a1.65 1.65 0 0 0-1.51 1z"/>',
    "folder": '<path d="M4 20a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2z"/>',
    "music": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
                '<path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>',
    "check": '<path d="M20 6L9 17l-5-5"/>',
    "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><path d="M12 16h.01"/>',
    "x_circle": '<circle cx="12" cy="12" r="9"/><path d="M15 9l-6 6M9 9l6 6"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/>'
            '<path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2"/>'
            '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "more": '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/>'
            '<circle cx="19" cy="12" r="1.3"/>',
    "chevron_up": '<path d="M18 15l-6-6-6 6"/>',
    "chevron_down": '<path d="M6 9l6 6 6-6"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "trash": '<path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
             '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
}

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{width}" stroke-linecap="round" '
    'stroke-linejoin="round">{paths}</svg>'
)


def pixmap(name: str, size: int = 16, color: str | None = None, width: float = 1.6) -> QPixmap:
    """Иконка как QPixmap нужного размера и цвета (с учётом DPI экрана)."""
    paths = _PATHS.get(name)
    if paths is None:
        return QPixmap()

    svg = _SVG.format(color=color or COLORS["text_muted"], width=width, paths=paths)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))

    ratio = 2.0  # рисуем с запасом — на HiDPI не будет мыла
    canvas = QPixmap(QSize(int(size * ratio), int(size * ratio)))
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    canvas.setDevicePixelRatio(ratio)
    return canvas


def icon(name: str, size: int = 16, color: str | None = None) -> QIcon:
    """Иконка как QIcon — для кнопок и пунктов меню."""
    return QIcon(pixmap(name, size, color))
