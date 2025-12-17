"""
Fenêtre principale de l'application
"""
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame, QSplitter, QMessageBox, QDialog,
    QLineEdit, QFormLayout, QToolBar, QStatusBar, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QAction, QIcon

from .config import app_state
from .client_module import ScreenClient, MultiScreenClient
from .server_module import ScreenServer
from .ui_login import LoginWindow, UserInfoWidget
from .ui_screens import ScreenListWidget, ScreenViewer, ScreenThumbnail
from .ui_style import THEME, ToastOverlay, button_solid, button_outline, status_badge


def _ui_debug(msg: str):
    if os.getenv("SS_UI_DEBUG", "0") == "1":
        print(f"[UI_DEBUG] {msg}", flush=True)


def _qt_flag_to_int(flag) -> int:
    try:
        return int(flag)
    except TypeError:
        return int(getattr(flag, "value", 0))


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
        name_label = QLabel("Nom:")
        form_layout.addRow(name_label, self.name_input)
        
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.1.100")
        ip_label = QLabel("Adresse IP:")
        form_layout.addRow(ip_label, self.ip_input)
        
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
    # Signal émis quand l'utilisateur se déconnecte (retourner à l'écran de login)
    logged_out = Signal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screen Sharing - Remote Desktop")
        self.setMinimumSize(1200, 800)
        
        # Composants
        self.multi_client = MultiScreenClient()
        self.server = ScreenServer()
        
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
        
        # (Call UI removed)
        
        # Barre d'outils
        self.main_toolbar = QFrame()
        self.main_toolbar.setFixedHeight(50)
        self.main_toolbar.setStyleSheet("""
            QFrame {
                background-color: white;
                border-bottom: 1px solid #e0e0e0;
            }
        """)
        toolbar_layout = QHBoxLayout(self.main_toolbar)
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
        
        main_layout.addWidget(self.main_toolbar)
        
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
        
        # (Call UI removed)
        
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
            
            # Vider la liste
            for screen_id in list(self.screen_list.thumbnails.keys()):
                self.screen_list.remove_screen(screen_id)
                
            # Mettre l'état en déconnecté
            app_state.logout()

            # Emettre un signal pour demander au contrôleur d'afficher l'écran de login
            try:
                self.logged_out.emit()
            except Exception:
                pass

            # Cacher la fenêtre principale (ne pas quitter l'application)
            try:
                self.hide()
            except Exception:
                pass
            
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

            # Notifier quand le partage distant s'arrête
            try:
                client.stream_state_changed.connect(
                    lambda state, sid=screen_id: self._on_remote_stream_state(sid, state)
                )
            except Exception:
                pass
            
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

    def _on_remote_stream_state(self, screen_id: str, state: str):
        state = (state or "").strip().lower()
        if state == "stopped":
            try:
                self.toast.show_toast("Partage arrêté", kind="info")
            except Exception:
                pass

            # Si l'utilisateur regardait ce stream en zoom, revenir à la liste
            if self.current_zoomed_screen == screen_id:
                try:
                    self.close_zoom()
                except Exception:
                    pass
            
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

        # Show the stream at 100% (no fitting) by default when zooming: treat zoom as 1:1
        try:
            viewer.fit_to_window = False
            viewer.zoom_level = 1.0
            # If we already have a latest frame, display it immediately at 100%
            try:
                latest = client.get_latest_frame()
                if latest is not None:
                    viewer.update_frame(latest)
            except Exception:
                pass
        except Exception:
            pass
            
        # Ajouter le nouveau
        self.zoom_layout.addWidget(viewer)
        self.screen_viewers[screen_id] = viewer
        self.current_zoomed_screen = screen_id
        try:
            viewer.setFocus(Qt.OtherFocusReason)
        except Exception:
            try:
                viewer.setFocus()
            except Exception:
                pass
        
        # Afficher la vue zoom
        self.content_stack.setCurrentIndex(1)

        _ui_debug(
            "MainWindow.zoom_screen "
            f"main={self.width()}x{self.height()} state={_qt_flag_to_int(self.windowState())} "
            f"central={self.centralWidget().width()}x{self.centralWidget().height()}"
        )

        # Forcer le plein écran en mode zoom
        if self._pre_zoom_window_state is None:
            self._pre_zoom_window_state = self.windowState()

        try:
            self.user_bar.hide()
        except Exception:
            pass
        try:
            self.main_toolbar.hide()
        except Exception:
            pass
        try:
            self.statusBar().hide()
        except Exception:
            pass

        self.showFullScreen()

        _ui_debug(
            "MainWindow.zoom_screen(after fullscreen) "
            f"main={self.width()}x{self.height()} state={_qt_flag_to_int(self.windowState())}"
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
            f"main={self.width()}x{self.height()} state={_qt_flag_to_int(self.windowState())}"
        )

        # Restaurer l'état précédent
        if self._pre_zoom_window_state is not None:
            prev = self._pre_zoom_window_state
            self._pre_zoom_window_state = None
            self.showNormal()
            if prev & Qt.WindowMaximized:
                self.showMaximized()

        # Restaurer les panneaux
        try:
            self.user_bar.show()
        except Exception:
            pass
        try:
            self.main_toolbar.show()
        except Exception:
            pass
        try:
            self.statusBar().show()
        except Exception:
            pass

        _ui_debug(
            "MainWindow.close_zoom(after restore) "
            f"main={self.width()}x{self.height()} state={_qt_flag_to_int(self.windowState())}"
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
            # Démarrer directement le serveur — les clients s'enregistrent automatiquement via TCP
            # Plus besoin de demander l'IP du client
            
            # Démarrer le serveur si pas encore lancé
            if not self.server.is_running:
                self.server.start()  # Démarrer sans IP spécifique
            
            # Démarrer le streaming vidéo
            self.server.start_streaming()
            self.share_screen_btn.setText("🛑 Arrêter le partage")
            self.share_screen_btn.setStyleSheet(button_solid(THEME.danger, THEME.danger_hover, padding="11px 18px"))
            
            # Afficher l'IP locale pour que les autres puissent se connecter
            local_ip = self._get_local_ip()
            self.toast.show_toast(f"Partage démarré • IP: {local_ip}", kind="success", duration=5000)
            self._refresh_app_status()
    
    def _get_local_ip(self):
        """Récupère l'adresse IP locale de la machine"""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
        
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
        # Call subsystem removed; nothing to cleanup here
        event.accept()
