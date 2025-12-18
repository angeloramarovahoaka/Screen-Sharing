from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QToolButton
)
from PySide6.QtCore import Signal, Qt, QSize, QEvent
from PySide6.QtGui import (
    QImage, QPixmap, QMouseEvent, QKeyEvent, QWheelEvent
)

from .utils import ui_debug
# Remonte de screens/ -> ui/ -> app/ -> pour trouver client_module
from app.client.screen_client import ScreenClient

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
        
        # Tracker l'état des touches modificatrices
        self.pressed_modifiers = set()
        
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setup_ui()

        try:
            self.setFocus(Qt.OtherFocusReason)
        except Exception:
            try:
                self.setFocus()
            except Exception:
                pass
        
    def setup_ui(self):
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

        # Forward key events
        self.screen_area.setFocusPolicy(Qt.NoFocus)
        self.screen_label.setFocusPolicy(Qt.NoFocus)
        self.screen_area.viewport().setFocusPolicy(Qt.NoFocus)
        self.screen_area.viewport().installEventFilter(self)
        self.screen_label.installEventFilter(self)

        self.setFocusPolicy(Qt.StrongFocus)
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
        return max(0.1, min(3.0, float(scale)))
        
    def update_frame(self, image: QImage):
        self.current_image = image
        if image and not image.isNull():
            if self.fit_to_window:
                new_zoom = self._fit_zoom_for_image(image)
                if abs(new_zoom - self.zoom_level) > 0.01:
                    self.zoom_level = new_zoom

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
            
            if not self.fit_to_window:
                self.screen_label.setMinimumSize(pm.size())
            else:
                self.screen_label.setMinimumSize(QSize(1, 1))

            self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")

            ui_debug(
                f"ScreenViewer.update_frame img={image.width()}x{image.height()} "
                f"zoom={self.zoom_level:.3f}"
            )
            
    def zoom_in(self):
        self.fit_to_window = False
        self.zoom_level = min(3.0, self.zoom_level + 0.25)
        self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")
        if self.current_image:
            self.update_frame(self.current_image)
            
    def zoom_out(self):
        self.fit_to_window = False
        self.zoom_level = max(0.25, self.zoom_level - 0.25)
        self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")
        if self.current_image:
            self.update_frame(self.current_image)

    def resizeEvent(self, event):
        if getattr(self, '_in_resize', False):
            return super().resizeEvent(event)
            
        self._in_resize = True
        try:
            if self.fit_to_window and self.current_image and not self.current_image.isNull():
                self.update_frame(self.current_image)
        finally:
            self._in_resize = False
        return super().resizeEvent(event)
            
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
            
    def toggle_control(self):
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
            self._release_all_modifiers()
    
    def _release_all_modifiers(self):
        if not self.client:
            return
        for modifier in list(self.pressed_modifiers):
            self.client.send_command({'type': 'key', 'action': 'release', 'key': modifier})
        self.pressed_modifiers.clear()
    
    def focusOutEvent(self, event):
        self._release_all_modifiers()
        super().focusOutEvent(event)
            
    def _get_normalized_position(self, pos):
        label_pos = self.screen_label.mapFrom(self, pos)
        pixmap = self.screen_label.pixmap()
        if not pixmap:
            return None, None
            
        offset_x = (self.screen_label.width() - pixmap.width()) // 2
        offset_y = (self.screen_label.height() - pixmap.height()) // 2
        
        x = label_pos.x() - offset_x
        y = label_pos.y() - offset_y
        
        if 0 <= x <= pixmap.width() and 0 <= y <= pixmap.height():
            return x / pixmap.width(), y / pixmap.height()
        return None, None
        
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.is_controlling and self.client:
            norm_x, norm_y = self._get_normalized_position(event.pos())
            if norm_x is not None:
                self.client.send_command({
                    'type': 'mouse', 'action': 'move', 'x': norm_x, 'y': norm_y
                })
        super().mouseMoveEvent(event)
        
    def mousePressEvent(self, event: QMouseEvent):
        if self.is_controlling and self.client:
            norm_x, norm_y = self._get_normalized_position(event.pos())
            if norm_x is not None:
                button_map = {Qt.LeftButton: 'left', Qt.RightButton: 'right', Qt.MiddleButton: 'middle'}
                button = button_map.get(event.button())
                if button:
                    self.client.send_command({
                        'type': 'mouse', 'action': 'press', 'button': button, 'x': norm_x, 'y': norm_y
                    })
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.is_controlling and self.client:
            norm_x, norm_y = self._get_normalized_position(event.pos())
            if norm_x is not None:
                button_map = {Qt.LeftButton: 'left', Qt.RightButton: 'right', Qt.MiddleButton: 'middle'}
                button = button_map.get(event.button())
                if button:
                    self.client.send_command({
                        'type': 'mouse', 'action': 'release', 'button': button, 'x': norm_x, 'y': norm_y
                    })
        super().mouseReleaseEvent(event)
        
    def wheelEvent(self, event: QWheelEvent):
        if self.is_controlling and self.client:
            delta = event.angleDelta()
            dx = delta.x() // 120
            dy = delta.y() // 120
            self.client.send_command({
                'type': 'mouse', 'action': 'scroll', 'dx': dx, 'dy': dy
            })
        super().wheelEvent(event)

    def event(self, event):
        if event.type() == QEvent.Type.KeyPress:
            if self.is_controlling and self.client:
                key = event.key()
                modifiers = event.modifiers()
                has_modifiers = modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)
                special_keys = (Qt.Key_Tab, Qt.Key_Backtab, Qt.Key_F1, Qt.Key_F2, Qt.Key_F3, Qt.Key_F4, 
                               Qt.Key_F5, Qt.Key_F6, Qt.Key_F7, Qt.Key_F8, Qt.Key_F9, Qt.Key_F10, 
                               Qt.Key_F11, Qt.Key_F12, Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter, 
                               Qt.Key_Backspace, Qt.Key_Delete, Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, 
                               Qt.Key_PageDown, Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down)
                
                if has_modifiers or key in special_keys:
                    self.keyPressEvent(event)
                    return True
                    
        elif event.type() == QEvent.Type.KeyRelease:
            if self.is_controlling and self.client:
                key = event.key()
                modifiers = event.modifiers()
                has_modifiers = modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)
                special_keys = (Qt.Key_Tab, Qt.Key_Backtab, Qt.Key_F1, Qt.Key_F2, Qt.Key_F3, Qt.Key_F4, 
                               Qt.Key_F5, Qt.Key_F6, Qt.Key_F7, Qt.Key_F8, Qt.Key_F9, Qt.Key_F10, 
                               Qt.Key_F11, Qt.Key_F12, Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter, 
                               Qt.Key_Backspace, Qt.Key_Delete, Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, 
                               Qt.Key_PageDown, Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down)
                
                if has_modifiers or key in special_keys:
                    self.keyReleaseEvent(event)
                    return True
                    
        return super().event(event)
        
    def keyPressEvent(self, event: QKeyEvent):
        key_name_debug = self._get_key_name(event)
        print(f"[KEY-CLIENT] keyPressEvent: key={event.key()} name={key_name_debug} autoRepeat={event.isAutoRepeat()} controlling={self.is_controlling}", flush=True)
        
        if event.isAutoRepeat():
            event.accept()
            return
        if self.is_controlling and self.client:
            modifiers = event.modifiers()
            key = event.key()
            
            is_modifier_key = key in [Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, 
                                      Qt.Key_Super_L, Qt.Key_Super_R]
            if not is_modifier_key:
                active_mods = []
                if (modifiers & Qt.ControlModifier): active_mods.append('ctrl')
                if (modifiers & Qt.ShiftModifier): active_mods.append('shift')
                if (modifiers & Qt.AltModifier): active_mods.append('alt')
                if (modifiers & Qt.MetaModifier): active_mods.append('cmd')

                key_name = self._get_key_name(event)
                if key_name:
                    print(f"[KEY-CLIENT] Sending: mods={active_mods} key={key_name}", flush=True)
                    if active_mods:
                        self.client.send_command({'type': 'key', 'action': 'combo', 'keys': active_mods + [key_name]})
                    else:
                        self.client.send_command({'type': 'key', 'action': 'press', 'key': key_name})
                    event.accept()
                    return
        super().keyPressEvent(event)
        
    def keyReleaseEvent(self, event: QKeyEvent):
        if event.isAutoRepeat():
            event.accept()
            return
        if self.is_controlling and self.client:
            key = event.key()
            key_name = self._get_key_name(event)
            if key_name:
                self.client.send_command({'type': 'key', 'action': 'release', 'key': key_name})
            
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
            event.accept()
            return
        super().keyReleaseEvent(event)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            if obj in (self.screen_area.viewport(), self.screen_label):
                if event.type() == QEvent.Type.KeyPress:
                    self.keyPressEvent(event)
                else:
                    self.keyReleaseEvent(event)
                return True
        return super().eventFilter(obj, event)
        
    def _get_key_name(self, event: QKeyEvent):
        key = event.key()
        text = event.text()
        special_keys = {
            Qt.Key_Return: 'enter', Qt.Key_Enter: 'enter', Qt.Key_Backspace: 'backspace',
            Qt.Key_Tab: 'tab', Qt.Key_Escape: 'esc', Qt.Key_Space: 'space',
            Qt.Key_Delete: 'delete', Qt.Key_Home: 'home', Qt.Key_End: 'end',
            Qt.Key_Left: 'arrow_left', Qt.Key_Right: 'arrow_right', Qt.Key_Up: 'arrow_up', Qt.Key_Down: 'arrow_down',
            Qt.Key_PageUp: 'page_up', Qt.Key_PageDown: 'page_down',
            Qt.Key_Shift: 'shift', Qt.Key_Control: 'ctrl', Qt.Key_Alt: 'alt',
            Qt.Key_Meta: 'cmd', Qt.Key_Super_L: 'cmd', Qt.Key_Super_R: 'cmd_r',
            Qt.Key_CapsLock: 'caps_lock', Qt.Key_Insert: 'insert', Qt.Key_Pause: 'pause', Qt.Key_Print: 'print_screen',
            Qt.Key_F1: 'f1', Qt.Key_F2: 'f2', Qt.Key_F3: 'f3', Qt.Key_F4: 'f4', Qt.Key_F5: 'f5', Qt.Key_F6: 'f6',
            Qt.Key_F7: 'f7', Qt.Key_F8: 'f8', Qt.Key_F9: 'f9', Qt.Key_F10: 'f10', Qt.Key_F11: 'f11', Qt.Key_F12: 'f12',
        }
        if key in special_keys: return special_keys[key]
        if text and text.isprintable(): return text.lower()
        if Qt.Key_A <= key <= Qt.Key_Z: return chr(key).lower()
        elif Qt.Key_0 <= key <= Qt.Key_9: return chr(key)
        
        numpad_keys = {
            Qt.Key_Minus: '-', Qt.Key_Plus: '+', Qt.Key_Equal: '=',
            Qt.Key_BracketLeft: '[', Qt.Key_BracketRight: ']', Qt.Key_Backslash: '\\',
            Qt.Key_Semicolon: ';', Qt.Key_Apostrophe: "'", Qt.Key_Comma: ',',
            Qt.Key_Period: '.', Qt.Key_Slash: '/', Qt.Key_QuoteLeft: '`',
        }
        if key in numpad_keys: return numpad_keys[key]
        return None