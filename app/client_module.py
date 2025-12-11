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
        
        # Listeners clavier/souris (optionnels, pour capture globale)
        self.keyboard_listener = None
        self.mouse_listener = None
        
    def connect_to_server(self, server_ip):
        """Se connecte à un serveur de partage d'écran"""
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

                reg = {'type': 'register', 'video_port': int(bound_port)}
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
        """Thread de réception du flux vidéo avec réassemblage des chunks"""
        frame_count = 0
        timeout_count = 0
        last_log_time = time.time()
        bound_addr = self.video_socket.getsockname() if self.video_socket else None
        logger.info(f"[VIDEO-RX] Starting receive thread, listening on {bound_addr}, server_ip={self.server_ip}")
        
        # Buffer for reassembling chunked frames
        # Format: {frame_id: {'chunks': {chunk_idx: data}, 'total': total_chunks}}
        frame_buffer = {}
        # Time (seconds) to wait for all chunks of a frame before giving up
        FRAME_ASSEMBLY_TIMEOUT = 2.0
        last_purge_time = time.time()
        current_frame_id = -1
        packets_received = 0
        
        while self.is_running:
            try:
                packet, addr = self.video_socket.recvfrom(BUFFER_SIZE)
                packets_received += 1
                timeout_count = 0  # Reset timeout counter on successful receive
                
                # Parse chunked frame format: "FRAME:frame_id:chunk_idx:total_chunks:data"
                if packet.startswith(b'FRAME:'):
                    try:
                        # Find the header end (4th colon)
                        header_end = 0
                        colon_count = 0
                        for i, b in enumerate(packet):
                            if b == ord(':'):
                                colon_count += 1
                                if colon_count == 4:
                                    header_end = i + 1
                                    break
                        
                        header = packet[:header_end-1].decode('utf-8')
                        chunk_data = packet[header_end:]
                        
                        parts = header.split(':')
                        frame_id = int(parts[1])
                        chunk_idx = int(parts[2])
                        total_chunks = int(parts[3])
                        
                        # Log first packet and periodically
                        if packets_received <= 3 or packets_received % 500 == 0:
                            logger.info(f"[VIDEO-RX] Received chunk {chunk_idx}/{total_chunks} of frame {frame_id} from {addr}, size={len(chunk_data)}")
                        
                        # Initialize buffer for this frame if needed
                        now = time.time()
                        if frame_id not in frame_buffer:
                            # Clean old frames older than timeout
                            old_frames = [fid for fid, meta in frame_buffer.items() if now - meta.get('first_seen', now) > FRAME_ASSEMBLY_TIMEOUT]
                            for old_fid in old_frames:
                                logger.debug(f"Discarding old incomplete frame {old_fid} (timeout)")
                                del frame_buffer[old_fid]

                            frame_buffer[frame_id] = {'chunks': {}, 'total': total_chunks, 'first_seen': now}
                        
                        # Store chunk
                        frame_buffer[frame_id]['chunks'][chunk_idx] = chunk_data
                        
                        # Check if frame is complete
                        if len(frame_buffer[frame_id]['chunks']) == total_chunks:
                            # Reassemble frame
                            frame_data = b''
                            for i in range(total_chunks):
                                frame_data += frame_buffer[frame_id]['chunks'][i]
                            
                            # Clean up buffer
                            del frame_buffer[frame_id]
                            
                            # Decode frame
                            try:
                                data = base64.b64decode(frame_data)
                                npdata = np.frombuffer(data, dtype=np.uint8)
                                frame = cv2.imdecode(npdata, cv2.IMREAD_COLOR)
                                
                                if frame is not None:
                                    frame_count += 1
                                    self.latest_frame = frame
                                    
                                    # Log frame completion periodically
                                    if frame_count <= 3 or frame_count % 30 == 0:
                                        logger.info(f"[VIDEO-RX] Decoded complete frame #{frame_count} (frame_id={frame_id}, size={len(frame_data)})")
                                    
                                    # Convertir en QImage et émettre le signal
                                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                    h, w, ch = frame_rgb.shape
                                    bytes_per_line = ch * w
                                    qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                                    self.frame_received.emit(qimg.copy())
                                else:
                                    logger.warning(f"[VIDEO-RX] Failed to decode frame {frame_id}")
                            except Exception as e:
                                logger.error(f"[VIDEO-RX] Error decoding frame {frame_id}: {e}")
                    
                    except Exception as e:
                        logger.error(f"[VIDEO-RX] Error parsing chunk: {e}")
                # Periodically purge frames that timed out waiting for missing chunks
                current_time = time.time()
                if current_time - last_purge_time > 1.0:
                    stale = [fid for fid, meta in frame_buffer.items() if current_time - meta.get('first_seen', current_time) > FRAME_ASSEMBLY_TIMEOUT]
                    for fid in stale:
                        logger.debug(f"Purging stale incomplete frame {fid} after {FRAME_ASSEMBLY_TIMEOUT}s (received {len(frame_buffer[fid]['chunks'])}/{frame_buffer[fid]['total']})")
                        del frame_buffer[fid]
                    last_purge_time = current_time
                else:
                    # Legacy single-packet frame (backward compatibility)
                    logger.debug(f"[VIDEO-RX] Received legacy packet from {addr}, size={len(packet)}")
                    try:
                        data = base64.b64decode(packet)
                        npdata = np.frombuffer(data, dtype=np.uint8)
                        frame = cv2.imdecode(npdata, cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            frame_count += 1
                            self.latest_frame = frame
                            
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            h, w, ch = frame_rgb.shape
                            bytes_per_line = ch * w
                            qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                            self.frame_received.emit(qimg.copy())
                    except Exception as e:
                        logger.error(f"[VIDEO-RX] Error with legacy packet: {e}")
                    
            except socket.timeout:
                timeout_count += 1
                # Log a timeout only occasionally to avoid log spam (every ~5 seconds)
                if timeout_count % 50 == 1:
                    logger.warning(f"[VIDEO-RX] Timeout waiting for video (consecutive={timeout_count}), bound={bound_addr}, frames_received={frame_count}, packets={packets_received}")
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
