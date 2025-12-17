"""
Fenêtre principale de l'application
"""
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame, QSplitter, QMessageBox, QDialog,
    QLineEdit, QFormLayout, QToolBar, QStatusBar, QApplication,
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QAction, QIcon

from .config import app_state, COMMAND_PORT, VIDEO_PORT
from .client_module import ScreenClient, MultiScreenClient, DiscoveryScanner
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
        title = QLabel("🖥️ Écrans partagés disponibles")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: #1976D2; background: transparent;")
        layout.addWidget(title)
        
        # Indication
        self.status_label = QLabel("🔍 Recherche en cours...")
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
        
        manual_title = QLabel("📝 Ou entrer l'IP manuellement:")
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
        
        self.refresh_btn = QPushButton("🔄 Actualiser")
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
        self.status_label.setText("🔍 Recherche en cours...")
        self.status_label.setStyleSheet("color: #666666; font-style: italic; background: transparent;")
        self.refresh_btn.setEnabled(False)
        self.scanner.start_scan(duration=3.0)
        
    def _on_server_found(self, server_info):
        """Appelé quand un serveur est trouvé"""
        item = QListWidgetItem()
        item.setText(f"🖥️ {server_info['name']}\n     📍 {server_info['ip']}")
        item.setData(Qt.UserRole, server_info)
        self.server_list.addItem(item)
        
        # Mettre à jour le statut
        count = self.server_list.count()
        self.status_label.setText(f"✅ {count} écran(s) trouvé(s)")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; background: transparent;")
        
    def _on_scan_finished(self):
        """Appelé quand le scan est terminé"""
        self.refresh_btn.setEnabled(True)
        if self.server_list.count() == 0:
            self.status_label.setText("❌ Aucun écran partagé trouvé sur le réseau")
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
