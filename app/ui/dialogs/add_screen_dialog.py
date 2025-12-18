from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QLineEdit, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ...config import COMMAND_PORT, VIDEO_PORT
from app.client.discovery import DiscoveryScanner


class AddScreenDialog(QDialog):
    """Dialog pour ajouter une nouvelle connexion d'écran - avec découverte automatique"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recevoir un écran partagé")
        self.setMinimumSize(450, 420)
        self.selected_server = None
        self.scanner = DiscoveryScanner()
        self.setup_ui()
        self._apply_style()
        self._start_scan()

    def _apply_style(self):
        """Applique un style explicite pour supporter le mode sombre"""
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                color: #333333;
            }
            QLabel {
                color: #333333;
                background: transparent;
            }
            QLineEdit {
                background-color: #ffffff;
                color: #333333;
                border: 2px solid #ddd;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #2196F3;
            }
            QLineEdit::placeholder {
                color: #999999;
            }
            QListWidget {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                background-color: #ffffff;
                color: #333333;
                padding: 12px;
                border-bottom: 1px solid #eee;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976D2;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
            QFrame#manualFrame {
                background-color: #f5f5f5;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }
        """)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Titre
        title = QLabel(" Écrans partagés disponibles")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: #1976D2; background: transparent;")
        layout.addWidget(title)

        # Indication
        self.status_label = QLabel(" Recherche en cours...")
        self.status_label.setStyleSheet("color: #666666; font-style: italic; background: transparent;")
        layout.addWidget(self.status_label)

        # Liste des serveurs disponibles
        self.server_list = QListWidget()
        self.server_list.setMinimumHeight(150)
        self.server_list.itemClicked.connect(self._on_server_selected)
        self.server_list.itemDoubleClicked.connect(self._on_server_double_clicked)
        layout.addWidget(self.server_list)

        # Section manuelle
        manual_frame = QFrame()
        manual_frame.setObjectName("manualFrame")
        manual_layout = QVBoxLayout(manual_frame)
        manual_layout.setSpacing(10)
        manual_layout.setContentsMargins(12, 12, 12, 12)

        manual_title = QLabel("Ou entrer l'IP manuellement:")
        manual_title.setFont(QFont("Segoe UI", 10))
        manual_title.setStyleSheet("color: #555555; background: transparent;")
        manual_layout.addWidget(manual_title)

        manual_row = QHBoxLayout()
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.1.100")
        self.ip_input.setMinimumHeight(38)
        self.ip_input.returnPressed.connect(self._on_manual_connect)
        manual_row.addWidget(self.ip_input)

        self.manual_connect_btn = QPushButton("Connecter")
        self.manual_connect_btn.setMinimumHeight(38)
        self.manual_connect_btn.setCursor(Qt.PointingHandCursor)
        self.manual_connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        self.manual_connect_btn.clicked.connect(self._on_manual_connect)
        manual_row.addWidget(self.manual_connect_btn)

        manual_layout.addLayout(manual_row)
        layout.addWidget(manual_frame)

        # Boutons du bas
        btn_layout = QHBoxLayout()

        self.refresh_btn = QPushButton(" Actualiser")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self._start_scan)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 6px;
                padding: 10px 18px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:disabled {
                background-color: #f5f5f5;
                color: #999999;
            }
        """)
        btn_layout.addWidget(self.refresh_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton("Annuler")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 6px;
                padding: 10px 18px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        btn_layout.addWidget(cancel_btn)

        self.connect_btn = QPushButton("Se connecter")
        self.connect_btn.setCursor(Qt.PointingHandCursor)
        self.connect_btn.setEnabled(False)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #43A047;
            }
            QPushButton:pressed {
                background-color: #388E3C;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """)
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        btn_layout.addWidget(self.connect_btn)

        layout.addLayout(btn_layout)

        # Connecter les signaux du scanner
        self.scanner.server_found.connect(self._on_server_found)
        self.scanner.scan_finished.connect(self._on_scan_finished)

    def _start_scan(self):
        """Lance le scan des serveurs"""
        self.server_list.clear()
        self.selected_server = None
        self.connect_btn.setEnabled(False)
        self.status_label.setText("Recherche en cours...")
        self.status_label.setStyleSheet("color: #666666; font-style: italic; background: transparent;")
        self.refresh_btn.setEnabled(False)
        self.scanner.start_scan(duration=3.0)

    def _on_server_found(self, server_info):
        """Appelé quand un serveur est trouvé"""
        item = QListWidgetItem()
        item.setText(f"🖥️ {server_info['name']}\n      {server_info['ip']}")
        item.setData(Qt.UserRole, server_info)
        self.server_list.addItem(item)

        # Mettre à jour le statut
        count = self.server_list.count()
        self.status_label.setText(f" {count} écran(s) trouvé(s)")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; background: transparent;")

    def _on_scan_finished(self):
        """Appelé quand le scan est terminé"""
        self.refresh_btn.setEnabled(True)
        if self.server_list.count() == 0:
            self.status_label.setText(" Aucun écran partagé trouvé sur le réseau")
            self.status_label.setStyleSheet("color: #f44336; background: transparent;")

    def _on_server_selected(self, item):
        """Appelé quand un serveur est sélectionné"""
        self.selected_server = item.data(Qt.UserRole)
        self.connect_btn.setEnabled(True)

    def _on_server_double_clicked(self, item):
        """Double-clic = sélection + connexion"""
        self.selected_server = item.data(Qt.UserRole)
        self.accept()

    def _on_connect_clicked(self):
        """Bouton connecter cliqué"""
        if self.selected_server:
            self.accept()

    def _on_manual_connect(self):
        """Connexion manuelle via IP"""
        ip = self.ip_input.text().strip()
        if ip:
            self.selected_server = {
                'name': ip,  # Utiliser l'IP comme nom par défaut
                'ip': ip,
                'port': COMMAND_PORT,
                'video_port': VIDEO_PORT
            }
            self.accept()

    def get_values(self):
        """Retourne (name, ip) du serveur sélectionné"""
        if self.selected_server:
            return self.selected_server['name'], self.selected_server['ip']
        return None, None

    def closeEvent(self, event):
        """Arrête le scanner à la fermeture"""
        self.scanner.stop_scan()
        super().closeEvent(event)
