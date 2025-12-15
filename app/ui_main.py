"""
Fenêtre principale de l'application
"""
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame, QSplitter, QMessageBox, QDialog,
    QLineEdit, QFormLayout, QToolBar, QStatusBar, QApplication, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QAction, QIcon

from .config import app_state
from .client_module import ScreenClient, MultiScreenClient
from .server_module import ScreenServer
from .ui_login import LoginWindow, UserInfoWidget
from .ui_screens import ScreenListWidget, ScreenViewer, ScreenThumbnail
from .call_module import AudioCall, CallDialog, CallWidget, PYAUDIO_AVAILABLE
from .ui_style import THEME, ToastOverlay, button_solid, button_outline, status_badge


def _ui_debug(msg: str):
    if os.getenv("SS_UI_DEBUG", "0") == "1":
        print(f"[UI_DEBUG] {msg}", flush=True)


class AddScreenDialog(QDialog):
    """Dialog pour ajouter une nouvelle connexion d'écran"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajouter un écran")
        self.setFixedSize(400, 200)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Titre
        title = QLabel("🖥️ Connexion à un écran distant")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(title)
        
        # Formulaire
        form_layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Mon PC Bureau")
        form_layout.addRow("Nom:", self.name_input)
        
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.1.100")
        form_layout.addRow("Adresse IP:", self.ip_input)
        
        layout.addLayout(form_layout)
        
        # Boutons
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        connect_btn = QPushButton("Connecter")
        connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        connect_btn.clicked.connect(self.accept)
        btn_layout.addWidget(connect_btn)
        
        layout.addLayout(btn_layout)
        
    def get_values(self):
        return self.name_input.text().strip(), self.ip_input.text().strip()


class MainWindow(QMainWindow):
    """
    Fenêtre principale de l'application Screen Sharing
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screen Sharing - Remote Desktop")
        self.setMinimumSize(1200, 800)
        
        # Composants
        self.multi_client = MultiScreenClient()
        self.server = ScreenServer()
        self.audio_call = AudioCall()
        
        # Vues
        self.current_zoomed_screen = None
        self.screen_viewers = {}
        self._pre_zoom_window_state = None
        
        # Configuration de l'interface
        self.setup_ui()
        self.setup_connections()
        
        # Timer pour mise à jour des miniatures
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_thumbnails)
        self.update_timer.start(100)  # 10 FPS pour les miniatures
        
    def setup_ui(self):
        """Configure l'interface principale"""
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Barre utilisateur
        self.user_bar = UserInfoWidget()
        self.user_bar.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-bottom: 1px solid #ddd;
            }
        """)
        main_layout.addWidget(self.user_bar)
        
        # Widget d'appel
        self.call_widget = CallWidget()
        main_layout.addWidget(self.call_widget)
        
        # Barre d'outils
        toolbar = QFrame()
        toolbar.setFixedHeight(50)
        toolbar.setStyleSheet("""
            QFrame {
                background-color: white;
                border-bottom: 1px solid #e0e0e0;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(15, 5, 15, 5)
        
        # Boutons de la barre d'outils
        self.add_screen_btn = QPushButton("➕ Ajouter écran")
        self.add_screen_btn.setCursor(Qt.PointingHandCursor)
        self.add_screen_btn.setStyleSheet(button_outline(THEME.success, hover_bg="rgba(76,175,80,0.10)", padding="9px 14px"))
        self.add_screen_btn.setMinimumHeight(38)
        toolbar_layout.addWidget(self.add_screen_btn)
        
        self.share_screen_btn = QPushButton("📤 Partager mon écran")
        self.share_screen_btn.setCursor(Qt.PointingHandCursor)
        self.share_screen_btn.setStyleSheet(button_solid(THEME.primary, THEME.primary_hover, padding="11px 18px"))
        self.share_screen_btn.setMinimumHeight(40)
        toolbar_layout.addWidget(self.share_screen_btn)
        
        toolbar_layout.addStretch()

        # Badge d'état global (Idle / Connected / Streaming)
        self.app_status_badge = QLabel("Idle")
        self.app_status_badge.setStyleSheet(status_badge(THEME.danger))
        self.app_status_badge.setAlignment(Qt.AlignCenter)
        toolbar_layout.addWidget(self.app_status_badge)
        
        main_layout.addWidget(toolbar)
        
        # Zone principale avec stack
        self.content_stack = QStackedWidget()
        
        # Page 1: Liste des écrans
        self.screen_list = ScreenListWidget()
        self.content_stack.addWidget(self.screen_list)
        
        # Page 2: Vue zoom (sera ajoutée dynamiquement)
        self.zoom_container = QWidget()
        self.zoom_layout = QVBoxLayout(self.zoom_container)
        self.zoom_layout.setContentsMargins(0, 0, 0, 0)
        self.content_stack.addWidget(self.zoom_container)
        
        main_layout.addWidget(self.content_stack)

        # Toast overlay (snackbar)
        self.toast = ToastOverlay(central_widget)
        self.toast.setGeometry(central_widget.rect())
        
        # Barre de statut
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Prêt")

        self._refresh_app_status()

    def _set_app_status(self, status: str):
        status = (status or "Idle").strip()
        if status.lower() == "streaming":
            self.app_status_badge.setText("Streaming")
            self.app_status_badge.setStyleSheet(status_badge(THEME.success))
        elif status.lower() == "connected":
            self.app_status_badge.setText("Connected")
            self.app_status_badge.setStyleSheet(status_badge("#FFB300", fg="#1a1a1a"))
        else:
            self.app_status_badge.setText("Idle")
            self.app_status_badge.setStyleSheet(status_badge(THEME.danger))

    def _refresh_app_status(self):
        # Streaming local takes precedence.
        if getattr(self.server, "is_streaming", False):
            self._set_app_status("Streaming")
            return

        # Any connected remote screen client => Connected
        if getattr(self.multi_client, "clients", None) and len(self.multi_client.clients) > 0:
            self._set_app_status("Connected")
        else:
            self._set_app_status("Idle")
        
    def setup_connections(self):
        """Configure les connexions de signaux"""
        # Barre utilisateur
        self.user_bar.logout_requested.connect(self.handle_logout)
        
        # Boutons toolbar
        self.add_screen_btn.clicked.connect(self.show_add_screen_dialog)
        self.share_screen_btn.clicked.connect(self.toggle_screen_sharing)
        
        # Liste des écrans
        self.screen_list.screen_selected.connect(self._on_screen_selected)
        self.screen_list.screen_zoom_requested.connect(self.zoom_screen)
        self.screen_list.screen_remove_requested.connect(self.remove_screen)
        
        # Multi-client
        self.multi_client.screen_updated.connect(self._on_screen_frame_updated)
        
        # Serveur
        self.server.status_changed.connect(lambda s: self.status_bar.showMessage(s))
        self.server.status_changed.connect(lambda _s: self._refresh_app_status())
        self.server.client_connected.connect(lambda c: self.status_bar.showMessage(f"Client connecté: {c}"))
        
        # Appel
        self.call_widget.end_call_requested.connect(self.end_call)
        self.call_widget.mute_toggled.connect(self.toggle_mute)
        self.audio_call.call_started.connect(lambda: self.call_widget.start_call(self.audio_call.peer_ip))
        self.audio_call.call_ended.connect(self.call_widget.end_call)
        
    def set_user(self, username):
        """Définit l'utilisateur connecté"""
        self.user_bar.set_username(username)
        self.status_bar.showMessage(f"Connecté en tant que {username}")
        
    def handle_logout(self):
        """Gère la déconnexion"""
        reply = QMessageBox.question(
            self,
            "Déconnexion",
            "Voulez-vous vraiment vous déconnecter ?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Fermer toutes les connexions
            self.multi_client.disconnect_all()
            self.server.stop()
            self.audio_call.end_call()
            
            # Vider la liste
            for screen_id in list(self.screen_list.thumbnails.keys()):
                self.screen_list.remove_screen(screen_id)
                
            app_state.logout()
            self.close()
            
    def show_add_screen_dialog(self):
        """Affiche le dialog d'ajout d'écran"""
        dialog = AddScreenDialog(self)
        if dialog.exec() == QDialog.Accepted:
            name, ip = dialog.get_values()
            if name and ip:
                self.add_screen(name, ip)
                
    def add_screen(self, name, ip):
        """Ajoute une connexion à un écran distant"""
        screen_id = f"{name}_{ip}"
        
        # Créer le client
        client = ScreenClient()
        
        if client.connect_to_server(ip):
            # Stocker le client
            self.multi_client.clients[screen_id] = client
            
            # Connecter les signaux
            client.frame_received.connect(
                lambda img, sid=screen_id: self._on_screen_frame_updated(sid, img)
            )
            
            # Ajouter à la liste visuelle
            self.screen_list.add_screen(screen_id, name)
            self.status_bar.showMessage(f"Connecté à {name} ({ip})")
            self.toast.show_toast(f"Connexion réussie: {name} ({ip})", kind="success")
            self._refresh_app_status()
        else:
            QMessageBox.warning(
                self,
                "Erreur de connexion",
                f"Impossible de se connecter à {ip}"
            )
            self.toast.show_toast(f"Connexion impossible: {ip}", kind="error")
            
    def remove_screen(self, screen_id):
        """Déconnecte et retire un écran"""
        if screen_id in self.multi_client.clients:
            self.multi_client.clients[screen_id].disconnect()
            del self.multi_client.clients[screen_id]
            
        self.screen_list.remove_screen(screen_id)

        self._refresh_app_status()
        
        # Revenir à la liste si on était en zoom sur cet écran
        if self.current_zoomed_screen == screen_id:
            self.close_zoom()
            
    def zoom_screen(self, screen_id):
        """Ouvre la vue zoom pour un écran"""
        if screen_id not in self.multi_client.clients:
            return
            
        client = self.multi_client.clients[screen_id]
        
        # Nettoyer complètement l'ancien viewer s'il existe
        if self.current_zoomed_screen and self.current_zoomed_screen in self.screen_viewers:
            old_viewer = self.screen_viewers[self.current_zoomed_screen]
            # Déconnecter les signaux
            old_client = self.multi_client.clients.get(self.current_zoomed_screen)
            if old_client:
                try:
                    old_client.frame_received.disconnect(old_viewer.update_frame)
                except:
                    pass
            # Retirer du layout et supprimer
            self.zoom_layout.removeWidget(old_viewer)
            old_viewer.deleteLater()
            del self.screen_viewers[self.current_zoomed_screen]
        
        # Créer le nouveau viewer
        viewer = ScreenViewer(screen_id, client)
        viewer.close_requested.connect(self.close_zoom)
        
        # Connecter les frames
        client.frame_received.connect(viewer.update_frame)
            
        # Ajouter le nouveau
        self.zoom_layout.addWidget(viewer)
        self.screen_viewers[screen_id] = viewer
        self.current_zoomed_screen = screen_id
        
        # Afficher la vue zoom
        self.content_stack.setCurrentIndex(1)

        _ui_debug(
            "MainWindow.zoom_screen "
            f"main={self.width()}x{self.height()} state={int(self.windowState())} "
            f"central={self.centralWidget().width()}x{self.centralWidget().height()}"
        )

        # Forcer le plein écran en mode zoom
        if self._pre_zoom_window_state is None:
            self._pre_zoom_window_state = self.windowState()
        self.showFullScreen()

        _ui_debug(
            "MainWindow.zoom_screen(after fullscreen) "
            f"main={self.width()}x{self.height()} state={int(self.windowState())}"
        )
        
    def close_zoom(self):
        """Ferme la vue zoom et revient à la liste"""
        # Nettoyer complètement le viewer actuel
        if self.current_zoomed_screen and self.current_zoomed_screen in self.screen_viewers:
            viewer = self.screen_viewers[self.current_zoomed_screen]
            # Déconnecter les signaux
            client = self.multi_client.clients.get(self.current_zoomed_screen)
            if client:
                try:
                    client.frame_received.disconnect(viewer.update_frame)
                except:
                    pass
            # Retirer du layout et supprimer
            self.zoom_layout.removeWidget(viewer)
            viewer.deleteLater()
            del self.screen_viewers[self.current_zoomed_screen]
        
        self.content_stack.setCurrentIndex(0)
        self.current_zoomed_screen = None

        _ui_debug(
            "MainWindow.close_zoom(before restore) "
            f"main={self.width()}x{self.height()} state={int(self.windowState())}"
        )

        # Restaurer l'état précédent
        if self._pre_zoom_window_state is not None:
            prev = self._pre_zoom_window_state
            self._pre_zoom_window_state = None
            self.showNormal()
            if prev & Qt.WindowMaximized:
                self.showMaximized()

        _ui_debug(
            "MainWindow.close_zoom(after restore) "
            f"main={self.width()}x{self.height()} state={int(self.windowState())}"
        )
        
    def toggle_screen_sharing(self):
        """Active/désactive le partage d'écran local"""
        if self.server.is_streaming:
            # Arrêter le streaming
            self.server.stop_streaming()
            self.share_screen_btn.setText("📤 Partager mon écran")
            self.share_screen_btn.setStyleSheet(button_solid(THEME.primary, THEME.primary_hover, padding="11px 18px"))
            self.toast.show_toast("Partage arrêté", kind="info")
            self._refresh_app_status()
        else:
            # Demander l'IP du client
            dialog = QDialog(self)
            dialog.setWindowTitle("Partager l'écran")
            layout = QVBoxLayout(dialog)
            
            label = QLabel("Adresse IP du client qui recevra le flux:")
            layout.addWidget(label)
            
            ip_input = QLineEdit()
            ip_input.setPlaceholderText("192.168.1.100")
            layout.addWidget(ip_input)
            
            webcam_checkbox = QCheckBox("Utiliser la webcam au lieu de l'écran")
            layout.addWidget(webcam_checkbox)
            
            btn_layout = QHBoxLayout()
            cancel_btn = QPushButton("Annuler")
            cancel_btn.clicked.connect(dialog.reject)
            btn_layout.addWidget(cancel_btn)
            
            start_btn = QPushButton("Démarrer")
            start_btn.clicked.connect(dialog.accept)
            btn_layout.addWidget(start_btn)
            layout.addLayout(btn_layout)
            
            if dialog.exec() == QDialog.Accepted:
                client_ip = ip_input.text().strip()
                if client_ip:
                    self.server.use_webcam = webcam_checkbox.isChecked()
                    self.server.add_client(client_ip)
                    # Démarrer le serveur si pas encore lancé
                    if not self.server.is_running:
                        self.server.start(client_ip)
                    # Démarrer le streaming vidéo
                    self.server.start_streaming()
                    self.share_screen_btn.setText("🛑 Arrêter le partage")
                    self.share_screen_btn.setStyleSheet(button_solid(THEME.danger, THEME.danger_hover, padding="11px 18px"))
                    self.toast.show_toast(f"Streaming démarré vers {client_ip}", kind="success")
                    self._refresh_app_status()
                    
    def show_call_dialog(self):
        """Affiche le dialog pour passer un appel"""
        if self.audio_call.is_in_call:
            return
            
        dialog = CallDialog(self)
        dialog.call_requested.connect(self.start_call)
        dialog.exec()
        
    def start_call(self, peer_ip):
        """Démarre un appel"""
        if self.audio_call.start_call(peer_ip):
            self.status_bar.showMessage(f"Appel en cours avec {peer_ip}")
            self.toast.show_toast(f"Appel démarré: {peer_ip}", kind="success")
        else:
            QMessageBox.warning(self, "Erreur", "Impossible de démarrer l'appel")
            self.toast.show_toast("Impossible de démarrer l'appel", kind="error")
            
    def end_call(self):
        """Termine l'appel"""
        self.audio_call.end_call()
        self.status_bar.showMessage("Appel terminé")
        self.toast.show_toast("Appel terminé", kind="info")
        
    def toggle_mute(self):
        """Bascule le mode muet"""
        muted = self.audio_call.toggle_mute()
        self.call_widget.set_muted(muted)
        
    def _on_screen_selected(self, screen_id):
        """Callback quand un écran est sélectionné"""
        self.status_bar.showMessage(f"Écran sélectionné: {screen_id}")
        
    def _on_screen_frame_updated(self, screen_id, image):
        """Callback quand une frame est mise à jour"""
        # Mettre à jour la miniature
        self.screen_list.update_screen_frame(screen_id, image)
        
    def _update_thumbnails(self):
        """Met à jour périodiquement les miniatures"""
        # Géré automatiquement par les signaux maintenant
        pass
        
    def closeEvent(self, event):
        """Gère la fermeture de la fenêtre"""
        # Nettoyer les ressources
        self.multi_client.disconnect_all()
        self.server.stop()
        self.audio_call.cleanup()
        event.accept()
