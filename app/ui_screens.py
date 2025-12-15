"""
Widgets pour l'affichage et la manipulation des écrans partagés
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy, QMenu, QToolButton, QSlider, QGridLayout, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Signal, Qt, QSize, QPoint, QTimer
from PySide6.QtGui import (
    QImage, QPixmap, QPainter, QFont, QMouseEvent, 
    QKeyEvent, QWheelEvent, QCursor, QColor, QLinearGradient
)

from .client_module import ScreenClient


def _ui_debug(msg: str):
    if os.getenv("SS_UI_DEBUG", "0") == "1":
        print(f"[UI_DEBUG] {msg}", flush=True)


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
        info_layout.addWidget(self.name_label)
        
        info_layout.addStretch()
        
        # Bouton menu
        self.menu_button = QToolButton()
        self.menu_button.setText("⋮")
        self.menu_button.setPopupMode(QToolButton.InstantPopup)
        self.menu_button.setStyleSheet("""
            QToolButton {
                border: none;
                padding: 2px 5px;
            }
            QToolButton:hover {
                background-color: rgba(0,0,0,0.1);
                border-radius: 3px;
            }
        """)
        
        menu = QMenu(self.menu_button)
        menu.addAction("🔍 Zoom", lambda: self.double_clicked.emit(self.screen_id))
        menu.addAction("❌ Déconnecter", lambda: self.remove_requested.emit(self.screen_id))
        self.menu_button.setMenu(menu)
        info_layout.addWidget(self.menu_button)
        
        layout.addLayout(info_layout)
        
    def update_style(self):
        """Met à jour le style selon l'état de sélection"""
        if self.is_selected:
            self.setStyleSheet("""
                QFrame {
                    background-color: #e3f2fd;
                    border: 2px solid #2196F3;
                    border-radius: 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: white;
                    border: 1px solid #ddd;
                    border-radius: 8px;
                }
                QFrame:hover {
                    border-color: #2196F3;
                }
            """)

        # Hover affordance via shadow (don't detach the effect: Qt may delete it)
        self._shadow.setEnabled(self._hovered and not self.is_selected)
            
    def update_frame(self, image: QImage):
        """Met à jour l'image affichée"""
        self.current_image = image
        if image and not image.isNull():
            pixmap = QPixmap.fromImage(image)
            scaled = pixmap.scaled(
                self.screen_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.screen_label.setPixmap(scaled)
            self.screen_label.setText("")
            
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


class ScreenViewer(QWidget):
    """
    Widget principal pour afficher et manipuler un écran en mode zoom
    """
    close_requested = Signal()
    
    def __init__(self, screen_id, client: ScreenClient, parent=None):
        super().__init__(parent)
        self.screen_id = screen_id
        self.client = client
        self.current_image = None
        self.zoom_level = 1.0
        self.fit_to_window = True
        self.is_controlling = True
        
        # Tracker l'état des touches modificatrices pour éviter de les envoyer plusieurs fois
        self.pressed_modifiers = set()
        
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setup_ui()
        
    def setup_ui(self):
        """Configure l'interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Barre d'outils
        toolbar = QFrame()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #333;
                border-bottom: 1px solid #444;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)
        
        # Titre
        title = QLabel(f"🖥️ {self.screen_id}")
        title.setStyleSheet("color: white; font-weight: bold;")
        toolbar_layout.addWidget(title)
        
        toolbar_layout.addStretch()
        
        # Contrôles de zoom
        zoom_out_btn = QToolButton()
        zoom_out_btn.setText("➖")
        zoom_out_btn.setStyleSheet("color: white; border: none; padding: 5px;")
        zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar_layout.addWidget(zoom_out_btn)
        
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("color: white; min-width: 50px;")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        toolbar_layout.addWidget(self.zoom_label)
        
        zoom_in_btn = QToolButton()
        zoom_in_btn.setText("➕")
        zoom_in_btn.setStyleSheet("color: white; border: none; padding: 5px;")
        zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar_layout.addWidget(zoom_in_btn)
        
        # Bouton plein écran
        fullscreen_btn = QToolButton()
        fullscreen_btn.setText("⛶")
        fullscreen_btn.setStyleSheet("color: white; border: none; padding: 5px;")
        fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        toolbar_layout.addWidget(fullscreen_btn)
        
        # Toggle contrôle
        self.control_btn = QToolButton()
        self.control_btn.setText("🖱️ Contrôle: ON")
        self.control_btn.setStyleSheet("""
            QToolButton {
                color: #4CAF50;
                border: 1px solid #4CAF50;
                border-radius: 3px;
                padding: 5px 10px;
            }
        """)
        self.control_btn.clicked.connect(self.toggle_control)
        toolbar_layout.addWidget(self.control_btn)
        
        # Bouton fermer
        close_btn = QToolButton()
        close_btn.setText("✕")
        close_btn.setStyleSheet("""
            QToolButton {
                color: white;
                border: none;
                padding: 5px;
            }
            QToolButton:hover {
                background-color: #f44336;
                border-radius: 3px;
            }
        """)
        close_btn.clicked.connect(self.close_requested.emit)
        toolbar_layout.addWidget(close_btn)
        
        layout.addWidget(toolbar)
        
        # Zone d'affichage de l'écran
        self.screen_area = QScrollArea()
        # Keep label size driving scrollbars; we'll scale pixmap ourselves.
        self.screen_area.setWidgetResizable(False)
        self.screen_area.setAlignment(Qt.AlignCenter)
        self.screen_area.setStyleSheet("""
            QScrollArea {
                background-color: #1a1a1a;
                border: none;
            }
        """)
        
        self.screen_label = QLabel()
        self.screen_label.setAlignment(Qt.AlignCenter)
        self.screen_label.setMouseTracking(True)
        self.screen_label.setStyleSheet("background-color: #1a1a1a;")
        self.screen_area.setWidget(self.screen_label)
        
        layout.addWidget(self.screen_area)

    def _viewport_size(self) -> QSize:
        try:
            return self.screen_area.viewport().size()
        except Exception:
            return QSize(0, 0)

    def _fit_zoom_for_image(self, image: QImage) -> float:
        vp = self._viewport_size()
        if vp.width() <= 0 or vp.height() <= 0:
            return 1.0
        if image.width() <= 0 or image.height() <= 0:
            return 1.0
        scale = min(vp.width() / image.width(), vp.height() / image.height())
        # Clamp to reasonable bounds.
        return max(0.1, min(3.0, float(scale)))
        
    def update_frame(self, image: QImage):
        """Met à jour l'image affichée"""
        self.current_image = image
        if image and not image.isNull():
            if self.fit_to_window:
                self.zoom_level = self._fit_zoom_for_image(image)

            # Appliquer le zoom
            new_w = max(1, int(image.width() * self.zoom_level))
            new_h = max(1, int(image.height() * self.zoom_level))
            scaled_image = image.scaled(
                QSize(new_w, new_h),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            pm = QPixmap.fromImage(scaled_image)
            self.screen_label.setPixmap(pm)
            self.screen_label.resize(pm.size())
            self.screen_label.setMinimumSize(pm.size())

            self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")

            _ui_debug(
                "ScreenViewer.update_frame "
                f"img={image.width()}x{image.height()} "
                f"viewport={self._viewport_size().width()}x{self._viewport_size().height()} "
                f"zoom={self.zoom_level:.3f} "
                f"pixmap={pm.width()}x{pm.height()} "
                f"label={self.screen_label.width()}x{self.screen_label.height()}"
            )
            
    def zoom_in(self):
        """Augmente le zoom"""
        self.fit_to_window = False
        self.zoom_level = min(3.0, self.zoom_level + 0.25)
        self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")
        if self.current_image:
            self.update_frame(self.current_image)
            
    def zoom_out(self):
        """Diminue le zoom"""
        self.fit_to_window = False
        self.zoom_level = max(0.25, self.zoom_level - 0.25)
        self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")
        if self.current_image:
            self.update_frame(self.current_image)

    def resizeEvent(self, event):
        # When fullscreen/resize happens, keep image fitted.
        _ui_debug(
            "ScreenViewer.resizeEvent "
            f"viewer={self.width()}x{self.height()} "
            f"viewport={self._viewport_size().width()}x{self._viewport_size().height()} "
            f"fit={self.fit_to_window}"
        )
        if self.fit_to_window and self.current_image and not self.current_image.isNull():
            self.update_frame(self.current_image)
        return super().resizeEvent(event)
            
    def toggle_fullscreen(self):
        """Bascule le mode plein écran"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
            
    def toggle_control(self):
        """Active/désactive le contrôle distant"""
        self.is_controlling = not self.is_controlling
        if self.is_controlling:
            self.control_btn.setText("🖱️ Contrôle: ON")
            self.control_btn.setStyleSheet("""
                QToolButton {
                    color: #4CAF50;
                    border: 1px solid #4CAF50;
                    border-radius: 3px;
                    padding: 5px 10px;
                }
            """)
        else:
            self.control_btn.setText("🖱️ Contrôle: OFF")
            self.control_btn.setStyleSheet("""
                QToolButton {
                    color: #f44336;
                    border: 1px solid #f44336;
                    border-radius: 3px;
                    padding: 5px 10px;
                }
            """)
            # Relâcher tous les modificateurs quand on désactive le contrôle
            self._release_all_modifiers()
    
    def _release_all_modifiers(self):
        """Relâche toutes les touches modificatrices pressées"""
        if not self.client:
            return
            
        for modifier in list(self.pressed_modifiers):
            self.client.send_command({'type': 'key', 'action': 'release', 'key': modifier})
        self.pressed_modifiers.clear()
    
    def focusOutEvent(self, event):
        """Appelé quand la fenêtre perd le focus - relâcher les modificateurs"""
        self._release_all_modifiers()
        super().focusOutEvent(event)
            
    def _get_normalized_position(self, pos):
        """Convertit la position en coordonnées normalisées"""
        label_pos = self.screen_label.mapFrom(self, pos)
        pixmap = self.screen_label.pixmap()
        if not pixmap:
            return None, None
            
        # Calculer l'offset si l'image est centrée
        offset_x = (self.screen_label.width() - pixmap.width()) // 2
        offset_y = (self.screen_label.height() - pixmap.height()) // 2
        
        x = label_pos.x() - offset_x
        y = label_pos.y() - offset_y
        
        if 0 <= x <= pixmap.width() and 0 <= y <= pixmap.height():
            return x / pixmap.width(), y / pixmap.height()
        return None, None
        
    def mouseMoveEvent(self, event: QMouseEvent):
        """Gère le mouvement de la souris"""
        if self.is_controlling and self.client:
            norm_x, norm_y = self._get_normalized_position(event.pos())
            if norm_x is not None:
                self.client.send_command({
                    'type': 'mouse',
                    'action': 'move',
                    'x': norm_x,
                    'y': norm_y
                })
        super().mouseMoveEvent(event)
        
    def mousePressEvent(self, event: QMouseEvent):
        """Gère le clic souris"""
        if self.is_controlling and self.client:
            norm_x, norm_y = self._get_normalized_position(event.pos())
            if norm_x is not None:
                button_map = {
                    Qt.LeftButton: 'left',
                    Qt.RightButton: 'right',
                    Qt.MiddleButton: 'middle'
                }
                button = button_map.get(event.button())
                if button:
                    self.client.send_command({
                        'type': 'mouse',
                        'action': 'press',
                        'button': button,
                        'x': norm_x,
                        'y': norm_y
                    })
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Gère le relâchement du clic"""
        if self.is_controlling and self.client:
            norm_x, norm_y = self._get_normalized_position(event.pos())
            if norm_x is not None:
                button_map = {
                    Qt.LeftButton: 'left',
                    Qt.RightButton: 'right',
                    Qt.MiddleButton: 'middle'
                }
                button = button_map.get(event.button())
                if button:
                    self.client.send_command({
                        'type': 'mouse',
                        'action': 'release',
                        'button': button,
                        'x': norm_x,
                        'y': norm_y
                    })
        super().mouseReleaseEvent(event)
        
    def wheelEvent(self, event: QWheelEvent):
        """Gère la molette de la souris"""
        if self.is_controlling and self.client:
            delta = event.angleDelta()
            dx = delta.x() // 120
            dy = delta.y() // 120
            self.client.send_command({
                'type': 'mouse',
                'action': 'scroll',
                'dx': dx,
                'dy': dy
            })
        super().wheelEvent(event)
        
    def keyPressEvent(self, event: QKeyEvent):
        """Gère les appuis de touches"""
        if self.is_controlling and self.client:
            modifiers = event.modifiers()
            key = event.key()
            
            # Vérifier si c'est une touche modificatrice elle-même
            is_modifier_key = key in [Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, 
                                      Qt.Key_Super_L, Qt.Key_Super_R]
            
            if not is_modifier_key:
                # C'est une touche normale, envoyer les modificateurs actifs d'abord (une seule fois)
                if (modifiers & Qt.ControlModifier) and 'ctrl' not in self.pressed_modifiers:
                    self.client.send_command({'type': 'key', 'action': 'press', 'key': 'ctrl'})
                    self.pressed_modifiers.add('ctrl')
                    
                if (modifiers & Qt.ShiftModifier) and 'shift' not in self.pressed_modifiers:
                    self.client.send_command({'type': 'key', 'action': 'press', 'key': 'shift'})
                    self.pressed_modifiers.add('shift')
                    
                if (modifiers & Qt.AltModifier) and 'alt' not in self.pressed_modifiers:
                    self.client.send_command({'type': 'key', 'action': 'press', 'key': 'alt'})
                    self.pressed_modifiers.add('alt')
                    
                if (modifiers & Qt.MetaModifier) and 'cmd' not in self.pressed_modifiers:
                    self.client.send_command({'type': 'key', 'action': 'press', 'key': 'cmd'})
                    self.pressed_modifiers.add('cmd')
            
            # Envoyer la touche principale
            key_name = self._get_key_name(event)
            if key_name:
                # Debug temporaire pour les touches directionnelles
                if key_name in ['arrow_left', 'arrow_up', 'arrow_right', 'arrow_down', 'left', 'up', 'right', 'down']:
                    print(f"DEBUG: Sending arrow key: {key_name}")
                self.client.send_command({
                    'type': 'key',
                    'action': 'press',
                    'key': key_name
                })
                
        super().keyPressEvent(event)
        
    def keyReleaseEvent(self, event: QKeyEvent):
        """Gère les relâchements de touches"""
        if self.is_controlling and self.client:
            key = event.key()
            
            # Envoyer le relâchement de la touche principale
            key_name = self._get_key_name(event)
            if key_name:
                self.client.send_command({
                    'type': 'key',
                    'action': 'release',
                    'key': key_name
                })
            
            # Si c'est une touche modificatrice qui est relâchée, la retirer du tracker
            if key == Qt.Key_Control and 'ctrl' in self.pressed_modifiers:
                self.client.send_command({'type': 'key', 'action': 'release', 'key': 'ctrl'})
                self.pressed_modifiers.discard('ctrl')
                
            elif key == Qt.Key_Shift and 'shift' in self.pressed_modifiers:
                self.client.send_command({'type': 'key', 'action': 'release', 'key': 'shift'})
                self.pressed_modifiers.discard('shift')
                
            elif key == Qt.Key_Alt and 'alt' in self.pressed_modifiers:
                self.client.send_command({'type': 'key', 'action': 'release', 'key': 'alt'})
                self.pressed_modifiers.discard('alt')
                
            elif key in [Qt.Key_Meta, Qt.Key_Super_L, Qt.Key_Super_R] and 'cmd' in self.pressed_modifiers:
                self.client.send_command({'type': 'key', 'action': 'release', 'key': 'cmd'})
                self.pressed_modifiers.discard('cmd')
                
        super().keyReleaseEvent(event)
        
    def _get_key_name(self, event: QKeyEvent):
        """Convertit un événement clavier en nom de touche"""
        key = event.key()
        text = event.text()
        
        # Mapping des touches spéciales
        special_keys = {
            Qt.Key_Return: 'enter',
            Qt.Key_Enter: 'enter',
            Qt.Key_Backspace: 'backspace',
            Qt.Key_Tab: 'tab',
            Qt.Key_Escape: 'esc',
            Qt.Key_Space: 'space',
            Qt.Key_Delete: 'delete',
            Qt.Key_Home: 'home',
            Qt.Key_End: 'end',
            Qt.Key_Left: 'arrow_left',
            Qt.Key_Right: 'arrow_right',
            Qt.Key_Up: 'arrow_up',
            Qt.Key_Down: 'arrow_down',
            Qt.Key_PageUp: 'page_up',
            Qt.Key_PageDown: 'page_down',
            Qt.Key_Shift: 'shift',
            Qt.Key_Control: 'ctrl',
            Qt.Key_Alt: 'alt',
            Qt.Key_Meta: 'cmd',  # Touche Windows/Command
            Qt.Key_Super_L: 'cmd',  # Windows gauche
            Qt.Key_Super_R: 'cmd_r',  # Windows droit
            Qt.Key_CapsLock: 'caps_lock',
            Qt.Key_Insert: 'insert',
            Qt.Key_Pause: 'pause',
            Qt.Key_Print: 'print_screen',
            Qt.Key_F1: 'f1',
            Qt.Key_F2: 'f2',
            Qt.Key_F3: 'f3',
            Qt.Key_F4: 'f4',
            Qt.Key_F5: 'f5',
            Qt.Key_F6: 'f6',
            Qt.Key_F7: 'f7',
            Qt.Key_F8: 'f8',
            Qt.Key_F9: 'f9',
            Qt.Key_F10: 'f10',
            Qt.Key_F11: 'f11',
            Qt.Key_F12: 'f12',
        }
        
        if key in special_keys:
            return special_keys[key]
        elif text and text.isprintable():
            return text
        return None


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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Titre
        title = QLabel("📺 Écrans connectés")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        # Texte foncé pour contraste sur fond clair (comme le nom d'utilisateur)
        title.setStyleSheet("color: #111111;")
        layout.addWidget(title)
        
        # Zone de scroll pour les miniatures
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        scroll.setWidget(self.grid_widget)
        layout.addWidget(scroll)
        
        # Message si aucun écran
        self.empty_label = QLabel("Aucun écran connecté.\nCliquez sur 'Ajouter' pour vous connecter à un serveur.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #999; padding: 50px;")
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
        # Désélectionner l'ancien
        if self.selected_screen and self.selected_screen in self.thumbnails:
            self.thumbnails[self.selected_screen].set_selected(False)
            
        # Sélectionner le nouveau
        self.selected_screen = screen_id
        self.thumbnails[screen_id].set_selected(True)
        self.screen_selected.emit(screen_id)
