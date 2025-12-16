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

from .config import VIDEO_PORT, COMMAND_PORT, BUFFER_SIZE, DEFAULT_WIDTH, DEFAULT_HEIGHT, SERVER_IP, app_state, USE_WEBCAM, JPEG_QUALITY
import logging
import os
from logging.handlers import RotatingFileHandler, DatagramHandler

# --- Logging configuration ---
LOG_LEVEL = os.getenv("SS_LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("screenshare.client")
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Rotating handler
    try:
        logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        file_path = os.path.join(logs_dir, "client.log")
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
        # Thread to listen for server commands
        self.command_listen_thread = None
        # If this client will stream its screen to a monitor (admin), track streaming state
        self.is_streaming_out = False
        self.streaming_thread = None
        self.streaming_target = None  # tuple (ip, port)
        
        # Listeners clavier/souris (optionnels, pour capture globale)
        self.keyboard_listener = None
        self.mouse_listener = None
        
    def connect_to_server(self, server_ip):
        """Se connecte à un serveur de partage d'écran"""
        # If no server_ip provided, use the configured SERVER_IP (no user prompt)
        if not server_ip:
            server_ip = SERVER_IP
        self.server_ip = server_ip
        logger.info(f"[CONNECT] Attempting connection to server {server_ip}...")
        
        try:
            # Socket vidéo UDP
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
            self.video_socket.settimeout(0.1)
            
            # Bind explicitly to an ephemeral UDP port (0) so multiple viewers don't conflict.
            try:
                self.video_socket.bind(('0.0.0.0', 0))
                bound_addr = self.video_socket.getsockname()
                logger.info(f"[CONNECT] UDP video socket bound to {bound_addr}")
            except Exception:
                # If bind fails, continue; we'll still attempt to use the socket.
                logger.exception("Failed to bind video socket to ephemeral port")
                
            # Socket commandes TCP
            logger.info(f"[CONNECT] Connecting TCP command socket to {server_ip}:{COMMAND_PORT}...")
            self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.command_socket.settimeout(5.0)
            self.command_socket.connect((server_ip, COMMAND_PORT))
            logger.info(f"[CONNECT] TCP connected! Local addr: {self.command_socket.getsockname()}")
            
            self.is_connected = True
            self.is_running = True
            
            # Démarrer le thread de réception (doit être lancé avant d'attendre des paquets)
            self.receive_thread = threading.Thread(target=self._receive_video, daemon=True)
            self.receive_thread.start()

            # Inform the server which UDP port we listen on for video (register)
            try:
                bound_port = self.video_socket.getsockname()[1]
                # If socket was not bound, getsockname may return 0; guard against that.
                if not bound_port:
                    # Try to bind explicitly to ephemeral port
                    try:
                        self.video_socket.bind(('0.0.0.0', 0))
                        bound_port = self.video_socket.getsockname()[1]
                    except Exception:
                        bound_port = 0
                # Include username when registering so the server can display it
                username = None
                try:
                    username = app_state.current_user
                except Exception:
                    username = None

                reg = {'type': 'register', 'video_port': int(bound_port)}
                if username:
                    reg['username'] = username
                self.command_socket.sendall((json.dumps(reg) + '\n').encode('utf-8'))
                logger.info(f"[CONNECT] Sent register to server: {reg} (server should send UDP to our port {bound_port})")
            except Exception as e:
                logger.exception(f"Failed to send register to server: {e}")
            # Also send START to signal readiness (server may ignore if using register)
            try:
                self.video_socket.sendto(b'START', (server_ip, VIDEO_PORT))
                logger.debug(f"Sent START to {(server_ip, VIDEO_PORT)}")
            except Exception:
                logger.debug("Failed to send START (non-fatal)")
            # Start a thread to listen for commands from the server
            try:
                self.command_listen_thread = threading.Thread(target=self._listen_server_commands, daemon=True)
                self.command_listen_thread.start()
            except Exception:
                logger.exception("Failed to start command listener thread")
        
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
        """Thread de réception du flux vidéo (simple comme client-with-cam.py)"""
        frame_count = 0
        timeout_count = 0
        bound_addr = self.video_socket.getsockname() if self.video_socket else None
        logger.info(f"[VIDEO-RX] Starting receive thread, listening on {bound_addr}, server_ip={self.server_ip}")
        
        while self.is_running:
            try:
                # Recevoir paquet UDP (base64 direct)
                packet, addr = self.video_socket.recvfrom(BUFFER_SIZE)
                timeout_count = 0  # Reset sur réception réussie
                
                # Décoder directement (comme client-with-cam.py)
                try:
                    data = base64.b64decode(packet)
                    npdata = np.frombuffer(data, dtype=np.uint8)
                    frame = cv2.imdecode(npdata, cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        frame_count += 1
                        self.latest_frame = frame
                        
                        # Log périodique
                        if frame_count % 100 == 0:
                            logger.info(f"[VIDEO-RX] Received {frame_count} frames from {addr}")
                        
                        # Convertir en QImage et émettre
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        h, w, ch = frame_rgb.shape
                        bytes_per_line = ch * w
                        qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                        self.frame_received.emit(qimg.copy())
                    else:
                        logger.debug(f"[VIDEO-RX] Failed to decode frame")
                        
                except Exception as e:
                    logger.debug(f"[VIDEO-RX] Error decoding packet: {e}")
                    
            except socket.timeout:
                timeout_count += 1
                # Log timeout seulement toutes les 5 secondes
                if timeout_count % 50 == 1:
                    logger.debug(f"[VIDEO-RX] Waiting for video... (frames_received={frame_count})")
                continue
            except Exception as e:
                if self.is_running:
                    logger.error(f"[VIDEO-RX] Error in receive loop: {e}")
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

    # ---- New: listen for server commands and optional streaming out ----
    def _listen_server_commands(self):
        """Listen for JSON commands from the server on the TCP command socket."""
        logger.info("Starting server command listener thread")
        try:
            conn = self.command_socket
            buf = b''
            while self.is_running and conn:
                try:
                    data = conn.recv(4096)
                    if not data:
                        break
                    buf += data
                    while b'\n' in buf:
                        line, buf = buf.split(b'\n', 1)
                        try:
                            cmd = json.loads(line.decode('utf-8'))
                        except Exception:
                            logger.warning("Invalid command JSON from server")
                            continue
                        self._process_server_command(cmd)
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.exception(f"Error in server command listener: {e}")
                    break
        finally:
            logger.info("Server command listener thread exiting")

    def _process_server_command(self, cmd):
        """Process a command sent by the server/admin."""
        try:
            t = cmd.get('type')
            if t == 'control' and cmd.get('action') == 'start_stream':
                ip = cmd.get('monitor_ip')
                port = int(cmd.get('monitor_port', VIDEO_PORT))
                self._start_streaming_to((ip, port))
            elif t == 'control' and cmd.get('action') == 'stop_stream':
                self._stop_streaming()
            else:
                logger.debug(f"Received server command: {cmd}")
        except Exception as e:
            logger.exception(f"Failed to process server command: {e}")

        # Handle input/control commands coming from admin
        try:
            if cmd.get('type') == 'mouse':
                action = cmd.get('action')
                if action != 'scroll':
                    x = int(cmd.get('x', 0) * self.display_width)
                    y = int(cmd.get('y', 0) * self.display_height)
                    try:
                        mouse.Controller().position = (x, y)
                    except Exception:
                        pass

                if action == 'move':
                    pass
                elif action == 'scroll':
                    try:
                        m = mouse.Controller()
                        m.scroll(int(cmd.get('dx', 0)), int(cmd.get('dy', 0)))
                    except Exception:
                        pass
                else:
                    btn = cmd.get('button')
                    btn_map = {'left': mouse.Button.left, 'right': mouse.Button.right, 'middle': mouse.Button.middle}
                    b = btn_map.get(btn)
                    if b:
                        m = mouse.Controller()
                        if action == 'press':
                            m.press(b)
                        elif action == 'release':
                            m.release(b)

            elif cmd.get('type') == 'key':
                action = cmd.get('action')
                key_name = cmd.get('key')
                # Map to pynput key where appropriate
                pk = None
                try:
                    from pynput.keyboard import Key as PKey
                    special = {
                        'enter': PKey.enter,
                        'backspace': PKey.backspace,
                        'tab': PKey.tab,
                        'esc': PKey.esc,
                        'space': PKey.space,
                        'left': PKey.left,
                        'right': PKey.right,
                        'up': PKey.up,
                        'down': PKey.down,
                    }
                    pk = special.get(key_name, None)
                except Exception:
                    pk = None

                kctrl = keyboard.Controller()
                try:
                    if action == 'press':
                        if pk:
                            kctrl.press(pk)
                        else:
                            kctrl.press(key_name)
                    elif action == 'release':
                        if pk:
                            kctrl.release(pk)
                        else:
                            kctrl.release(key_name)
                except Exception:
                    pass
        except Exception:
            pass

    def _start_streaming_to(self, target):
        """Start sending captured frames via UDP to target (ip, port)."""
        if not target or not target[0]:
            logger.warning("Invalid streaming target")
            return
        if self.is_streaming_out:
            logger.info("Already streaming out; restarting target")
            self.streaming_target = target
            return
        self.is_streaming_out = True
        self.streaming_target = target

        def _stream_loop():
            logger.info(f"Starting outbound stream to {target}")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                use_webcam = USE_WEBCAM
                if use_webcam:
                    cap = cv2.VideoCapture(0)
                    if not cap.isOpened():
                        logger.error("Webcam open failed for outbound streaming")
                        return
                else:
                    cap = None

                while self.is_streaming_out:
                    try:
                        if cap is not None:
                            ret, frame = cap.read()
                            if not ret:
                                time.sleep(0.01)
                                continue
                        else:
                            try:
                                from PIL import ImageGrab as PILGrab
                                img = PILGrab.grab()
                                frame = np.array(img, dtype=np.uint8)
                                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                            except Exception:
                                time.sleep(0.05)
                                continue

                        encoded, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                        b64encoded = base64.b64encode(buffer)
                        try:
                            sock.sendto(b64encoded, target)
                        except Exception as e:
                            logger.debug(f"UDP send error to {target}: {e}")
                        time.sleep(0.02)
                    except Exception as e:
                        logger.exception(f"Error in outbound streaming loop: {e}")
                        time.sleep(0.1)
            except Exception as e:
                logger.exception(f"Outbound streaming error: {e}")
            finally:
                try:
                    if cap is not None:
                        cap.release()
                except:
                    pass
                try:
                    sock.close()
                except:
                    pass
                logger.info("Outbound stream loop ended")

        self.streaming_thread = threading.Thread(target=_stream_loop, daemon=True)
        self.streaming_thread.start()

    def _stop_streaming(self):
        if not self.is_streaming_out:
            return
        self.is_streaming_out = False
        self.streaming_target = None
        try:
            if self.streaming_thread:
                self.streaming_thread.join(timeout=0.5)
        except Exception:
            pass


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
