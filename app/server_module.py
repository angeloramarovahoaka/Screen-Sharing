"""
Module Serveur - Partage d'écran et réception des commandes
Basé sur server.py original
"""
import cv2
import imutils
import socket
import numpy as np
import time
import base64
import threading
import json
from PySide6.QtCore import QObject, Signal, QThread
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key
import logging
import os
from logging.handlers import RotatingFileHandler, DatagramHandler

try:
    import pyscreenshot as ImageGrab
except ImportError:
    from PIL import ImageGrab

from .config import VIDEO_PORT, COMMAND_PORT, BUFFER_SIZE, JPEG_QUALITY, DEFAULT_WIDTH

# --- Logging configuration ---
LOG_LEVEL = os.getenv("SS_LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("screenshare.server")
if not logger.handlers:
    # Console handler
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Rotating handler (logs/server.log)
    try:
        logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        file_path = os.path.join(logs_dir, "server.log")
        fh = RotatingFileHandler(file_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception:
        pass

    # Optional remote log collector via UDP: set SS_LOG_COLLECTOR=host:port
    collector = os.getenv("SS_LOG_COLLECTOR")
    if collector:
        try:
            host, port = collector.split(":")
            dh = DatagramHandler(host, int(port))
            logger.addHandler(dh)
        except Exception:
            pass

logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))


