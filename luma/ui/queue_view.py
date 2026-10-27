"""
Очередь загрузки: карточки треков с обложкой, метаданными и прогрессом.

Карточка — элемент музыкального продукта, а не строка лога:
обложка, название, исполнитель, источник, длительность и статус.
Все данные — настоящие метаданные от движка загрузки; если обложки
нет, показывается нейтральный placeholder с нотой.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from mutagen.id3 import ID3
from PySide6.QtCore import (
    QEasingCurve,
    QSize,
    QPropertyAnimation,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QAction, QGuiApplication, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QPushButton,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from luma.ui import icons
from luma.ui.theme import COLORS, MOTION, RADIUS, SIZE, SPACE, STATUS_PILL, TYPE

STATUS_TEXT = {
    "queued": "В очереди",
    "resolving": "Обработка ссылки",
    "downloading": "Загрузка",
    "converting": "Конвертация",
    "done": "Готово",
    "no_cover": "Без обложки",
    "error": "Ошибка",
    "cancelled": "Отменено",
}


def plural_tracks(count: int) -> str:
    """Склонение: 1 трек, 2 трека, 5 треков."""
    tail = count % 100
    if 11 <= tail <= 14:
        return f"{count} треков"
    last = count % 10
    if last == 1:
        return f"{count} трек"
    if 2 <= last <= 4:
        return f"{count} трека"
    return f"{count} треков"


def format_duration(seconds: float | None) -> str:
    if not seconds:
        return ""
    total = int(round(seconds))
    if total >= 3600:
        return f"{total // 3600}:{(total % 3600) // 60:02d}:{total % 60:02d}"
    return f"{total // 60}:{total % 60:02d}"


def source_name(raw: str | None) -> str:
    """Человеческое имя площадки из extractor_key yt-dlp."""
    if not raw:
        return ""
    low = raw.lower()
    if "youtube" in low:
        return "YouTube"
    if "soundcloud" in low:
        return "SoundCloud"
    if "bandcamp" in low:
        return "Bandcamp"
    return raw.split(":")[0].capitalize()


def _placeholder_cover(size: int) -> QPixmap:
    """Нейтральная заглушка обложки — нота на приглушённой подложке."""
    from PySide6.QtGui import QColor

    ratio = 2
    base = QPixmap(size * ratio, size * ratio)
    base.setDevicePixelRatio(ratio)
    base.fill(Qt.transparent)

    painter = QPainter(base)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(COLORS["surface_active"]))
    painter.drawRoundedRect(
        0, 0, size * ratio, size * ratio, RADIUS["md"] * ratio, RADIUS["md"] * ratio
    )
    note = icons.pixmap("music", int(size * 0.42), COLORS["text_muted"])
    note_size = int(size * 0.42 * ratio)
    scaled = note.scaled(note_size, note_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    painter.drawPixmap(
        (size * ratio - note_size) // 2, (size * ratio - note_size) // 2, scaled
    )
    painter.end()
    return base


def _rounded(pixmap: QPixmap, size: int) -> QPixmap:
    """Обрезает обложку в квадрат со скруглением."""
    from PySide6.QtGui import QPainterPath

    ratio = 2
    target = size * ratio
    scaled = pixmap.scaled(
        target, target, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
    )

    canvas = QPixmap(target, target)
    canvas.setDevicePixelRatio(ratio)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, target, target, RADIUS["md"] * ratio, RADIUS["md"] * ratio)
    painter.setClipPath(path)
    painter.drawPixmap(
        (target - scaled.width()) // 2, (target - scaled.height()) // 2, scaled
    )
    painter.end()
    return canvas


@dataclass
class TrackState:
    key: str
    title: str
    artist: str = ""
    source: str = ""
    duration: float | None = None
    url: str = ""
    filepath: str = ""
    status: str = "queued"
    percent: int = 0
    detail: str = ""
    size_text: str = ""
    thumbnail: str = ""
    quality: dict = field(default_factory=dict)


class TrackCard(QFrame):
    """Одна строка очереди: обложка, название, прогресс, статус, действия."""

    redownload_requested = Signal(str)
    remove_requested = Signal(str)
    cancel_requested = Signal(str)

    def __init__(self, state: TrackState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TrackRow")
        self.state = state
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumHeight(SIZE["row"])

        row = QHBoxLayout(self)
        row.setContentsMargins(SPACE["md"], SPACE["sm"] + 2, SPACE["md"], SPACE["sm"] + 2)
        row.setSpacing(SPACE["md"])

        self.cover = QLabel(objectName="Cover")
        self.cover.setFixedSize(SIZE["cover"], SIZE["cover"])
        self.cover.setPixmap(_placeholder_cover(SIZE["cover"]))
        row.addWidget(self.cover, 0, Qt.AlignVCenter)

        text_column = QVBoxLayout()
        text_column.setSpacing(3)
        self.title_label = QLabel(objectName="CardTitle")
        self.title_label.setTextFormat(Qt.PlainText)
        self.meta_label = QLabel(objectName="CardMeta")
        self.meta_label.setTextFormat(Qt.PlainText)
        for label in (self.title_label, self.meta_label):
            label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        text_column.addWidget(self.title_label)
        text_column.addWidget(self.meta_label)
        row.addLayout(text_column, 5)

        # Прогресс активной загрузки — в середине строки
        self.progress_box = QWidget()
        progress_layout = QHBoxLayout(self.progress_box)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress = QProgressBar(objectName="RowProgress")
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        progress_layout.addWidget(self.progress)
        self.progress_box.setVisible(False)
        row.addWidget(self.progress_box, 4)

        # Скорость и объём
        numbers = QVBoxLayout()
        numbers.setSpacing(1)
        numbers.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.speed_label = QLabel(objectName="RowSpeed")
        self.speed_label.setAlignment(Qt.AlignRight)
        self.size_label = QLabel(objectName="RowSize")
        self.size_label.setAlignment(Qt.AlignRight)
        numbers.addWidget(self.speed_label)
        numbers.addWidget(self.size_label)
        self.numbers_box = QWidget()
        self.numbers_box.setLayout(numbers)
        self.numbers_box.setVisible(False)
        row.addWidget(self.numbers_box, 0, Qt.AlignVCenter)

        # Реальное качество источника: «MP3 320», «Opus 130», «WAV»
        self.quality_badge = QLabel(objectName="QualityBadge")
        self.quality_badge.setFixedHeight(22)
        self.quality_badge.setAlignment(Qt.AlignCenter)
        self.quality_badge.setVisible(False)
        row.addWidget(self.quality_badge, 0, Qt.AlignVCenter)

        # Индикатор статуса: кружок и подпись — отдельные элементы,
        # иначе символ «точки» встаёт по базовой линии шрифта и выглядит
        # смещённым вверх относительно текста.
        self.status_pill = QFrame(objectName="StatusPill")
        self.status_pill.setFixedHeight(22)
        pill_layout = QHBoxLayout(self.status_pill)
        pill_layout.setContentsMargins(10, 0, 11, 0)
        pill_layout.setSpacing(7)
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(6, 6)
        self.status_text = QLabel(objectName="StatusPillText")
        pill_layout.addWidget(self.status_dot, 0, Qt.AlignVCenter)
        pill_layout.addWidget(self.status_text, 0, Qt.AlignVCenter)
        row.addWidget(self.status_pill, 0, Qt.AlignVCenter)

        self.action_button = QPushButton(objectName="IconButton")
        self.action_button.setFixedSize(28, 28)
        self.action_button.setIconSize(QSize(16, 16))
        self.action_button.setCursor(Qt.PointingHandCursor)
        self.action_button.clicked.connect(self._on_action_clicked)
        row.addWidget(self.action_button, 0, Qt.AlignVCenter)

        self._progress_anim = QPropertyAnimation(self.progress, b"value", self)
        self._progress_anim.setDuration(MOTION["fast"])
        self._progress_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._meta_text = ""
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.refresh()

    # --------------------------------------------------------- отрисовка

    def refresh(self) -> None:
        state = self.state
        self.title_label.setText(state.title or "Без названия")
        self.title_label.setToolTip(state.title)

        if state.status == "error" and state.detail:
            self._meta_text = state.detail
        else:
            parts = [p for p in (state.artist, source_name(state.source)) if p]
            duration = format_duration(state.duration)
            if duration:
                parts.append(duration)
            self._meta_text = "  ·  ".join(parts) if parts else "—"
        self.meta_label.setText(self._meta_text)
        self.meta_label.setToolTip(self._meta_text)

        # Пилюля статуса: точка + подпись в цвете состояния
        color, background = STATUS_PILL.get(
            state.status, (COLORS["text_muted"], COLORS["surface_active"])
        )
        label = STATUS_TEXT.get(state.status, state.status)
        if getattr(self, "_compact", False) and state.status == "downloading":
            label = f"{label} · {state.percent}%"
        self.status_text.setText(label)
        self.status_text.setStyleSheet(f"color: {color}; background: transparent;")
        self.status_dot.setStyleSheet(
            f"background-color: {color}; border-radius: 3px;"
        )
        self.status_pill.setStyleSheet(
            f"QFrame#StatusPill {{ background-color: {background}; "
            f"border-radius: 11px; }}"
        )
        self.status_pill.setToolTip(state.detail if state.status == "error" else "")

        quality = state.quality or {}
        show_quality = state.status in ("done", "no_cover") and bool(quality.get("label"))
        self.quality_badge.setVisible(show_quality)
        if show_quality:
            good = quality.get("good")
            q_color = COLORS["success"] if good else COLORS["text_muted"]
            q_border = COLORS["success_dim"] if good else COLORS["divider"]
            self.quality_badge.setText(quality["label"])
            self.quality_badge.setToolTip(quality.get("tooltip", ""))
            self.quality_badge.setStyleSheet(
                f"QLabel#QualityBadge {{ color: {q_color}; background: transparent; "
                f"border: 1px solid {q_border}; border-radius: 6px; "
                f"padding: 0 8px; font-size: {TYPE['caption']}px; font-weight: 600; }}"
            )

        active = state.status in ("downloading", "converting")
        self.setProperty("active", "yes" if active else "")
        self.style().unpolish(self)
        self.style().polish(self)

        if state.status == "converting":
            self.progress.setRange(0, 0)  # неопределённый индикатор
        else:
            self.progress.setRange(0, 100)
        compact = getattr(self, "_compact", False)
        self.progress_box.setVisible(active and not compact)
        self.numbers_box.setVisible(
            active and not compact and bool(state.detail or state.size_text)
        )
        self.speed_label.setText(
            f"{state.detail}  ·  {state.percent}%" if state.detail else f"{state.percent}%"
        )
        self.size_label.setText(state.size_text)

        # У всех строк одно и то же действие — меню.
        # Отмена живёт в шапке, потому что движок отменяет очередь целиком,
        # а не отдельный трек: кнопка в строке обещала бы не то, что делает.
        self.action_button.setIcon(icons.icon("more", 16, COLORS["text_muted"]))
        self.action_button.setToolTip("Действия")

    def _on_action_clicked(self) -> None:
        menu = self._build_menu()
        menu.exec(self.action_button.mapToGlobal(self.action_button.rect().bottomLeft()))

    def set_progress(self, percent: int) -> None:
        self.state.percent = percent
        self._progress_anim.stop()
        self._progress_anim.setStartValue(self.progress.value())
        self._progress_anim.setEndValue(percent)
        self._progress_anim.start()
        self.refresh()

    def set_cover_data(self, data: bytes) -> None:
        pixmap = QPixmap()
        if pixmap.loadFromData(data) and not pixmap.isNull():
            self.cover.setPixmap(_rounded(pixmap, SIZE["cover"]))

    def load_cover_from_file(self, filepath: Path) -> bool:
        """Обложка из ID3-тега готового MP3."""
        try:
            tags = ID3(str(filepath))
            apics = tags.getall("APIC")
            if apics:
                pixmap = QPixmap()
                if pixmap.loadFromData(apics[0].data):
                    self.cover.setPixmap(_rounded(pixmap, SIZE["cover"]))
                    return True
        except Exception:
            pass
        return False

    COMPACT_WIDTH = 720

    def resizeEvent(self, event) -> None:  # noqa: N802 (интерфейс Qt)
        super().resizeEvent(event)
        self._apply_density()
        self._elide()

    def _apply_density(self) -> None:
        """На узком окне прогресс и цифры прячутся — название важнее."""
        compact = self.width() < self.COMPACT_WIDTH
        if compact != getattr(self, "_compact", None):
            self._compact = compact
            self.refresh()

    def _elide(self) -> None:
        """Длинные названия обрезаются многоточием, а не ломают вёрстку.

        Текст всегда берётся из исходных строк, иначе при каждом
        изменении размера обрезалась бы уже обрезанная строка.
        """
        from PySide6.QtGui import QFontMetrics

        width = max(120, self.title_label.width())
        for label, text in (
            (self.title_label, self.state.title or "Без названия"),
            (self.meta_label, getattr(self, "_meta_text", "")),
        ):
            metrics = QFontMetrics(label.font())
            label.setText(metrics.elidedText(text, Qt.ElideRight, width))

    # ---------------------------------------------------- контекстное меню

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        self._build_menu().exec(event.globalPos())

    def _build_menu(self) -> QMenu:
        menu = QMenu(self)
        state = self.state

        again = QAction(icons.icon("refresh", 16), "Скачать заново", menu)
        again.setEnabled(
            bool(state.url) and state.status not in ("downloading", "converting")
        )
        again.triggered.connect(lambda: self.redownload_requested.emit(state.key))
        menu.addAction(again)

        in_folder = QAction(icons.icon("folder", 16), "Показать в папке", menu)
        has_file = bool(state.filepath) and Path(state.filepath).exists()
        in_folder.setEnabled(has_file)
        in_folder.triggered.connect(self._open_folder)
        menu.addAction(in_folder)

        copy = QAction(icons.icon("copy", 16), "Скопировать ссылку", menu)
        copy.setEnabled(bool(state.url))
        copy.triggered.connect(lambda: QGuiApplication.clipboard().setText(state.url))
        menu.addAction(copy)

        if state.status in ("downloading", "converting"):
            stop = QAction(icons.icon("close", 16), "Остановить загрузку", menu)
            stop.triggered.connect(lambda: self.cancel_requested.emit(state.key))
            menu.addAction(stop)

        menu.addSeparator()
        remove = QAction(icons.icon("trash", 16), "Убрать из списка", menu)
        remove.triggered.connect(lambda: self.remove_requested.emit(state.key))
        menu.addAction(remove)
        return menu

    def _open_folder(self) -> None:
        path = Path(self.state.filepath)
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path.parent)])
        except Exception:
            pass


class QueueView(QScrollArea):
    """Список карточек с пустым состоянием."""

    redownload_requested = Signal(str)
    cancel_requested = Signal(str)
    counts_changed = Signal(int, int, int)  # готово, всего, ошибок

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Queue")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)

        self._cards: dict[str, TrackCard] = {}
        self._order: list[str] = []

        body = QWidget(objectName="QueueBody")
        outer = QVBoxLayout(body)
        outer.setContentsMargins(0, 0, SPACE["sm"], SPACE["sm"])
        outer.setSpacing(0)

        # Все строки лежат в одной панели — рамка одна, а не у каждой строки
        self.panel = QFrame(objectName="QueuePanel")
        self._layout = QVBoxLayout(self.panel)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        outer.addWidget(self.panel)
        outer.addStretch(1)
        self.panel.setVisible(False)
        self.setWidget(body)

        # Пустое состояние — отдельный слой поверх области,
        # центрируется по ней при любом размере окна.
        self._empty = self._build_empty_state()
        self._empty.setParent(self.viewport())
        self._apply_empty_state(True)

    def _mark_last_row(self) -> None:
        """У последней строки нет нижнего разделителя."""
        rows = [self._layout.itemAt(i).widget() for i in range(self._layout.count())]
        rows = [r for r in rows if r is not None]
        for index, row in enumerate(rows):
            row.setProperty("last", "yes" if index == len(rows) - 1 else "")
            row.style().unpolish(row)
            row.style().polish(row)

    def _apply_empty_state(self, empty: bool) -> None:
        self.panel.setVisible(not empty)
        self._empty.setVisible(empty)
        if empty:
            self._center_empty()

    def _center_empty(self) -> None:
        viewport = self.viewport()
        hint = self._empty.sizeHint()
        self._empty.setGeometry(
            0,
            max(0, (viewport.height() - hint.height()) // 2),
            viewport.width(),
            hint.height(),
        )
        self._empty.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802 (интерфейс Qt)
        super().resizeEvent(event)
        if self._empty.isVisible():
            self._center_empty()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._empty.isVisible():
            self._center_empty()

    def _build_empty_state(self) -> QWidget:
        holder = QWidget()
        holder.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["sm"])
        layout.setAlignment(Qt.AlignCenter)

        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("download", 24, COLORS["text_faint"]))
        glyph.setAlignment(Qt.AlignCenter)

        title = QLabel("Очередь пуста", objectName="EmptyTitle")
        title.setAlignment(Qt.AlignCenter)
        hint = QLabel(
            "Вставьте ссылку выше — трек появится здесь", objectName="EmptyHint"
        )
        hint.setAlignment(Qt.AlignCenter)

        layout.addWidget(glyph)
        layout.addWidget(title)
        layout.addWidget(hint)
        return holder

    # ------------------------------------------------------------- данные

    def clear(self) -> None:
        for key in list(self._cards):
            self._remove(key)
        self._update_counts()

    def upsert(self, state: TrackState) -> TrackCard:
        card = self._cards.get(state.key)
        if card is None:
            card = TrackCard(state)
            card.redownload_requested.connect(self.redownload_requested)
            card.remove_requested.connect(self._remove)
            self._cards[state.key] = card
            self._order.append(state.key)
            self._layout.addWidget(card)
            card.cancel_requested.connect(self.cancel_requested)
            self._animate_in(card)
            self._apply_empty_state(False)
            self._mark_last_row()
        else:
            previous = card.state
            # Не затираем уже известные данные пустыми значениями
            for field_name in (
                "title", "artist", "source", "duration", "url", "filepath", "thumbnail",
                "quality",
            ):
                value = getattr(state, field_name)
                if value:
                    setattr(previous, field_name, value)
            previous.status = state.status
            if state.detail:
                previous.detail = state.detail
            card.refresh()
        self._update_counts()
        return card

    def card(self, key: str) -> TrackCard | None:
        return self._cards.get(key)

    def set_status(self, key: str, status: str, detail: str = "") -> None:
        card = self._cards.get(key)
        if card is None:
            return
        card.state.status = status
        if detail:
            card.state.detail = detail
        card.refresh()
        self._update_counts()

    def set_progress(self, key: str, percent: int, detail: str = "") -> None:
        card = self._cards.get(key)
        if card is None:
            return
        card.state.status = "downloading"
        card.state.detail = detail
        card.set_progress(percent)

    def finalize(self, cancelled: bool) -> None:
        """Незавершённые карточки получают итоговый статус."""
        for card in self._cards.values():
            if card.state.status in ("queued", "resolving", "downloading", "converting"):
                card.state.status = "cancelled" if cancelled else "error"
                if not cancelled and not card.state.detail:
                    card.state.detail = "Загрузка не завершилась"
                card.refresh()
        self._update_counts()

    def states(self) -> list[TrackState]:
        return [self._cards[key].state for key in self._order if key in self._cards]

    # ---------------------------------------------------------- внутреннее

    def _remove(self, key: str) -> None:
        card = self._cards.pop(key, None)
        if card is not None:
            self._layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        if key in self._order:
            self._order.remove(key)
        if not self._cards:
            self._apply_empty_state(True)
        else:
            self._mark_last_row()
        self._update_counts()

    def _animate_in(self, card: TrackCard) -> None:
        effect = QGraphicsOpacityEffect(card)
        card.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", card)
        animation.setDuration(MOTION["base"])
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.finished.connect(lambda: card.setGraphicsEffect(None))
        animation.start(QPropertyAnimation.DeleteWhenStopped)

    def _update_counts(self) -> None:
        done = sum(
            1 for c in self._cards.values() if c.state.status in ("done", "no_cover")
        )
        errors = sum(1 for c in self._cards.values() if c.state.status == "error")
        self.counts_changed.emit(done, len(self._cards), errors)
