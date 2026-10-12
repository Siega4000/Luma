"""
Знак Luma — собственная марка приложения.

Скруглённый квадрат акцентного цвета со стилизованной волной —
отсылка к звуковой форме. Рисуется кодом, файл не нужен.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from luma.ui.theme import COLORS

_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect x="0" y="0" width="32" height="32" rx="9" fill="{fill}"/>
  <g stroke="{mark}" stroke-width="2.6" stroke-linecap="round">
    <path d="M10 11v10"/>
    <path d="M16 8v16"/>
    <path d="M22 13v6"/>
  </g>
</svg>
"""


def logo_pixmap(size: int = 26) -> QPixmap:
    svg = _SVG.format(fill=COLORS["accent_fill"], mark=COLORS["on_accent"])
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))

    ratio = 2
    pixmap = QPixmap(QSize(size * ratio, size * ratio))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap
