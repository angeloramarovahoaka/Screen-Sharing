"""
app/ui/__init__.py
"""
import sys
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QMessageBox)
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QPixmap, QCursor

# Import depuis votre module client
from app.client.screen_client import ScreenClient

class LoginWindow(QWidget):
    login_successful = Signal(str)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login")
        self.resize(300, 150)
        layout = QVBoxLayout(self)
        self.ip_input = QLineEdit("127.0.0.1") # IP par défaut
        self.connect_btn = QPushButton("Se connecter")
        self.connect_btn.clicked.connect(self.do_login)
        layout.addWidget(QLabel("IP Serveur:"))
        layout.addWidget(self.ip_input)
        layout.addWidget(self.connect_btn)

    def do_login(self):
        ip = self.ip_input.text()
        if ip: self.login_successful.emit(ip)

class MainWindow(QMainWindow):
    logged_out = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screen Viewer")
        self.resize(1280, 720)
        
        # Client
        self.client = ScreenClient()
        self.client.frame_received.connect(self.update_image)
        self.client.status_changed.connect(lambda s: print(f"Status: {s}"))
        self.client.disconnected.connect(self.close)
        
        # --- CONNEXION DU SIGNAL DE MODE CAPTURE ---
        self.client.capture_mode_changed.connect(self.on_capture_mode_changed)

        # UI
        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.layout = QVBoxLayout(self.central)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.video_label = QLabel("Connexion...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background: black; color: white;")
        self.layout.addWidget(self.video_label)
        
        # Mouse tracking pour envoyer les mouvements même sans cliquer
        self.central.setMouseTracking(True)
        self.video_label.setMouseTracking(True)

    def set_user(self, ip):
        self.client.connect_to_server(ip)

    # --- CLIC POUR ACTIVER LE MODE VM ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.client.is_connected:
            # Active le mode capture si pas déjà actif
            if not self.client.grabber.is_captured:
                self.client.start_capture_mode()
            else:
                # Si on est déjà en mode capture, on envoie le clic
                w, h = self.video_label.width(), self.video_label.height()
                self.client.send_mouse_click(event.x(), event.y(), w, h, 'left', 'press')
        elif event.button() == Qt.RightButton and self.client.is_connected:
             w, h = self.video_label.width(), self.video_label.height()
             self.client.send_mouse_click(event.x(), event.y(), w, h, 'right', 'press')
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.client.is_connected:
            btn = 'left' if event.button() == Qt.LeftButton else 'right'
            w, h = self.video_label.width(), self.video_label.height()
            self.client.send_mouse_click(event.x(), event.y(), w, h, btn, 'release')

    def mouseMoveEvent(self, event):
        if self.client.is_connected:
            w, h = self.video_label.width(), self.video_label.height()
            self.client.send_mouse_move(event.x(), event.y(), w, h)

    # --- CHANGEMENT VISUEL (SOURIS/TITRE) ---
    @Slot(bool)
    def on_capture_mode_changed(self, active):
        if active:
            # Mode VM : on cache la souris locale et change le titre
            self.setCursor(Qt.BlankCursor)
            self.setWindowTitle("CONTROLE TOTAL (CTRL-DROIT pour sortir)")
        else:
            # Mode Normal : souris visible
            self.setCursor(Qt.ArrowCursor)
            self.setWindowTitle("Screen Viewer (Cliquer pour contrôler)")

    @Slot(QImage)
    def update_image(self, img):
        self.video_label.setPixmap(QPixmap.fromImage(img))

    def closeEvent(self, event):
        self.client.disconnect()
        self.logged_out.emit()
        event.accept()