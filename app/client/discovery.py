"""
DiscoveryScanner: Scans for screen sharing servers on the local network.
"""
import socket
import json
import threading
import time
from PySide6.QtCore import QObject, Signal
from ..config import DISCOVERY_PORT, COMMAND_PORT, VIDEO_PORT
import logging

logger = logging.getLogger("screenshare.client.discovery")

class DiscoveryScanner(QObject):
    server_found = Signal(dict)  # Emits {name, ip, port, video_port}
    scan_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._socket = None
        self._found_servers = {}  # ip -> server_info

    def start_scan(self, duration=3.0):
        if self._running:
            return
        self._running = True
        self._found_servers = {}
        thread = threading.Thread(target=self._scan_thread, args=(duration,), daemon=True)
        thread.start()

    def stop_scan(self):
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass

    def _scan_thread(self, duration):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._socket.bind(('', DISCOVERY_PORT))
            self._socket.settimeout(0.5)
            start_time = time.time()
            while self._running and (time.time() - start_time) < duration:
                try:
                    data, addr = self._socket.recvfrom(1024)
                    try:
                        message = json.loads(data.decode('utf-8'))
                        if message.get('type') == 'screen_share_announcement':
                            server_ip = message.get('ip', addr[0])
                            if server_ip not in self._found_servers:
                                server_info = {
                                    'name': message.get('name', 'Unknown'),
                                    'ip': server_ip,
                                    'port': message.get('port', COMMAND_PORT),
                                    'video_port': message.get('video_port', VIDEO_PORT)
                                }
                                self._found_servers[server_ip] = server_info
                                self.server_found.emit(server_info)
                    except json.JSONDecodeError:
                        pass
                except socket.timeout:
                    continue
                except Exception:
                    if self._running:
                        pass
        except Exception as e:
            logger.debug(f"Discovery scan error: {e}")
        finally:
            self._running = False
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
            self.scan_finished.emit()

    def get_found_servers(self):
        return list(self._found_servers.values())
