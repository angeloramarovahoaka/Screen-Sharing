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
import platform
from PySide6.QtCore import QObject, Signal, QThread
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key
import logging
import os
from logging.handlers import RotatingFileHandler, DatagramHandler

# Import pour la gestion des touches spéciales sur Windows
if platform.system() == 'Windows':
    import ctypes
    from ctypes import wintypes

try:
    import pyscreenshot as ImageGrab
except ImportError:
    from PIL import ImageGrab

from .config import VIDEO_PORT, COMMAND_PORT, BUFFER_SIZE, JPEG_QUALITY, DEFAULT_WIDTH, USE_WEBCAM

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
        self.is_streaming = False  # Contrôle si le streaming vidéo est actif
        self.connected_clients = {}
        
        # Configuration
        self.use_webcam = USE_WEBCAM
        
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
        
        # Constants pour les touches directionnelles sur Windows
        if platform.system() == 'Windows':
            self.VK_LEFT = 0x25
            self.VK_UP = 0x26
            self.VK_RIGHT = 0x27
            self.VK_DOWN = 0x28
            self.KEYEVENTF_KEYUP = 0x0002
    
    def _press_arrow_key(self, direction):
        """Appuie sur une touche directionnelle en utilisant l'API Windows native"""
        if platform.system() == 'Windows':
            vk_codes = {
                'arrow_left': self.VK_LEFT,
                'arrow_up': self.VK_UP,
                'arrow_right': self.VK_RIGHT,
                'arrow_down': self.VK_DOWN
            }
            if direction in vk_codes:
                print(f"DEBUG: Pressing {direction} with ctypes, VK={vk_codes[direction]}")
                ctypes.windll.user32.keybd_event(vk_codes[direction], 0, 0, 0)
                return True
        return False
    
    def _release_arrow_key(self, direction):
        """Relâche une touche directionnelle en utilisant l'API Windows native"""
        if platform.system() == 'Windows':
            vk_codes = {
                'arrow_left': self.VK_LEFT,
                'arrow_up': self.VK_UP,
                'arrow_right': self.VK_RIGHT,
                'arrow_down': self.VK_DOWN
            }
            if direction in vk_codes:
                print(f"DEBUG: Releasing {direction} with ctypes, VK={vk_codes[direction]}")
                ctypes.windll.user32.keybd_event(vk_codes[direction], 0, self.KEYEVENTF_KEYUP, 0)
                return True
        return False
        
    def get_pynput_key(self, key_name):
        """Convertit une chaîne en objet pynput Key ou caractère."""
        # Mapping explicite pour les touches spéciales
        key_mapping = {
            'enter': Key.enter,
            'backspace': Key.backspace,
            'tab': Key.tab,
            'esc': Key.esc,
            'space': Key.space,
            'delete': Key.delete,
            'home': Key.home,
            'end': Key.end,
            'left': Key.left,
            'right': Key.right,
            'up': Key.up,
            'down': Key.down,
            'arrow_left': Key.left,
            'arrow_right': Key.right,
            'arrow_up': Key.up,
            'arrow_down': Key.down,
            'page_up': Key.page_up,
            'page_down': Key.page_down,
            'shift': Key.shift_l,
            'shift_l': Key.shift_l,
            'shift_r': Key.shift_r,
            'ctrl': Key.ctrl_l,
            'ctrl_l': Key.ctrl_l,
            'ctrl_r': Key.ctrl_r,
            'alt': Key.alt_l,
            'alt_l': Key.alt_l,
            'alt_r': Key.alt_r,
            'cmd': Key.cmd,
            'cmd_l': Key.cmd,
            'cmd_r': Key.cmd_r,
            'caps_lock': Key.caps_lock,
            'insert': Key.insert,
            'pause': Key.pause,
            'print_screen': Key.print_screen,
            'f1': Key.f1,
            'f2': Key.f2,
            'f3': Key.f3,
            'f4': Key.f4,
            'f5': Key.f5,
            'f6': Key.f6,
            'f7': Key.f7,
            'f8': Key.f8,
            'f9': Key.f9,
            'f10': Key.f10,
            'f11': Key.f11,
            'f12': Key.f12,
        }
        
        # Chercher dans le mapping
        if key_name in key_mapping:
            return key_mapping[key_name]
        
        # Sinon, retourner le caractère tel quel (pour les lettres, chiffres, etc.)
        return key_name
            
    def start(self):
        """Démarre le serveur (écoute commandes seulement, pas de streaming auto)"""
        self.is_running = True
        logger.info("Starting ScreenServer (command listener)")
        
        # Démarrer le thread des commandes
        self.command_thread = threading.Thread(target=self._command_listener, daemon=True)
        self.command_thread.start()
        
        # NE PAS démarrer le streaming automatiquement
        # Il sera démarré via start_streaming() sur demande
        
        self.status_changed.emit("Serveur démarré (prêt pour streaming)")
        logger.info("Serveur démarré - en attente de demande de streaming")
        
    def start_streaming(self):
        """Démarre le streaming vidéo (sur demande)"""
        if self.is_streaming:
            logger.warning("Streaming already active")
            return
        
        self.is_streaming = True
        self.video_thread = threading.Thread(target=self._video_streamer, daemon=True)
        self.video_thread.start()
        self.status_changed.emit("Streaming vidéo démarré")
        logger.info("Video streaming started on demand")
    
    def stop_streaming(self):
        """Arrête le streaming vidéo"""
        self.is_streaming = False
        if self.video_socket:
            try:
                self.video_socket.close()
                self.video_socket = None
            except:
                pass
        self.status_changed.emit("Streaming vidéo arrêté")
        logger.info("Video streaming stopped")
        
    def stop(self):
        """Arrête le serveur"""
        self.is_running = False
        self.is_streaming = False
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
            
            if self.use_webcam:
                # Utiliser la webcam
                vid = cv2.VideoCapture(0)
                if not vid.isOpened():
                    self.error_occurred.emit("Impossible d'ouvrir la webcam")
                    logger.error("Failed to open webcam")
                    return
                logger.info("Using webcam for video streaming")
            else:
                vid = None
                logger.info("Using screen capture for video streaming")
            
            frame_count = 0
            last_log_time = time.time()

            while self.is_running and self.is_streaming:
                try:
                    # Capture frame
                    if self.use_webcam:
                        ret, frame = vid.read()
                        if not ret or frame is None:
                            logger.debug("Webcam read returned no frame; retrying")
                            time.sleep(0.01)
                            continue
                        frame = imutils.resize(frame, width=DEFAULT_WIDTH)
                    else:
                        img_pil = ImageGrab.grab()
                        frame = np.array(img_pil, dtype=np.uint8)
                        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        frame = imutils.resize(frame, width=DEFAULT_WIDTH)

                    # Encode JPEG (simple comme server-with-cam.py)
                    encoded, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                    b64encoded = base64.b64encode(buffer)

                    # Send to all connected clients (simple UDP to each registered addr)
                    for client_id, client_info in list(self.connected_clients.items()):
                        try:
                            # client_info may be a tuple (legacy) or a dict with ip/port
                            if isinstance(client_info, dict):
                                addr = (client_info.get('ip'), int(client_info.get('port', VIDEO_PORT)))
                            else:
                                addr = client_info
                            self.video_socket.sendto(b64encoded, addr)
                            frame_count += 1
                            if frame_count % 100 == 0:
                                logger.info(f"Sent {frame_count} frames to {addr}")
                        except Exception as e:
                            logger.debug(f"Error sending to {client_info}: {e}")

                    # Petit délai pour éviter surcharge (optionnel, ajustable)
                    time.sleep(0.01)

                except Exception as e:
                    logger.debug(f"Erreur dans video_streamer loop: {e}")
                    time.sleep(0.01)
                    
                # Log stats périodiques
                if time.time() - last_log_time > 10:
                    logger.info(f"Video streamer stats: frames_sent={frame_count}, clients={len(self.connected_clients)}")
                    last_log_time = time.time()
                    
        except Exception as e:
            self.error_occurred.emit(f"Erreur vidéo: {e}")
            logger.exception(f"Video streamer fatal error: {e}")
        finally:
            if self.use_webcam and 'vid' in locals():
                vid.release()
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
                    # Store client info as dict so we can keep username + port
                    # Store connection socket so server can send commands back to client
                    self.connected_clients[client_id] = {'ip': addr[0], 'port': VIDEO_PORT, 'username': None, 'conn': conn}
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

    def send_command_to_client(self, client_id, command_dict):
        """Send a JSON command to a connected client via its command socket."""
        try:
            info = self.connected_clients.get(client_id)
            if not info:
                logger.warning(f"send_command_to_client: unknown client_id {client_id}")
                return False
            conn = info.get('conn')
            if not conn:
                logger.warning(f"send_command_to_client: no conn for {client_id}")
                return False
            msg = json.dumps(command_dict) + "\n"
            conn.sendall(msg.encode('utf-8'))
            return True
        except Exception as e:
            logger.exception(f"Failed to send command to {client_id}: {e}")
            return False
                
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
                                username = command.get('username') or None
                                # Update mapping so we send video UDP to the provided port and store username
                                existing = self.connected_clients.get(client_id, {})
                                existing['ip'] = addr[0]
                                existing['port'] = video_port
                                existing['username'] = username
                                # preserve existing 'conn' if present
                                self.connected_clients[client_id] = existing
                                logger.info(f"Registered client {client_id} -> {(addr[0], video_port)} (username={username})")

                                # Démarrer automatiquement le streaming quand un client s'enregistre
                                if not self.is_streaming:
                                    logger.info("Auto-starting streaming for registered client")
                                    self.start_streaming()
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
            if 'keys' in command:
                key_names = command['keys']
            else:
                key_names = [command['key']]
            for key_name in key_names:
                # Debug temporaire pour les touches directionnelles
                if key_name in ['arrow_left', 'arrow_up', 'arrow_right', 'arrow_down', 'left', 'up', 'right', 'down']:
                    print(f"DEBUG SERVER: Processing arrow key: {key_name}, action: {action}")
                
                # Gestion spéciale des touches directionnelles sur Windows
                arrow_keys = ['arrow_left', 'arrow_up', 'arrow_right', 'arrow_down']
                if key_name in arrow_keys:
                    if action == 'press':
                        if not self._press_arrow_key(key_name):
                            # Fallback à pynput si ctypes échoue
                            pynput_key = self.get_pynput_key(key_name)
                            if pynput_key:
                                self.keyboard.press(pynput_key)
                    elif action == 'release':
                        if not self._release_arrow_key(key_name):
                            # Fallback à pynput si ctypes échoue
                            pynput_key = self.get_pynput_key(key_name)
                            if pynput_key:
                                self.keyboard.release(pynput_key)
                else:
                    # Touches normales via pynput
                    pynput_key = self.get_pynput_key(key_name)
                    
                    if pynput_key:
                        try:
                            if action == 'press':
                                self.keyboard.press(pynput_key)
                            elif action == 'release':
                                self.keyboard.release(pynput_key)
                        except Exception as e:
                            logger.error(f"Failed to execute key action {action} for {key_name}: {e}")
                    else:
                        logger.warning(f"Could not map key_name '{key_name}' to pynput key")
                    
    def add_client(self, client_ip):
        """Ajoute un client pour recevoir le flux vidéo"""
        client_id = f"{client_ip}:{VIDEO_PORT}"
        self.connected_clients[client_id] = {'ip': client_ip, 'port': VIDEO_PORT, 'username': None}
        self.client_connected.emit(client_id)
        
    def remove_client(self, client_id):
        """Retire un client"""
        if client_id in self.connected_clients:
            del self.connected_clients[client_id]
            self.client_disconnected.emit(client_id)
    
    def _press_arrow_key(self, direction):
        """Appuie sur une touche directionnelle en utilisant l'API Windows native"""
        if platform.system() == 'Windows':
            vk_codes = {
                'arrow_left': self.VK_LEFT,
                'arrow_up': self.VK_UP,
                'arrow_right': self.VK_RIGHT,
                'arrow_down': self.VK_DOWN
            }
            if direction in vk_codes:
                print(f"DEBUG: Pressing {direction} with ctypes, VK={vk_codes[direction]}")
                ctypes.windll.user32.keybd_event(vk_codes[direction], 0, 0, 0)
                return True
        return False
    
    def _release_arrow_key(self, direction):
        """Relâche une touche directionnelle en utilisant l'API Windows native"""
        if platform.system() == 'Windows':
            vk_codes = {
                'arrow_left': self.VK_LEFT,
                'arrow_up': self.VK_UP,
                'arrow_right': self.VK_RIGHT,
                'arrow_down': self.VK_DOWN
            }
            if direction in vk_codes:
                print(f"DEBUG: Releasing {direction} with ctypes, VK={vk_codes[direction]}")
                ctypes.windll.user32.keybd_event(vk_codes[direction], 0, self.KEYEVENTF_KEYUP, 0)
                return True
        return False
