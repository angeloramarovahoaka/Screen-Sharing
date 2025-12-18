"""
app/client/screen_client.py
"""
import socket
import json
import threading
import time
import base64
import numpy as np
import cv2
import os
import logging
from pynput import keyboard  # Nécessaire pour le hook bas niveau

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage
from ..config import VIDEO_PORT, COMMAND_PORT, BUFFER_SIZE, DEFAULT_WIDTH, DEFAULT_HEIGHT

logger = logging.getLogger("screenshare.client")

# --- CLASSE DE CAPTURE (MODE VM) ---
class KeyboardGrabber(QObject):
    command_signal = Signal(dict)
    capture_ended = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.listener = None
        self.is_captured = False
        self.escape_key = keyboard.Key.ctrl_r # Touche de sortie: CTRL Droit

    def start(self):
        if self.listener: return
        self.is_captured = True
        # suppress=True BLOQUE la touche Windows locale
        self.listener = keyboard.Listener(
            on_press=self._on_press, 
            on_release=self._on_release, 
            suppress=True
        )
        self.listener.start()

    def stop(self):
        if self.listener:
            try: self.listener.stop()
            except: pass
            self.listener = None
        self.is_captured = False
        self.capture_ended.emit()

    def _on_press(self, key):
        print(f"TOUCHE APPUYÉE: {key}")
        try:
            if key == self.escape_key:
                self.stop()
                return
            self.command_signal.emit({"type": "key", "action": "press", "key": self._get_key_name(key)})
        except: pass

    def _on_release(self, key):
        try:
            if key == self.escape_key: return
            self.command_signal.emit({"type": "key", "action": "release", "key": self._get_key_name(key)})
        except: pass

    def _get_key_name(self, key):
        if hasattr(key, 'char') and key.char:
            return key.char
        elif hasattr(key, 'name'):
            # Sur Linux, la touche Windows est souvent 'cmd' ou 'super'
            if key.name in ['cmd', 'cmd_l', 'cmd_r', 'super', 'super_l', 'super_r']: 
                return 'win' 
            return key.name
        return str(key).replace("Key.", "")

# --- CLIENT PRINCIPAL ---
class ScreenClient(QObject):
    frame_received = Signal(QImage)
    status_changed = Signal(str)
    connected = Signal()
    disconnected = Signal()
    # Nouveau signal pour l'interface
    capture_mode_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_connected = False
        self.is_running = False
        self.video_socket = None
        self.command_socket = None
        
        # Initialisation du Grabber
        self.grabber = KeyboardGrabber()
        self.grabber.command_signal.connect(self.send_command)
        self.grabber.capture_ended.connect(lambda: self.capture_mode_changed.emit(False))

    def connect_to_server(self, server_ip):
        # ... (Votre code de connexion existant - Copiez le ici) ...
        # Assurez-vous d'initialiser les sockets ici
        try:
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.video_socket.bind(('0.0.0.0', 0))
            self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.command_socket.connect((server_ip, COMMAND_PORT))
            
            # Register video port
            port = self.video_socket.getsockname()[1]
            reg = {'type': 'register', 'video_port': port}
            self.command_socket.sendall((json.dumps(reg) + '\n').encode('utf-8'))
            self.video_socket.sendto(b'START', (server_ip, VIDEO_PORT))

            self.is_connected = True
            self.is_running = True
            
            # Threads
            threading.Thread(target=self._receive_video, daemon=True).start()
            
            self.connected.emit()
            return True
        except Exception as e:
            self.status_changed.emit(f"Erreur: {e}")
            return False

    # --- METHODES POUR LE MODE VM ---
    def start_capture_mode(self):
        if self.is_connected and not self.grabber.is_captured:
            self.grabber.start()
            self.capture_mode_changed.emit(True)

    def stop_capture_mode(self):
        self.grabber.stop()

    def disconnect(self):
        self.stop_capture_mode()
        self.is_running = False
        self.is_connected = False
        if self.video_socket: self.video_socket.close()
        if self.command_socket: self.command_socket.close()
        self.disconnected.emit()

    def _receive_video(self):
        while self.is_running:
            try:
                packet, _ = self.video_socket.recvfrom(BUFFER_SIZE)
                npdata = np.frombuffer(packet, dtype=np.uint8)
                frame = cv2.imdecode(npdata, cv2.IMREAD_COLOR)
                if frame is not None:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
                    self.frame_received.emit(qimg.copy())
            except: pass

    def send_command(self, cmd):
        if self.is_connected and self.command_socket:
            try:
                self.command_socket.sendall((json.dumps(cmd) + '\n').encode('utf-8'))
            except: pass

    def send_mouse_move(self, x, y, w, h):
        if w > 0 and h > 0:
            self.send_command({'type': 'mouse', 'action': 'move', 'x': x/w, 'y': y/h})

    def send_mouse_click(self, x, y, w, h, btn, act):
        if w > 0 and h > 0:
            self.send_command({'type': 'mouse', 'action': act, 'button': btn, 'x': x/w, 'y': y/h})
            
    def set_display_size(self, w, h): pass