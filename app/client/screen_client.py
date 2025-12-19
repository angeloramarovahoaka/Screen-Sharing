"""
ScreenClient: Handles video stream reception and command sending.
"""
import socket
import json
import threading
import time
import base64
import numpy as np
import cv2
import os
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage
from ..config import VIDEO_PORT, COMMAND_PORT, BUFFER_SIZE, DEFAULT_WIDTH, DEFAULT_HEIGHT
import logging

logger = logging.getLogger("screenshare.client.screen_client")

class ScreenClient(QObject):
    frame_received = Signal(QImage)
    status_changed = Signal(str)
    stream_state_changed = Signal(str)  # 'started' | 'stopped'
    connected = Signal()
    disconnected = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server_ip = None
        self.display_width = DEFAULT_WIDTH
        self.display_height = DEFAULT_HEIGHT
        self.is_running = False
        self.is_connected = False
        self.latest_frame = None
        self.video_socket = None
        self.command_socket = None
        self.receive_thread = None
        self.control_thread = None
        self.keyboard_listener = None
        self.mouse_listener = None

    def connect_to_server(self, server_ip):
        self.server_ip = server_ip
        logger.info(f"[CONNECT] Attempting connection to server {server_ip}...")
        try:
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.video_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
            self.video_socket.settimeout(0.1)
            try:
                self.video_socket.bind(('0.0.0.0', 0))
                bound_addr = self.video_socket.getsockname()
                logger.info(f"[CONNECT] UDP video socket bound to {bound_addr}")
            except Exception:
                logger.exception("Failed to bind video socket to ephemeral port")
            logger.info(f"[CONNECT] Connecting TCP command socket to {server_ip}:{COMMAND_PORT}...")
            self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.command_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.command_socket.settimeout(5.0)
            self.command_socket.connect((server_ip, COMMAND_PORT))
            logger.info(f"[CONNECT] TCP connected! Local addr: {self.command_socket.getsockname()}")
            self.is_connected = True
            self.is_running = True
            self.receive_thread = threading.Thread(target=self._receive_video, daemon=True)
            self.receive_thread.start()
            try:
                self.command_socket.settimeout(0.5)
            except Exception:
                pass
            self.control_thread = threading.Thread(target=self._receive_control, daemon=True)
            self.control_thread.start()
            try:
                bound_port = self.video_socket.getsockname()[1]
                if not bound_port:
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
        self.is_running = False
        self.is_connected = False
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

    def _receive_control(self):
        buf = b""
        while self.is_running and self.is_connected and self.command_socket:
            try:
                chunk = self.command_socket.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8", errors="replace"))
                    except Exception:
                        continue
                    if isinstance(msg, dict) and msg.get("type") == "stream":
                        state = str(msg.get("state", "")).strip().lower()
                        if state in {"started", "stopped"}:
                            self.stream_state_changed.emit(state)
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                logger.debug(f"[CTRL-RX] Error: {e}")
                break
        if self.is_running and self.is_connected:
            try:
                self.disconnect()
            except Exception:
                pass

    def _receive_video(self):
        frame_count = 0
        timeout_count = 0
        bound_addr = self.video_socket.getsockname() if self.video_socket else None
        logger.info(f"[VIDEO-RX] Starting receive thread, listening on {bound_addr}, server_ip={self.server_ip}")
        while self.is_running:
            try:
                packet, addr = self.video_socket.recvfrom(BUFFER_SIZE)
                timeout_count = 0
                try:
                    npdata = np.frombuffer(packet, dtype=np.uint8)
                    frame = cv2.imdecode(npdata, cv2.IMREAD_COLOR)
                    if frame is None:
                        data = base64.b64decode(packet)
                        npdata = np.frombuffer(data, dtype=np.uint8)
                        frame = cv2.imdecode(npdata, cv2.IMREAD_COLOR)
                    if frame is not None:
                        frame_count += 1
                        self.latest_frame = frame
                        if frame_count % 100 == 0:
                            logger.info(f"[VIDEO-RX] Received {frame_count} frames from {addr}")
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
                if timeout_count % 50 == 1:
                    logger.debug(f"[VIDEO-RX] Waiting for video... (frames_received={frame_count})")
                continue
            except Exception as e:
                if self.is_running:
                    logger.error(f"[VIDEO-RX] Error in receive loop: {e}")
                    time.sleep(0.001)

    def send_command(self, command_dict):
        if not self.command_socket or not self.is_connected:
            return False
        try:
            message = json.dumps(command_dict) + '\n'
            if os.getenv("SS_INPUT_DEBUG", "0") == "1":
                logger.info(f"[INPUT-CLIENT] send_command: {command_dict}")
            self.command_socket.sendall(message.encode('utf-8'))
            return True
        except Exception as e:
            if os.getenv("SS_INPUT_DEBUG", "0") == "1":
                logger.exception(f"[INPUT-CLIENT] send_command failed: {e}")
            return False

    def send_mouse_move(self, x, y, widget_width, widget_height):
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
        command = {
            'type': 'mouse',
            'action': 'scroll',
            'dx': dx,
            'dy': dy
        }
        self.send_command(command)

    def send_key_event(self, key_name, action):
        command = {
            'type': 'key',
            'action': action,
            'key': key_name
        }
        self.send_command(command)

    def get_latest_frame(self):
        return self.latest_frame

    def set_display_size(self, width, height):
        self.display_width = width
        self.display_height = height
