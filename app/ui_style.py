"""UI helpers (styles, toasts, small components).

Kept intentionally small to avoid a full design-system rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFrame,
    QLabel,
    QGraphicsOpacityEffect,
)


@dataclass(frozen=True)
class UiTheme:
    # Reuse existing colors already hard-coded across the project.
    primary: str = "#2196F3"
    primary_hover: str = "#1976D2"

    success: str = "#4CAF50"
    success_hover: str = "#43A047"

    danger: str = "#f44336"
    danger_hover: str = "#d32f2f"

    accent: str = "#9C27B0"
    accent_hover: str = "#7B1FA2"

    text: str = "#333"
    muted: str = "#666"
    border: str = "#ddd"
    surface: str = "#ffffff"
    surface_alt: str = "#f5f5f5"


THEME = UiTheme()


def button_solid(bg: str, hover: str, *, radius: int = 8, padding: str = "10px 18px") -> str:
    return f"""
        QPushButton {{
            background-color: {bg};
            color: white;
            border: none;
            border-radius: {radius}px;
            padding: {padding};
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {hover};
        }}
        QPushButton:pressed {{
            background-color: {hover};
        }}
        QPushButton:disabled {{
            background-color: #ccc;
            color: #666;
        }}
    """


def button_outline(color: str, hover_bg: str = "rgba(33,150,243,0.08)", *, radius: int = 8, padding: str = "10px 18px") -> str:
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {color};
            border: 2px solid {color};
            border-radius: {radius}px;
            padding: {padding};
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {hover_bg};
        }}
        QPushButton:pressed {{
            background-color: {hover_bg};
        }}
        QPushButton:disabled {{
            border-color: #ccc;
            color: #999;
        }}
    """


def status_badge(bg: str, fg: str = "white") -> str:
    return f"""
        QLabel {{
            background-color: {bg};
            color: {fg};
            border-radius: 10px;
            padding: 4px 10px;
            font-weight: bold;
        }}
    """


class ToastOverlay(QWidget):
    """Small snackbar/toast overlay.

    Usage:
        overlay = ToastOverlay(parent_widget)
        overlay.show_toast("Connected", kind="success")
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)
        self._layout.setAlignment(Qt.AlignTop | Qt.AlignRight)

        self.hide()

    def resizeEvent(self, event):
        # Always cover the parent.
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        return super().resizeEvent(event)

    def show_toast(self, message: str, *, kind: str = "info", duration_ms: int = 2500):
        self.show()

        if kind == "success":
            bg = THEME.success
        elif kind == "error":
            bg = THEME.danger
        else:
            bg = THEME.primary

        toast = QFrame(self)
        toast.setObjectName("toast")
        toast.setStyleSheet(
            f"""
            QFrame#toast {{
                background-color: {bg};
                border-radius: 10px;
            }}
            QLabel {{
                color: white;
                padding: 10px 12px;
                font-weight: bold;
            }}
            """
        )

        label = QLabel(message, toast)
        label.setWordWrap(True)

        layout = QVBoxLayout(toast)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label)

        # Fade in
        effect = QGraphicsOpacityEffect(toast)
        toast.setGraphicsEffect(effect)
        effect.setOpacity(0.0)

        anim_in = QPropertyAnimation(effect, b"opacity", toast)
        anim_in.setDuration(120)
        anim_in.setStartValue(0.0)
        anim_in.setEndValue(1.0)
        anim_in.start(QPropertyAnimation.DeleteWhenStopped)

        self._layout.addWidget(toast)

        def _hide_and_delete():
            anim_out = QPropertyAnimation(effect, b"opacity", toast)
            anim_out.setDuration(180)
            anim_out.setStartValue(1.0)
            anim_out.setEndValue(0.0)

            def _cleanup():
                self._layout.removeWidget(toast)
                toast.deleteLater()
                if self._layout.count() == 0:
                    self.hide()

            anim_out.finished.connect(_cleanup)
            anim_out.start(QPropertyAnimation.DeleteWhenStopped)

        QTimer.singleShot(duration_ms, _hide_and_delete)
