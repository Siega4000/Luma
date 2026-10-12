"""Верхняя панель окна: логотип, меню и кнопки управления окном."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from luma.ui import icons
from luma.ui.logo import logo_pixmap
from luma.ui.theme import COLORS, SIZE, SPACE


def _window_button(name: str, tooltip: str, close: bool = False) -> QPushButton:
    button = QPushButton()
    button.setObjectName("CloseButton" if close else "WindowButton")
    button.setIcon(icons.icon(name, 15, COLORS["text_muted"]))
    button.setIconSize(QSize(15, 15))
    button.setFixedSize(34, 26)
    button.setToolTip(tooltip)
    button.setFocusPolicy(Qt.TabFocus)
    button.setCursor(Qt.ArrowCursor)
    return button


class TitleBar(QWidget):
    """Заголовок окна. Перетаскивание и двойной клик отдаёт наружу."""

    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()
    settings_requested = Signal()
    log_requested = Signal()
    drag_started = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(SIZE["titlebar"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], 0, SPACE["xs"], 0)
        layout.setSpacing(SPACE["xs"])

        glyph = QLabel()
        glyph.setPixmap(logo_pixmap(24))
        glyph.setFixedSize(24, 24)
        layout.addWidget(glyph)
        layout.addSpacing(SPACE["sm"] + 2)
        layout.addWidget(QLabel("Luma", objectName="Wordmark"))
        layout.addStretch(1)

        self.settings_button = _window_button("settings", "Настройки")
        self.settings_button.clicked.connect(self.settings_requested)

        self.min_button = _window_button("minimize", "Свернуть")
        self.min_button.clicked.connect(self.minimize_requested)

        self.max_button = _window_button("maximize", "Развернуть")
        self.max_button.clicked.connect(self.maximize_requested)

        self.close_button = _window_button("close", "Закрыть", close=True)
        self.close_button.clicked.connect(self.close_requested)

        layout.addWidget(self.settings_button)

        divider = QFrame(objectName="TitleDivider")
        divider.setFixedSize(1, 18)
        layout.addSpacing(SPACE["sm"])
        layout.addWidget(divider)
        layout.addSpacing(SPACE["sm"])
        for widget in (self.min_button, self.max_button, self.close_button):
            layout.addWidget(widget)

    def set_maximized(self, maximized: bool) -> None:
        self.max_button.setIcon(
            icons.icon("restore" if maximized else "maximize", 15, COLORS["text_muted"])
        )
        self.max_button.setToolTip("Восстановить" if maximized else "Развернуть")

    # ------------------------------------------------------------ события

    def mousePressEvent(self, event) -> None:  # noqa: N802 (интерфейс Qt)
        if event.button() == Qt.LeftButton:
            self.drag_started.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.maximize_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
