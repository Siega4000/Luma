"""
Диалоги Luma: настройки и журнал.

Главный экран остаётся чистым — технические переключатели и подробный
лог живут здесь, но остаются в одном-двух кликах.
"""

from __future__ import annotations

import html

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from luma.config import APP_VERSION
from luma.ui import icons
from luma.ui.assets import check_icon_path
from luma.ui.theme import COLORS, LOG_COLORS, SPACE, build_stylesheet


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {COLORS['divider']}; border: none;")
    return line


class SettingsDialog(QDialog):
    """Компактные настройки: пропуск скачанного и обновление движка."""

    check_engine_requested = Signal()
    folder_change_requested = Signal()

    def __init__(self, settings, engine_version: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Настройки")
        self.setStyleSheet(build_stylesheet(check_icon_path()))
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["xl"], SPACE["xl"], SPACE["xl"], SPACE["xl"])
        layout.setSpacing(SPACE["lg"])

        layout.addWidget(QLabel("Настройки", objectName="DialogTitle"))

        # --- Папка библиотеки ---
        folder_row = QVBoxLayout()
        folder_row.setSpacing(SPACE["xs"])
        folder_row.addWidget(QLabel("Папка библиотеки", objectName="FieldLabel"))
        self.folder_label = QLabel(str(settings.download_dir), objectName="FieldHint")
        self.folder_label.setWordWrap(True)
        folder_row.addWidget(self.folder_label)
        change = QPushButton("Выбрать папку…", objectName="Secondary")
        change.setFixedHeight(32)
        change.setCursor(Qt.PointingHandCursor)
        change.clicked.connect(self.folder_change_requested)
        folder_row.addWidget(change, 0, Qt.AlignLeft)
        layout.addLayout(folder_row)

        layout.addWidget(_divider())

        # --- Поведение загрузки ---
        self.skip_check = QCheckBox("Пропускать уже скачанные треки")
        self.skip_check.setChecked(settings.skip_downloaded)
        self.skip_check.toggled.connect(
            lambda checked: setattr(self.settings, "skip_downloaded", checked)
        )
        layout.addWidget(self.skip_check)
        hint = QLabel(
            "Повторная загрузка плейлиста докачает только новые треки.",
            objectName="FieldHint",
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addWidget(_divider())

        # --- Названия и качество ---
        self.clean_check = QCheckBox("Чистить названия треков")
        self.clean_check.setChecked(settings.clean_titles)
        layout.addWidget(self.clean_check)
        layout.addWidget(self._hint(
            "Убирает [FREE DL], OUT NOW, Premiere, (128 kbps), эмодзи и жанр в скобках, "
            "добавляет исполнителя, если его нет. Версия трека — (Original Mix), "
            "(Extended Mix), (X Remix) — остаётся."
        ))

        self.catalog_check = QCheckBox("Убирать каталожные номера вида [IHT016]")
        self.catalog_check.setChecked(settings.strip_catalog)
        self.catalog_check.toggled.connect(
            lambda checked: setattr(self.settings, "strip_catalog", checked)
        )
        catalog_row = QHBoxLayout()
        catalog_row.setContentsMargins(SPACE["xl"], 0, 0, 0)
        catalog_row.addWidget(self.catalog_check)
        layout.addLayout(catalog_row)

        def on_clean(checked: bool) -> None:
            self.settings.clean_titles = checked
            self.catalog_check.setEnabled(checked)

        self.clean_check.toggled.connect(on_clean)
        self.catalog_check.setEnabled(settings.clean_titles)

        self.force_check = QCheckBox("Всегда перекодировать в MP3 320")
        self.force_check.setChecked(settings.force_320)
        self.force_check.toggled.connect(
            lambda checked: setattr(self.settings, "force_320", checked)
        )
        layout.addWidget(self.force_check)
        layout.addWidget(self._hint(
            "SoundCloud и Bandcamp отдают MP3 128 — по умолчанию он сохраняется "
            "без изменений. С этой опцией файл станет 320 kbps и примерно в 2,5 раза "
            "больше, но звучать будет так же, как источник."
        ))

        layout.addWidget(_divider())

        self.auto_update_check = QCheckBox("Обновлять движок загрузки автоматически")
        self.auto_update_check.setChecked(settings.auto_update_engine)
        self.auto_update_check.toggled.connect(
            lambda checked: setattr(self.settings, "auto_update_engine", checked)
        )
        layout.addWidget(self.auto_update_check)

        layout.addWidget(_divider())

        # --- Движок ---
        engine_row = QHBoxLayout()
        engine_row.setSpacing(SPACE["md"])
        engine_column = QVBoxLayout()
        engine_column.setSpacing(2)
        engine_column.addWidget(QLabel("Движок загрузки", objectName="FieldLabel"))
        self.engine_label = QLabel(f"yt-dlp {engine_version}", objectName="FieldHint")
        engine_column.addWidget(self.engine_label)
        engine_row.addLayout(engine_column, 1)

        self.check_button = QPushButton("Проверить", objectName="Secondary")
        self.check_button.setFixedHeight(32)
        self.check_button.setCursor(Qt.PointingHandCursor)
        self.check_button.setIcon(icons.icon("refresh", 16, COLORS["text"]))
        self.check_button.setIconSize(QSize(16, 16))
        self.check_button.clicked.connect(self._on_check_clicked)
        engine_row.addWidget(self.check_button, 0, Qt.AlignVCenter)
        layout.addLayout(engine_row)

        layout.addStretch(1)

        footer = QHBoxLayout()
        footer.addWidget(QLabel(f"Luma {APP_VERSION}", objectName="FieldHint"))
        footer.addStretch(1)
        close = QPushButton("Готово", objectName="Primary")
        close.setFixedHeight(34)
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.accept)
        close.setDefault(True)
        footer.addWidget(close)
        layout.addLayout(footer)
        close.setFocus()

        # Подсказки переносятся по словам: высоту окна считаем
        # по фиксированной ширине, иначе нижние строки обрезаются.
        self.setFixedWidth(500)
        layout.activate()
        height = layout.heightForWidth(500)
        if height > 0:
            self.setMinimumHeight(height)
            self.resize(500, height)

    @staticmethod
    def _hint(text: str) -> QLabel:
        label = QLabel(text, objectName="FieldHint")
        label.setWordWrap(True)
        return label

    def _on_check_clicked(self) -> None:
        self.check_button.setEnabled(False)
        self.check_button.setText("Проверяю…")
        self.check_engine_requested.emit()

    def engine_check_finished(self, text: str) -> None:
        self.check_button.setEnabled(True)
        self.check_button.setText("Проверить")
        self.engine_label.setText(text)

    def update_folder(self, path: str) -> None:
        self.folder_label.setText(path)


class LogDialog(QDialog):
    """Подробный журнал выполнения."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Журнал")
        self.setStyleSheet(build_stylesheet(check_icon_path()))
        self.resize(720, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["xl"], SPACE["xl"], SPACE["xl"], SPACE["xl"])
        layout.setSpacing(SPACE["md"])

        header = QHBoxLayout()
        header.addWidget(QLabel("Журнал", objectName="DialogTitle"))
        header.addStretch(1)
        close = QPushButton("Закрыть", objectName="Secondary")
        close.setFixedHeight(32)
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.accept)
        header.addWidget(close)
        layout.addLayout(header)

        self.view = QTextEdit(objectName="LogView")
        self.view.setReadOnly(True)
        layout.addWidget(self.view)

    def append(self, message: str, level: str = "info") -> None:
        color = LOG_COLORS.get(level, LOG_COLORS["info"])
        self.view.append(
            f'<span style="color:{color}">{html.escape(message)}</span>'
        )
        self.view.moveCursor(QTextCursor.End)

    def clear(self) -> None:
        self.view.clear()
