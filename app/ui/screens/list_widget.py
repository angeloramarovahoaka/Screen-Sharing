from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QGridLayout
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QImage

from .thumbnail import ScreenThumbnail

class ScreenListWidget(QWidget):
    """
    Widget pour afficher la liste des écrans connectés
    """
    screen_selected = Signal(str)
    screen_zoom_requested = Signal(str)
    screen_remove_requested = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.thumbnails = {}
        self.selected_screen = None
        self.setup_ui()
        
    def setup_ui(self):
        """Configure l'interface"""
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Titre
        title = QLabel("📺 Écrans connectés")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("color: #111111; background-color: transparent;")
        layout.addWidget(title)
        
        # Zone de scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #ffffff;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #ffffff;
            }
        """)
        
        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background-color: #ffffff;")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        scroll.setWidget(self.grid_widget)
        layout.addWidget(scroll)
        
        # Message si aucun écran
        self.empty_label = QLabel("Aucun écran connecté.\nCliquez sur 'Ajouter' pour vous connecter à un serveur.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #888888; padding: 50px; background-color: transparent;")
        layout.addWidget(self.empty_label)
        
    def add_screen(self, screen_id, screen_name):
        """Ajoute un écran à la liste"""
        if screen_id in self.thumbnails:
            return
            
        thumbnail = ScreenThumbnail(screen_id, screen_name)
        thumbnail.clicked.connect(self._on_thumbnail_clicked)
        thumbnail.double_clicked.connect(self.screen_zoom_requested.emit)
        thumbnail.remove_requested.connect(self.screen_remove_requested.emit)
        
        self.thumbnails[screen_id] = thumbnail
        self._update_grid()
        self.empty_label.hide()
        
    def remove_screen(self, screen_id):
        """Retire un écran de la liste"""
        if screen_id in self.thumbnails:
            thumbnail = self.thumbnails[screen_id]
            self.grid_layout.removeWidget(thumbnail)
            thumbnail.deleteLater()
            del self.thumbnails[screen_id]
            
            if self.selected_screen == screen_id:
                self.selected_screen = None
                
            self._update_grid()
            
            if not self.thumbnails:
                self.empty_label.show()
                
    def update_screen_frame(self, screen_id, image: QImage):
        """Met à jour la frame d'un écran"""
        if screen_id in self.thumbnails:
            self.thumbnails[screen_id].update_frame(image)
            
    def _update_grid(self):
        """Réorganise la grille des miniatures"""
        # Retirer tous les widgets
        for i in reversed(range(self.grid_layout.count())):
            self.grid_layout.itemAt(i).widget().setParent(None)
            
        # Réajouter dans la grille
        cols = 3
        for i, thumbnail in enumerate(self.thumbnails.values()):
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(thumbnail, row, col)
            
    def _on_thumbnail_clicked(self, screen_id):
        """Gère le clic sur une miniature"""
        if self.selected_screen and self.selected_screen in self.thumbnails:
            self.thumbnails[self.selected_screen].set_selected(False)
            
        self.selected_screen = screen_id
        self.thumbnails[screen_id].set_selected(True)
        self.screen_selected.emit(screen_id)