"""
Кастомная рамка окна без потери системных возможностей Windows.

Перетаскивание и изменение размера выполняются через системные
операции Qt (startSystemMove / startSystemResize), поэтому
сохраняются привязка к краям (Aero Snap), двойной клик по заголовку,
сочетания Win+стрелки и обычное поведение в панели задач.

По краям окна оставлена невидимая полоса RESIZE_MARGIN,
за которую окно тянется мышью.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCursor

RESIZE_MARGIN = 6


class FramelessMixin:
    """Подмешивается к QMainWindow/QDialog, которым нужна своя рамка."""

    def init_frameless(self) -> None:
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setMouseTracking(True)
        self._resize_edges = Qt.Edges()
        self._drag_origin: QPoint | None = None
        self._request_rounded_corners()

    # ------------------------------------------------------- системное

    def _request_rounded_corners(self) -> None:
        """Просит DWM скруглить углы окна (Windows 11). Необязательно."""
        if sys.platform != "win32":
            return
        try:
            import ctypes

            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2
            value = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(self.winId()),
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        except Exception:
            pass  # на Windows 10 и ниже углы просто останутся прямыми

    def start_system_move(self) -> bool:
        """Перетаскивание окна средствами системы (работает Aero Snap)."""
        handle = self.windowHandle()
        if handle is not None:
            try:
                return bool(handle.startSystemMove())
            except Exception:
                return False
        return False

    def toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # --------------------------------------------------- изменение размера

    def _edges_at(self, pos: QPoint) -> Qt.Edges:
        if self.isMaximized() or self.isFullScreen():
            return Qt.Edges()
        edges = Qt.Edges()
        margin = RESIZE_MARGIN
        if pos.x() <= margin:
            edges |= Qt.LeftEdge
        if pos.x() >= self.width() - margin:
            edges |= Qt.RightEdge
        if pos.y() <= margin:
            edges |= Qt.TopEdge
        if pos.y() >= self.height() - margin:
            edges |= Qt.BottomEdge
        return edges

    @staticmethod
    def _cursor_for(edges: Qt.Edges) -> Qt.CursorShape:
        left, right = edges & Qt.LeftEdge, edges & Qt.RightEdge
        top, bottom = edges & Qt.TopEdge, edges & Qt.BottomEdge
        if (top and left) or (bottom and right):
            return Qt.SizeFDiagCursor
        if (top and right) or (bottom and left):
            return Qt.SizeBDiagCursor
        if left or right:
            return Qt.SizeHorCursor
        if top or bottom:
            return Qt.SizeVerCursor
        return Qt.ArrowCursor

    def handle_frame_move(self, pos: QPoint) -> None:
        """Меняет курсор у краёв окна. Вызывается из mouseMoveEvent."""
        shape = self._cursor_for(self._edges_at(pos))
        if shape == Qt.ArrowCursor:
            self.unsetCursor()
        else:
            self.setCursor(QCursor(shape))

    def handle_frame_press(self, pos: QPoint) -> bool:
        """Начинает системное изменение размера, если курсор у края."""
        edges = self._edges_at(pos)
        if not edges:
            return False
        handle = self.windowHandle()
        if handle is None:
            return False
        try:
            handle.startSystemResize(edges)
            return True
        except Exception:
            return False
