"""
Module Client - Réception du flux vidéo et envoi des commandes
Basé sur client.py original
"""
import cv2
import socket
import numpy as np
import base64
import time
import json
import threading
from PySide6.QtCore import QObject, Signal, QThread, QTimer
from PySide6.QtGui import QImage, QPixmap
from pynput import keyboard, mouse

from .config import VIDEO_PORT, COMMAND_PORT, BUFFER_SIZE, DEFAULT_WIDTH, DEFAULT_HEIGHT


class ScreenClient(QObject):
    """
    Client de réception d'écran partagé
    Reçoit le flux vidéo et envoie les commandes de contrôle
    """
    frame_received = Signal(QImage)
    status_changed = Signal(str)
    connected = Signal()
    disconnected = Signal()
    error_occurred = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Configuration
        self.server_ip = None
        self.display_width = DEFAULT_WIDTH
        self.display_height = DEFAULT_HEIGHT
        
        # État
        self.is_running = False
        self.is_connected = False
        self.latest_frame = None
        
        # Sockets
        self.video_socket = None
        self.command_socket = None
        
        # Thread de réception
        self.receive_thread = None
        
        # Listeners clavier/souris (optionnels, pour capture globale)
        self.keyboard_listener = None
        self.mouse_listener = None
        
    def connect_to_server(self, server_ip):
        """Se connecte à un serveur de partage d'écran"""
        self.server_ip = server_ip
        
        try:
            # Socket vidéo UDP
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
            self.video_socket.settimeout(0.1)
            
            try:
                self.video_socket.bind(('0.0.0.0', VIDEO_PORT))
            except:
                pass
                
            # Socket commandes TCP
            self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.command_socket.settimeout(5.0)
            self.command_socket.connect((server_ip, COMMAND_PORT))
            
            self.is_connected = True
            self.is_running = True
            
            # Démarrer le thread de réception
            self.receive_thread = threading.Thread(target=self._receive_video, daemon=True)
            self.receive_thread.start()
            
            # Envoyer le message de démarrage
            self.video_socket.sendto(b'START', (server_ip, VIDEO_PORT))
            
            self.status_changed.emit(f"Connecté à {server_ip}")
            self.connected.emit()
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"Erreur de connexion: {e}")
            self.disconnect()
            return False
            
    def disconnect(self):
        """Se déconnecte du serveur"""
        self.is_running = False
        self.is_connected = False
        
        # Arrêter les listeners
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except:
                pass
            self.keyboard_listener = None
            
        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except:
                pass
            self.mouse_listener = None
        
        # Fermer les sockets
        if self.video_socket:
            try:
                self.video_socket.close()
            except:
                pass
            self.video_socket = None
            
        if self.command_socket:
            try:
                self.command_socket.close()
            except:
                pass
            self.command_socket = None
            
        self.latest_frame = None
        self.status_changed.emit("Déconnecté")
        self.disconnected.emit()
        
    def _receive_video(self):
        """Thread de réception du flux vidéo"""
        while self.is_running:
            try:
                packet, addr = self.video_socket.recvfrom(BUFFER_SIZE)
                data = base64.b64decode(packet)
                npdata = np.frombuffer(data, dtype=np.uint8)
                frame = cv2.imdecode(npdata, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    self.latest_frame = frame
                    
                    # Convertir en QImage et émettre le signal
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = frame_rgb.shape
                    bytes_per_line = ch * w
                    qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                    self.frame_received.emit(qimg.copy())
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    time.sleep(0.001)
                    
    def send_command(self, command_dict):
        """Envoie une commande au serveur"""
        if not self.command_socket or not self.is_connected:
            return False
            
        try:
            message = json.dumps(command_dict) + '\n'
            self.command_socket.sendall(message.encode('utf-8'))
            return True
        except Exception as e:
            return False
            
    def send_mouse_move(self, x, y, widget_width, widget_height):
        """Envoie une commande de mouvement souris normalisée"""
        if widget_width == 0 or widget_height == 0:
            return
            
        normalized_x = x / widget_width
        normalized_y = y / widget_height
        
        command = {
            'type': 'mouse',
            'action': 'move',
            'x': normalized_x,
            'y': normalized_y
        }
        self.send_command(command)
        
    def send_mouse_click(self, x, y, widget_width, widget_height, button, action):
        """Envoie une commande de clic souris"""
        if widget_width == 0 or widget_height == 0:
            return
            
        normalized_x = x / widget_width
        normalized_y = y / widget_height
        
        command = {
            'type': 'mouse',
            'action': action,
            'button': button,
            'x': normalized_x,
            'y': normalized_y
        }
        self.send_command(command)
        
    def send_mouse_scroll(self, dx, dy):
        """Envoie une commande de défilement"""
        command = {
            'type': 'mouse',
            'action': 'scroll',
            'dx': dx,
            'dy': dy
        }
        self.send_command(command)
        
    def send_key_event(self, key_name, action):
        """Envoie une commande clavier"""
        command = {
            'type': 'key',
            'action': action,
            'key': key_name
        }
        self.send_command(command)
        
    def get_latest_frame(self):
        """Retourne la dernière frame reçue"""
        return self.latest_frame
        
    def set_display_size(self, width, height):
        """Définit la taille d'affichage"""
        self.display_width = width
        self.display_height = height


class MultiScreenClient(QObject):
    """
    Client pour gérer plusieurs connexions d'écrans simultanées
    """
    screen_added = Signal(str, QImage)
    screen_removed = Signal(str)
    screen_updated = Signal(str, QImage)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.clients = {}
        
    def add_screen(self, screen_id, server_ip):
        """Ajoute une connexion à un écran"""
        if screen_id in self.clients:
            return False
            
        client = ScreenClient()
        client.frame_received.connect(
            lambda img, sid=screen_id: self._on_frame_received(sid, img)
        )
        
        if client.connect_to_server(server_ip):
            self.clients[screen_id] = client
            return True
        return False
        
    def remove_screen(self, screen_id):
        """Retire une connexion d'écran"""
        if screen_id in self.clients:
            self.clients[screen_id].disconnect()
            del self.clients[screen_id]
            self.screen_removed.emit(screen_id)
            
    def get_client(self, screen_id):
        """Retourne le client pour un écran donné"""
        return self.clients.get(screen_id)
        
    def _on_frame_received(self, screen_id, image):
        """Callback quand une frame est reçue"""
        self.screen_updated.emit(screen_id, image)
        
    def disconnect_all(self):
        """Déconnecte tous les écrans"""
        for client in self.clients.values():
            client.disconnect()
        self.clients.clear()
