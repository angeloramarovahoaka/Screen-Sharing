from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QFont, QColor, QLinearGradient

class SkeletonPreview(QLabel):
    """Preview area with an animated skeleton shimmer until a pixmap is set."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(190, 100)
        self.setText("📺 En attente…")

    def _tick(self):
        # Only animate when we don't have a real pixmap.
        pm = self.pixmap()
        if pm is not None and not pm.isNull():
            return
        self._phase = (self._phase + 0.035) % 1.0
        self.update()

    def paintEvent(self, event):
        pm = self.pixmap()
        if pm is not None and not pm.isNull():
            return super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        r = self.rect()

        # Background
        painter.fillRect(r, QColor("#1a1a1a"))

        # Shimmer
        w = max(1, r.width())
        offset = int((self._phase * (w + 120)) - 120)
        grad = QLinearGradient(offset, 0, offset + 120, 0)
        grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        grad.setColorAt(0.5, QColor(255, 255, 255, 26))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(r, grad)

        # Text hint
        painter.setPen(QColor("#666"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(r, Qt.AlignCenter, self.text())

        painter.end()