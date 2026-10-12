"""Короткие уведомления поверх окна — об успехе, предупреждении, ошибке."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from luma.ui import icons
from luma.ui.theme import COLORS, MOTION, SPACE

_ICONS = {
    "success": ("check", COLORS["success"]),
    "warning": ("alert", COLORS["warning"]),
    "error": ("x_circle", COLORS["error"]),
    "info": ("music", COLORS["text_muted"]),
}


class Toast(QFrame):
    """Всплывающее сообщение в правом нижнем углу родительского окна."""

    def __init__(self, parent: QWidget, text: str, level: str = "info") -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["md"], SPACE["sm"] + 2, SPACE["lg"], SPACE["sm"] + 2)
        layout.setSpacing(SPACE["sm"] + 2)

        name, color = _ICONS.get(level, _ICONS["info"])
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap(name, 16, color))
        layout.addWidget(glyph)

        label = QLabel(text, objectName="ToastText")
        # Короткие сообщения держим в одну строку — перенос выглядит неряшливо
        label.setWordWrap(len(text) > 56)
        label.setMaximumWidth(360)
        layout.addWidget(label)

        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)

    def show_for(self, milliseconds: int = 3200) -> None:
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()

        self._fade(0.0, 1.0, MOTION["base"])
        QTimer.singleShot(milliseconds, self._dismiss)

    def _place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        margin = SPACE["xl"]
        self.move(
            QPoint(
                parent.width() - self.width() - margin,
                parent.height() - self.height() - margin - 16,
            )
        )

    def _fade(self, start: float, end: float, duration: int) -> QPropertyAnimation:
        animation = QPropertyAnimation(self._effect, b"opacity", self)
        animation.setDuration(duration)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start(QPropertyAnimation.DeleteWhenStopped)
        return animation

    def _dismiss(self) -> None:
        animation = self._fade(1.0, 0.0, MOTION["fast"])
        animation.finished.connect(self.deleteLater)


def notify(parent: QWidget, text: str, level: str = "info") -> None:
    """Показывает уведомление, если окно видимо."""
    if parent is None or not parent.isVisible():
        return
    Toast(parent, text, level).show_for()
