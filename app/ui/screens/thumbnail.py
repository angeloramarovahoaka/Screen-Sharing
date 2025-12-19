from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QMenu, QSizePolicy, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QImage, QPixmap, QColor
from .skeleton import SkeletonPreview


class ScreenThumbnail(QFrame):
    """
    Widget miniature pour afficher un écran dans la liste
    """
    clicked = Signal(str)  # screen_id
    double_clicked = Signal(str)  # screen_id pour zoom
    remove_requested = Signal(str)  # screen_id

    def __init__(self, screen_id, screen_name, parent=None):
        super().__init__(parent)
        self.screen_id = screen_id
        self.screen_name = screen_name
        self.is_selected = False
        self.current_image = None
        self._hovered = False
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(18)
        self._shadow.setOffset(0, 6)
        self._shadow.setColor(QColor(0, 0, 0, 60))
        # Keep the effect attached; toggle via setEnabled() to avoid Qt deleting it.
        self.setGraphicsEffect(self._shadow)
        self._shadow.setEnabled(False)

        self.setFixedSize(200, 140)
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setup_ui()
        self.update_style()

    def setup_ui(self):
        """Configure l'interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Zone d'affichage de l'écran (skeleton animé tant qu'aucune frame)
        self.screen_label = SkeletonPreview()
        self.screen_label.setStyleSheet(
            "QLabel { border-radius: 6px; }"
        )
        layout.addWidget(self.screen_label)

        # Barre d'info
        info_layout = QHBoxLayout()

        # Indicateur de statut
        self.status_indicator = QLabel("🟢")
        self.status_indicator.setFixedSize(20, 20)
        info_layout.addWidget(self.status_indicator)

        # Nom de l'écran
        self.name_label = QLabel(self.screen_name)
        self.name_label.setFont(QFont("Segoe UI", 9))
        # Ensure high contrast on any background (dark text)
        self.name_label.setStyleSheet("color: #111111;")
        info_layout.addWidget(self.name_label)

        info_layout.addStretch()

        # Bouton menu
        self.menu_button = QToolButton()
        self.menu_button.setText("⋮")
        self.menu_button.setPopupMode(QToolButton.InstantPopup)
        # Improve contrast: darker text, subtle hover background
        self.menu_button.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 2px 6px;
                color: #111111;
                background: transparent;
                font-weight: 600;
            }
            QToolButton:hover {
                background-color: rgba(0,0,0,0.04);
                border-radius: 3px;
            }
            QToolButton:pressed {
                background-color: rgba(0,0,0,0.06);
            }
        """)

        menu = QMenu(self.menu_button)
        menu.addAction("🔍 Zoom", lambda: self.double_clicked.emit(self.screen_id))
        menu.addAction("❌ Déconnecter", lambda: self.remove_requested.emit(self.screen_id))
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                color: #111111;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 12px;
            }
            QMenu::item:selected {
                background-color: #f0f0f0;
            }
        """)
        self.menu_button.setMenu(menu)
        info_layout.addWidget(self.menu_button)

        layout.addLayout(info_layout)

    def update_style(self):
        """Met à jour le style selon l'état de sélection"""
        if self.is_selected:
            self.setStyleSheet("""
                QFrame { 
                    background-color: #ffffff; 
                    border: 2px solid #4CAF50;
                    border-radius: 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame { 
                    background-color: #ffffff; 
                    border: 1px solid #eee;
                    border-radius: 8px;
                }
            """)

        # Hover affordance via shadow (don't detach the effect: Qt may delete it)
        self._shadow.setEnabled(self._hovered and not self.is_selected)

    def update_frame(self, image: QImage):
        """Met à jour l'image affichée"""
        self.current_image = image
        if image and not image.isNull():
            # Scale the image to fit the label while keeping aspect ratio
            pix = QPixmap.fromImage(image)
            w = max(1, self.screen_label.width() - 4)
            h = max(1, self.screen_label.height() - 4)
            scaled = pix.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.screen_label.setPixmap(scaled)
        else:
            # Clear pixmap to show skeleton
            self.screen_label.setPixmap(QPixmap())

    def set_selected(self, selected):
        """Définit l'état de sélection"""
        self.is_selected = selected
        self.update_style()

    def set_status(self, connected):
        """Met à jour l'indicateur de statut"""
        self.status_indicator.setText("🟢" if connected else "🔴")

    def mousePressEvent(self, event):
        """Gère le clic"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.screen_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Gère le double-clic"""
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.screen_id)
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self.update_style()
        return super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update_style()
        return super().leaveEvent(event)