class ScreenServer(QObject):
    """
    Serveur de partage d'écran
    Envoie le flux vidéo et reçoit les commandes de contrôle
    """
    status_changed = Signal(str)
    client_connected = Signal(str)
    client_disconnected = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Outils de simulation
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        
        # Résolution d'écran (à ajuster selon votre écran)
        self.screen_width = 1920
        self.screen_height = 1080
        
        # État
        self.is_running = False
        self.connected_clients = {}
        
        # Sockets
        self.video_socket = None
        self.command_socket = None
        
        # Threads
        self.video_thread = None
        self.command_thread = None
        
        # Mapping des boutons souris
        self.button_map = {
            "left": Button.left,
            "right": Button.right,
            "middle": Button.middle
        }
        
    def get_pynput_key(self, key_name):
        """Convertit une chaîne en objet pynput Key ou caractère."""
        try:
            return getattr(Key, key_name)
        except AttributeError:
            return key_name
            
    def start(self, client_ip):
        """Démarre le serveur de partage d'écran"""
        self.client_ip = client_ip
        self.is_running = True
        logger.info(f"Starting ScreenServer for client {client_ip}")
        
        # Démarrer le thread des commandes
        self.command_thread = threading.Thread(target=self._command_listener, daemon=True)
        self.command_thread.start()
        
        # Démarrer le thread vidéo
        self.video_thread = threading.Thread(target=self._video_streamer, daemon=True)
        self.video_thread.start()
        
        self.status_changed.emit("Serveur démarré")
        logger.info("Serveur démarré (signals emitted)")
        
    def stop(self):
        """Arrête le serveur"""
        self.is_running = False
        logger.info("Stopping ScreenServer")
        
        if self.video_socket:
            try:
                self.video_socket.close()
            except:
                pass
                
        if self.command_socket:
            try:
                self.command_socket.close()
            except:
                pass
                
        self.status_changed.emit("Serveur arrêté")
        logger.info("Serveur arrêté (signals emitted)")
        
    def _video_streamer(self):
        """Thread de streaming vidéo"""
        try:
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.status_changed.emit("Streaming vidéo démarré")
            logger.info("Video streamer thread started")
            
            while self.is_running:
                try:
                    # Capture d'écran
                    img_pil = ImageGrab.grab()
                    frame = np.array(img_pil, dtype=np.uint8)
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    frame = imutils.resize(frame, width=DEFAULT_WIDTH)
                    
                    # Encodage JPEG
                    encoded, buffer = cv2.imencode(
                        '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                    )
                    b64encoded = base64.b64encode(buffer)
                    
                    # Envoi à tous les clients connectés
                    for client_id, client_addr in list(self.connected_clients.items()):
                        try:
                            sent = self.video_socket.sendto(b64encoded, client_addr)
                            logger.debug(f"Sent video packet to {client_addr} ({len(b64encoded)} bytes) -> sendto returned {sent}")
                        except Exception as e:
                            logger.exception(f"Erreur en envoyant vers {client_addr}: {e}")
                            # Ne pas supprimer le client automatiquement; laisser la logique de socket gérer
                            
                except Exception as e:
                    logger.debug(f"Erreur dans video_streamer loop: {e}")
                    time.sleep(0.01)
                    
        except Exception as e:
            self.error_occurred.emit(f"Erreur vidéo: {e}")
            logger.exception(f"Video streamer fatal error: {e}")
        finally:
            if self.video_socket:
                self.video_socket.close()
                
    def _command_listener(self):
        """Thread d'écoute des commandes TCP"""
        try:
            self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.command_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.command_socket.bind(('0.0.0.0', COMMAND_PORT))
            self.command_socket.listen(5)
            self.status_changed.emit(f"Écoute commandes sur port {COMMAND_PORT}")
            logger.info(f"Listening for command connections on 0.0.0.0:{COMMAND_PORT}")
            
            while self.is_running:
                try:
                    self.command_socket.settimeout(1.0)
                    conn, addr = self.command_socket.accept()
                    client_id = f"{addr[0]}:{addr[1]}"
                    self.connected_clients[client_id] = (addr[0], VIDEO_PORT)
                    self.client_connected.emit(client_id)
                    logger.info(f"Accepted command connection from {addr}; registered client_id={client_id}")
                    
                    # Traiter les commandes de ce client
                    client_thread = threading.Thread(
                        target=self._handle_client_commands,
                        args=(conn, addr, client_id),
                        daemon=True
                    )
                    client_thread.start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.is_running:
                        logger.debug(f"Error in command_listener accept loop: {e}")
                        time.sleep(0.1)
                        
        except Exception as e:
            self.error_occurred.emit(f"Erreur commandes: {e}")
            logger.exception(f"Command listener fatal error: {e}")
        finally:
            if self.command_socket:
                self.command_socket.close()
                
    def _handle_client_commands(self, conn, addr, client_id):
        """Gère les commandes d'un client spécifique"""
        try:
            logger.debug(f"Start handling commands for {client_id}")
            while self.is_running:
                data = conn.recv(1024)
                if not data:
                    break
                    
                logger.debug(f"Received {len(data)} bytes from {addr}")
                try:
                    command_str = data.decode('utf-8')
                except Exception:
                    logger.exception("Failed to decode command bytes as utf-8")
                    continue
                
                for command_json in command_str.split('\n'):
                    if not command_json:
                        continue
                        
                    try:
                        logger.debug(f"Command JSON raw: {command_json}")
                        command = json.loads(command_json)
                        # Special handling for 'register' so client can tell us its UDP port
                        if isinstance(command, dict) and command.get('type') == 'register':
                            try:
                                video_port = int(command.get('video_port', VIDEO_PORT))
                                # Update mapping so we send video UDP to the provided port
                                self.connected_clients[client_id] = (addr[0], video_port)
                                logger.info(f"Registered client {client_id} -> {(addr[0], video_port)}")
                            except Exception as e:
                                logger.exception(f"Failed to process register from {client_id}: {e}")
                        else:
                            self._execute_command(command)
                    except json.JSONDecodeError:
                        logger.warning(f"JSON decode error for: {command_json}")
                        pass
                    except Exception as e:
                        logger.exception(f"Error executing command: {e}")
                        pass
                        
        except Exception as e:
            logger.exception(f"Exception in client command handler for {client_id}: {e}")
        finally:
            conn.close()
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]
            self.client_disconnected.emit(client_id)
            logger.info(f"Closed command connection for {client_id}")
            
    def _execute_command(self, command):
        """Exécute une commande reçue"""
        cmd_type = command.get('type')
        
        if cmd_type == 'mouse':
            action = command['action']
            
            if action != 'scroll':
                x = int(command['x'] * self.screen_width)
                y = int(command['y'] * self.screen_height)
                self.mouse.position = (x, y)
                
            if action == 'move':
                pass
            elif action == 'scroll':
                self.mouse.scroll(command.get('dx', 0), command.get('dy', 0))
            else:
                button_str = command.get('button')
                pynput_button = self.button_map.get(button_str)
                
                if pynput_button:
                    if action == 'press':
                        self.mouse.press(pynput_button)
                    elif action == 'release':
                        self.mouse.release(pynput_button)
                        
        elif cmd_type == 'key':
            action = command['action']
            key_name = command['key']
            pynput_key = self.get_pynput_key(key_name)
            
            if pynput_key:
                if action == 'press':
                    self.keyboard.press(pynput_key)
                elif action == 'release':
                    self.keyboard.release(pynput_key)
                    
    def add_client(self, client_ip):
        """Ajoute un client pour recevoir le flux vidéo"""
        client_id = f"{client_ip}:{VIDEO_PORT}"
        self.connected_clients[client_id] = (client_ip, VIDEO_PORT)
        self.client_connected.emit(client_id)
        
    def remove_client(self, client_id):
        """Retire un client"""
        if client_id in self.connected_clients:
            del self.connected_clients[client_id]
            self.client_disconnected.emit(client_id)
