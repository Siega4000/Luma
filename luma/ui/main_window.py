"""
Главное окно Luma.

Компоновка сверху вниз:
  1. Заголовок окна — логотип, журнал, настройки, кнопки окна
  2. Поле ссылки + кнопка основного действия
  3. Очередь загрузки с карточками треков
  4. Нижняя панель — папка библиотеки и состояние

Технические переключатели вынесены в диалог настроек, подробный лог —
в отдельное окно журнала. Главный экран остаётся чистым.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from luma.config import APP_NAME, Settings, archive_file
from luma.core import engine_update
from luma.core.downloader import DownloadEngine
from luma.core.update_worker import EngineUpdateWorker
from luma.core.worker import DownloadWorker
from luma.ui import icons
from luma.ui.cover_fetch import CoverFetcher
from luma.ui.dialogs import LogDialog, SettingsDialog
from luma.ui.queue_view import QueueView, TrackState, plural_tracks
from luma.ui.assets import check_icon_path
from luma.ui.theme import COLORS, SIZE, SPACE, build_stylesheet
from luma.ui.title_bar import TitleBar
from luma.ui.toast import notify
from luma.ui.window_frame import FramelessMixin

log = logging.getLogger("luma.ui")

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


class MainWindow(FramelessMixin, QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings()
        self.worker: DownloadWorker | None = None
        self.update_worker: EngineUpdateWorker | None = None
        self.settings_dialog: SettingsDialog | None = None
        self._progress_text = ""
        self._running = False

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(620, 560)
        self.resize(760, 680)
        self.setStyleSheet(build_stylesheet(check_icon_path()))

        self.covers = CoverFetcher()
        self.covers.cover_ready.connect(self._on_cover_ready)
        self.covers.start()

        self.log_dialog = LogDialog(self)

        self._build_ui()
        self.init_frameless()
        self.url_input.setFocus()
        self._install_shortcuts()
        QTimer.singleShot(400, self._check_ffmpeg)

        if self.settings.auto_update_engine:
            QTimer.singleShot(1500, lambda: self._check_engine(silent=True))

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QWidget(objectName="Root")
        self.setCentralWidget(root)
        root.setMouseTracking(True)

        shell = QVBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        # --- Заголовок ---
        self.title_bar = TitleBar()
        self.title_bar.minimize_requested.connect(self.showMinimized)
        self.title_bar.maximize_requested.connect(self._toggle_maximize)
        self.title_bar.close_requested.connect(self.close)
        self.title_bar.settings_requested.connect(self._open_settings)
        self.title_bar.log_requested.connect(self._open_log)
        self.title_bar.drag_started.connect(self.start_system_move)
        shell.addWidget(self.title_bar)

        # --- Рабочая область ---
        content = QWidget()
        content.setMouseTracking(True)
        body = QVBoxLayout(content)
        body.setContentsMargins(SPACE["xl"], SPACE["xl"], SPACE["xl"], SPACE["lg"])
        body.setSpacing(SPACE["lg"])
        shell.addWidget(content, 1)

        body.addLayout(self._build_input_block())
        body.addLayout(self._build_queue_header())
        self.queue = QueueView()
        self.queue.redownload_requested.connect(self._redownload)
        self.queue.cancel_requested.connect(lambda _key: self._cancel())
        self.queue.counts_changed.connect(self._on_counts_changed)
        body.addWidget(self.queue, 1)

        shell.addWidget(self._build_status_bar())

    def _build_input_block(self) -> QVBoxLayout:
        block = QVBoxLayout()
        block.setSpacing(SPACE["md"])

        # --- строка ввода: поле + кнопка действия ---
        line = QHBoxLayout()
        line.setSpacing(SPACE["md"])

        self.input_shell = QFrame(objectName="InputShell")
        shell = QHBoxLayout(self.input_shell)
        shell.setContentsMargins(SPACE["md"] + 2, SPACE["sm"], SPACE["sm"], SPACE["sm"])
        shell.setSpacing(SPACE["sm"] + 2)

        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("link", 16, COLORS["text_muted"]))
        glyph.setFixedWidth(18)
        shell.addWidget(glyph, 0, Qt.AlignTop if False else Qt.AlignVCenter)

        self.url_input = QPlainTextEdit(objectName="UrlInput")
        self.url_input.setPlaceholderText(
            "Вставьте ссылку на трек или плейлист — по одной в строке"
        )
        self.url_input.setFixedHeight(SIZE["input_min"] - 20)
        self.url_input.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.url_input.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.url_input.setTabChangesFocus(True)
        self.url_input.setFrameShape(QFrame.NoFrame)
        self.url_input.textChanged.connect(self._on_input_changed)
        self.url_input.installEventFilter(self)
        shell.addWidget(self.url_input, 1)

        self.clear_button = QPushButton(objectName="IconButton")
        self.clear_button.setFixedSize(28, 28)
        self.clear_button.setIcon(icons.icon("close", 16, COLORS["text_muted"]))
        self.clear_button.setIconSize(QSize(16, 16))
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.setToolTip("Очистить поле")
        self.clear_button.setVisible(False)
        self.clear_button.clicked.connect(self.url_input.clear)
        shell.addWidget(self.clear_button, 0, Qt.AlignVCenter)

        self.input_shell.setFixedHeight(SIZE["button"])
        line.addWidget(self.input_shell, 1)

        self.cancel_button = QPushButton("Отменить", objectName="Secondary")
        self.cancel_button.setFixedHeight(SIZE["button"])
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._cancel)
        line.addWidget(self.cancel_button)

        self.start_button = QPushButton("Скачать", objectName="Primary")
        self.start_button.setFixedHeight(SIZE["button"])
        self.start_button.setMinimumWidth(150)
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.setIcon(icons.icon("download", 16, COLORS["on_accent"]))
        self.start_button.setIconSize(QSize(16, 16))
        self.start_button.setToolTip("Начать загрузку (Ctrl+Enter)")
        self.start_button.clicked.connect(self._start)
        line.addWidget(self.start_button)
        block.addLayout(line)

        # --- метки площадок и подсказка/ошибка ---
        chips = QHBoxLayout()
        chips.setSpacing(SPACE["sm"])
        self.platform_chips = {}
        for key, title in (
            ("soundcloud", "SoundCloud"),
            ("youtube", "YouTube"),
            ("bandcamp", "Bandcamp"),
        ):
            chip = self._make_platform_chip(title)
            self.platform_chips[key] = chip
            chips.addWidget(chip)
        chips.addStretch(1)

        self.hint_label = QLabel("", objectName="InputHint")
        chips.addWidget(self.hint_label)
        block.addLayout(chips)
        return block

    def _make_platform_chip(self, title: str) -> QFrame:
        """Метка площадки: подсвечивается, когда ссылка распознана."""
        chip = QFrame(objectName="PlatformChip")
        chip.setFixedHeight(28)
        layout = QHBoxLayout(chip)
        layout.setContentsMargins(SPACE["md"], 0, SPACE["md"], 0)
        layout.setSpacing(SPACE["sm"])
        dot = QLabel("●")
        dot.setObjectName("ChipText")
        layout.addWidget(dot)
        layout.addWidget(QLabel(title, objectName="ChipText"))
        return chip

    def _build_queue_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(SPACE["sm"])
        row.addWidget(QLabel("Очередь", objectName="SectionLabel"))
        row.addStretch(1)
        self.queue_counter = QLabel("", objectName="InputHint")
        row.addWidget(self.queue_counter)
        return row

    def _build_status_bar(self) -> QWidget:
        bar = QWidget(objectName="StatusBar")
        bar.setFixedHeight(SIZE["statusbar"])
        bar.setMouseTracking(True)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(SPACE["lg"], 0, SPACE["lg"], 0)
        layout.setSpacing(SPACE["sm"])

        self.folder_button = QPushButton(objectName="Ghost")
        self.folder_button.setIcon(icons.icon("folder", 16, COLORS["text_muted"]))
        self.folder_button.setIconSize(QSize(16, 16))
        self.folder_button.setCursor(Qt.PointingHandCursor)
        self.folder_button.setToolTip("Выбрать папку библиотеки")
        self.folder_button.clicked.connect(self._choose_folder)
        self._update_folder_button()
        layout.addWidget(self.folder_button)

        layout.addStretch(1)

        self.status_label = QLabel("Готово к работе", objectName="StatusText")
        layout.addWidget(self.status_label)

        self.log_button = QPushButton(objectName="IconButton")
        self.log_button.setFixedSize(28, 28)
        self.log_button.setIcon(icons.icon("chevron_up", 16, COLORS["text_muted"]))
        self.log_button.setIconSize(QSize(16, 16))
        self.log_button.setCursor(Qt.PointingHandCursor)
        self.log_button.setToolTip("Журнал (Ctrl+L)")
        self.log_button.clicked.connect(self._open_log)
        layout.addWidget(self.log_button)
        return bar

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._start)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self._start)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self._open_log)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self._open_settings)
        QShortcut(
            QKeySequence("Escape"), self, activated=lambda: self._cancel()
        )

    # ------------------------------------------------- рамка окна и размеры

    def _toggle_maximize(self) -> None:
        self.toggle_maximize()
        self.title_bar.set_maximized(self.isMaximized())

    def changeEvent(self, event) -> None:  # noqa: N802 (интерфейс Qt)
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            self.title_bar.set_maximized(self.isMaximized())

    COMPACT_WIDTH = 760

    def resizeEvent(self, event) -> None:  # noqa: N802 (интерфейс Qt)
        super().resizeEvent(event)
        compact = self.width() < self.COMPACT_WIDTH
        if compact == getattr(self, "_compact_top", None):
            return
        self._compact_top = compact
        # На узком окне кнопки ужимаются, чтобы поле ссылки не страдало
        self.start_button.setMinimumWidth(104 if compact else 150)
        self.start_button.setIcon(
            QIcon() if compact else icons.icon("download", 16, COLORS["on_accent"])
        )
        self.cancel_button.setText("Стоп" if compact else "Отменить")

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self.handle_frame_move(event.position().toPoint())
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self.handle_frame_press(
            event.position().toPoint()
        ):
            event.accept()
            return
        super().mousePressEvent(event)

    # ------------------------------------------------------------ действия

    def _autogrow_input(self) -> None:
        """
        Поле растёт под текст, но не выше заданного предела.

        Считаются строки после переноса, а не по нажатию Enter:
        длинная ссылка (SoundCloud с хвостом ?si=…&utm_…) занимает
        несколько строк, и при высоте в одну строку поле прокручивалось
        к её концу — начало ссылки пропадало из вида.
        """
        editor = self.url_input
        doc = editor.document()
        layout = doc.documentLayout()
        content = 0.0
        block = doc.begin()
        while block.isValid():
            content += layout.blockBoundingRect(block).height()
            block = block.next()
        content += doc.documentMargin() * 2

        line_height = editor.fontMetrics().lineSpacing()
        limit = SIZE["input_max"] - 20
        inner = int(max(line_height + 4, min(content, limit)))
        if editor.height() != inner:
            editor.setFixedHeight(inner)
            self.input_shell.setFixedHeight(inner + 20)
        if content <= limit:
            # Всё помещается — показываем текст с начала
            editor.verticalScrollBar().setValue(0)

    def _detect_platforms(self, text: str) -> set[str]:
        found = set()
        low = text.lower()
        if "soundcloud.com" in low or "snd.sc" in low:
            found.add("soundcloud")
        if "youtube.com" in low or "youtu.be" in low:
            found.add("youtube")
        if "bandcamp.com" in low:
            found.add("bandcamp")
        return found

    def _update_platform_chips(self, text: str) -> None:
        active = self._detect_platforms(text)
        for key, chip in self.platform_chips.items():
            chip.setProperty("active", "yes" if key in active else "")
            chip.style().unpolish(chip)
            chip.style().polish(chip)
            for child in chip.findChildren(QLabel):
                child.style().unpolish(child)
                child.style().polish(child)

    def eventFilter(self, obj, event):  # noqa: N802 (интерфейс Qt)
        """Рамка поля подсвечивается, когда фокус внутри него."""
        if obj is self.url_input and event.type() == event.Type.Resize:
            # Ширина поля изменилась — перенос строк пересчитан, высота тоже
            if event.size().width() != event.oldSize().width():
                QTimer.singleShot(0, self._autogrow_input)
        if obj is self.url_input and self.input_shell.property("state") != "error":
            if event.type() == event.Type.FocusIn:
                self._set_input_state("focus")
            elif event.type() == event.Type.FocusOut:
                self._set_input_state("")
        return super().eventFilter(obj, event)

    def _set_input_state(self, state: str) -> None:
        self.input_shell.setProperty("state", state)
        self.input_shell.style().unpolish(self.input_shell)
        self.input_shell.style().polish(self.input_shell)

    def _on_input_changed(self) -> None:
        self._autogrow_input()
        text = self.url_input.toPlainText()
        self.clear_button.setVisible(bool(text.strip()))
        self._update_platform_chips(text)
        if self.input_shell.property("state") == "error":
            self._set_input_state("focus" if self.url_input.hasFocus() else "")
            self.hint_label.setText("")
            self.hint_label.setStyleSheet("")

    def _collect_urls(self) -> list[str]:
        urls, seen = [], set()
        for line in self.url_input.toPlainText().splitlines():
            url = line.strip()
            if url and not url.startswith("#") and url not in seen:
                urls.append(url)
                seen.add(url)
        return urls

    def _show_input_error(self, message: str) -> None:
        self.input_shell.setProperty("state", "error")
        self.input_shell.style().unpolish(self.input_shell)
        self.input_shell.style().polish(self.input_shell)
        self.hint_label.setText(message)
        self.hint_label.setStyleSheet(f"color: {COLORS['error']}; font-size: 11px;")
        self.url_input.setFocus()

    def _check_ffmpeg(self) -> None:
        if not DownloadEngine.ffmpeg_available():
            message = (
                "ffmpeg не найден — конвертация в MP3 и обложки работать не будут. "
                "Положите ffmpeg.exe рядом с Luma.exe."
            )
            self._append_log(message, "error")
            notify(self, "ffmpeg не найден — см. журнал", "error")

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Папка библиотеки", str(self.settings.download_dir)
        )
        if path:
            self.settings.download_dir = path
            self._update_folder_button()
            if self.settings_dialog is not None:
                self.settings_dialog.update_folder(path)

    def _update_folder_button(self) -> None:
        path = Path(self.settings.download_dir)
        parts = path.parts
        short = str(path) if len(parts) <= 2 else str(Path(*parts[-2:]))
        self.folder_button.setText(f"  {short}")
        self.folder_button.setToolTip(f"Папка библиотеки: {path}")

    def _start(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        urls = self._collect_urls()
        if not urls:
            self._show_input_error("Добавьте ссылку — по одной в строке")
            return
        if not any(_URL_RE.match(u) for u in urls):
            self._show_input_error("Это не похоже на ссылку — нужен адрес вида https://…")
            return

        output_dir = Path(self.settings.download_dir)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            notify(self, f"Не удалось создать папку: {exc}", "error")
            return

        self.queue.clear()
        self.log_dialog.clear()
        self._append_log(f"Очередь: {len(urls)} ссыл(ок) → {output_dir}", "info")

        archive = archive_file() if self.settings.skip_downloaded else None
        if archive is not None:
            self._append_log("Режим докачки: скачанные ранее треки пропускаются.", "info")

        self.worker = self._make_worker(urls, output_dir, archive_path=archive)
        self._set_running(True)
        self.worker.start()

    def _make_worker(
        self,
        urls: list[str],
        output_dir: Path,
        archive_path: Path | None,
        force: bool = False,
    ) -> DownloadWorker:
        worker = DownloadWorker(
            urls,
            output_dir,
            self.settings.audio_bitrate,
            archive_path=archive_path,
            force=force,
            clean_titles=self.settings.clean_titles,
            strip_catalog=self.settings.strip_catalog,
            force_320=self.settings.force_320,
        )
        worker.log_message.connect(self._append_log)
        worker.content_resolved.connect(self._on_content_resolved)
        worker.track_started.connect(self._on_track_started)
        worker.track_progress.connect(self._on_track_progress)
        worker.track_completed.connect(self._on_track_completed)
        worker.url_failed.connect(self._on_url_failed)
        worker.status_changed.connect(self._on_status)
        worker.finished_summary.connect(self._on_finished)
        worker.finished.connect(self._on_thread_done)
        return worker

    def _cancel(self) -> None:
        if self.worker and self.worker.isRunning():
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText("Отмена…")
            self.worker.cancel()

    def _redownload(self, key: str) -> None:
        if self.worker and self.worker.isRunning():
            notify(self, "Дождитесь окончания текущей загрузки", "warning")
            return
        card = self.queue.card(key)
        if card is None or not card.state.url:
            return

        state = card.state
        target = (
            Path(state.filepath).parent
            if state.filepath
            else Path(self.settings.download_dir)
        )
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            notify(self, f"Папка недоступна: {exc}", "error")
            return

        state.status = "queued"
        state.percent = 0
        card.refresh()
        self._append_log(f"Повторная загрузка: {state.url}", "info")

        self.worker = self._make_worker(
            [state.url], target, archive_path=None, force=True
        )
        self._set_running(True)
        self.worker.start()

    # -------------------------------------------------------------- сигналы

    def _on_content_resolved(self, data: dict) -> None:
        """Ссылка распознана — показываем карточки до начала загрузки."""
        entries = data.get("entries") or []
        if data.get("is_playlist") and data.get("playlist_title"):
            self._append_log(
                f"Плейлист «{data['playlist_title']}» — {len(entries)} трек(ов)", "info"
            )
        for entry in entries:
            key = entry.get("id") or entry.get("url") or ""
            if not key:
                continue
            state = TrackState(
                key=key,
                title=entry.get("title") or "",
                artist=entry.get("artist") or "",
                source=entry.get("source") or data.get("source", ""),
                duration=entry.get("duration"),
                url=entry.get("url") or "",
                thumbnail=entry.get("thumbnail") or "",
                status="queued",
            )
            self.queue.upsert(state)
            if state.thumbnail:
                self.covers.request(key, state.thumbnail)

    def _on_track_started(self, info: dict) -> None:
        key = info.get("id") or info.get("url") or ""
        if not key:
            return
        state = TrackState(
            key=key,
            title=info.get("title") or "",
            artist=info.get("artist") or "",
            source=info.get("source") or "",
            duration=info.get("duration"),
            url=info.get("url") or "",
            thumbnail=info.get("thumbnail") or "",
            status="downloading",
        )
        self.queue.upsert(state)
        if state.thumbnail:
            self.covers.request(key, state.thumbnail)

    def _on_track_progress(self, key: str, percent: int, title: str, speed: str) -> None:
        if not key:
            return
        if percent >= 100:
            self.queue.set_status(key, "converting")
        else:
            self.queue.set_progress(key, percent, speed)

    def _on_track_completed(self, data: dict) -> None:
        key = data.get("id") or data.get("url") or ""
        if not key:
            return
        state = TrackState(
            key=key,
            title=data.get("title") or "",
            artist=data.get("artist") or "",
            source=data.get("source") or "",
            duration=data.get("duration"),
            url=data.get("url") or "",
            filepath=data.get("filepath") or "",
            status="done" if data.get("cover_embedded") else "no_cover",
            quality=data.get("quality") or {},
        )
        card = self.queue.upsert(state)
        if state.filepath:
            card.load_cover_from_file(Path(state.filepath))

    def _on_url_failed(self, url: str, error: str) -> None:
        self.queue.upsert(
            TrackState(key=url, title=url, url=url, status="error", detail=error)
        )

    def _on_status(self, text: str) -> None:
        self._progress_text = text
        self.queue_counter.setText(text)
        # Кнопка отражает фазу, в которой сейчас движок
        if getattr(self, "_running", False):
            self.start_button.setText(
                "Проверка…" if text.startswith("Проверка") else "Загрузка…"
            )

    def _on_counts_changed(self, done: int, total: int, errors: int) -> None:
        if not total:
            self.queue_counter.setText("")
            self.status_label.setText("Готово к работе")
            return
        # Пока идёт загрузка, в шапке виден ход процесса, а не размер очереди
        self.queue_counter.setText(
            self._progress_text if getattr(self, "_running", False)
            else plural_tracks(total)
        )
        text = f"Загружено: {done} из {total}"
        if errors:
            text += f"  ·  ошибок: {errors}"
        self.status_label.setText(text)

    def _on_finished(self, summary: dict) -> None:
        self.queue.finalize(summary["cancelled"])
        failed = summary["urls_failed"]
        tracks = summary["tracks_done"]

        if summary["cancelled"]:
            self.status_label.setText("Загрузка отменена")
            notify(self, "Загрузка отменена", "warning")
        elif failed:
            self.status_label.setText("Завершено с ошибками")
            notify(self, f"Готово: {tracks} · с ошибками: {len(failed)}", "warning")
        elif tracks:
            self.status_label.setText("Готово")
            notify(self, f"Скачано треков: {tracks}", "success")
        else:
            self.status_label.setText("Готово")

        self._append_log(
            f"Итог: треков — {tracks}, обложек — {summary['covers_embedded']}, "
            f"ошибок — {len(failed)}.",
            "warning" if failed or summary["cancelled"] else "success",
        )
        for url in failed:
            self._append_log(f"  не обработано: {url}", "error")

    def _on_thread_done(self) -> None:
        self._set_running(False)
        self.worker = None
        # Очередь закончилась — в шапке снова её состав, а не ход загрузки
        self._progress_text = ""
        self.queue_counter.setText(plural_tracks(len(self.queue.states())))

    def _on_cover_ready(self, key: str, data: bytes) -> None:
        card = self.queue.card(key)
        if card is not None:
            card.set_cover_data(data)

    # ------------------------------------------------- настройки и журнал

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, engine_update.active_version(), self)
        dialog.check_engine_requested.connect(lambda: self._check_engine(silent=False))
        dialog.folder_change_requested.connect(self._choose_folder)
        self.settings_dialog = dialog
        dialog.exec()
        self.settings_dialog = None

    def _open_log(self) -> None:
        self.log_dialog.show()
        self.log_dialog.raise_()
        self.log_dialog.activateWindow()

    def _check_engine(self, silent: bool) -> None:
        if self.update_worker and self.update_worker.isRunning():
            return
        self.update_worker = EngineUpdateWorker(silent=silent)
        self.update_worker.finished_result.connect(self._on_engine_checked)
        self.update_worker.start()

    def _on_engine_checked(self, result: dict) -> None:
        self.update_worker = None
        status = result.get("status")
        silent = result.get("silent", False)
        version = result.get("latest") or result.get("current", "")

        if status == "updated":
            self._append_log(
                f"Движок обновлён до {version}. Изменения вступят в силу "
                "после перезапуска Luma.",
                "success",
            )
            notify(self, f"Движок обновлён до {version} — нужен перезапуск", "success")
        elif status == "error":
            message = result.get("message", "неизвестная ошибка")
            self._append_log(f"Не удалось проверить обновления: {message}", "warning")
            if not silent:
                notify(self, "Не удалось проверить обновления", "warning")
        elif not silent:
            notify(self, f"Движок актуален ({version})", "success")

        if self.settings_dialog is not None:
            suffix = " · перезапустите Luma" if status == "updated" else ""
            self.settings_dialog.engine_check_finished(f"yt-dlp {version}{suffix}")

    # --------------------------------------------------------- вспомогательное

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.start_button.setEnabled(not running)
        self.start_button.setText("Загрузка…" if running else "Скачать")
        if not getattr(self, "_compact_top", False):
            self.start_button.setIcon(
                icons.icon(
                    "download", 16,
                    COLORS["text_faint"] if running else COLORS["on_accent"],
                )
            )
        self.cancel_button.setVisible(running)
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText("Отменить")
        self.url_input.setReadOnly(running)
        if running:
            self.status_label.setText("Подготовка…")

    def _append_log(self, message: str, level: str = "info") -> None:
        self.log_dialog.append(message, level)
        log.log(
            logging.ERROR if level == "error" else logging.INFO, "[ui] %s", message
        )

    def closeEvent(self, event) -> None:  # noqa: N802 (интерфейс Qt)
        if self.worker and self.worker.isRunning():
            answer = QMessageBox.question(
                self,
                APP_NAME,
                "Идёт загрузка. Отменить и выйти?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.cancel()
            self.worker.wait(5000)
        self.covers.stop()
        self.covers.wait(2000)
        event.accept()
