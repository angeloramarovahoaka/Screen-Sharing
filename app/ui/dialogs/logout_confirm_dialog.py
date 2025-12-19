from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt


class LogoutConfirmDialog(QDialog):
    """Dialog de confirmation de déconnexion avec style personnalisé"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Déconnexion")
        self.setFixedSize(380, 200)
        self.setModal(True)
        self._apply_style()
        self.setup_ui()

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border-radius: 12px;
            }
            QLabel {
                color: #333333;
                background: transparent;
            }
            QLabel#titleLabel {
                color: #1976D2;
                font-size: 16px;
                font-weight: bold;
            }
            QLabel#messageLabel {
                color: #555555;
                font-size: 13px;
            }
            QLabel#iconLabel {
                font-size: 48px;
            }
        """)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        # Titre
        header_layout = QHBoxLayout()

        title_layout = QVBoxLayout()
        title_label = QLabel("Déconnexion")
        title_label.setObjectName("titleLabel")
        title_layout.addWidget(title_label)

        message_label = QLabel("Voulez-vous vraiment vous déconnecter ?")
        message_label.setObjectName("messageLabel")
        title_layout.addWidget(message_label)

        header_layout.addLayout(title_layout)
        layout.addLayout(header_layout)

        # Boutons
        btn_layout = QHBoxLayout()

        cancel_btn = QPushButton("Annuler")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setMinimumHeight(30)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-color: #bbbbbb;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        logout_btn = QPushButton("Se déconnecter")
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.setMinimumHeight(40)
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:pressed {
                background-color: #c62828;
            }
        """)
        logout_btn.clicked.connect(self.accept)
        btn_layout.addWidget(logout_btn)

        layout.addLayout(btn_layout)
