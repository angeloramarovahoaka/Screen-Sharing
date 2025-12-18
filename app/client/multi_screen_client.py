"""
MultiScreenClient: Manages multiple simultaneous screen connections.
"""
from PySide6.QtCore import QObject, Signal, QImage
from .screen_client import ScreenClient

class MultiScreenClient(QObject):
    screen_added = Signal(str, QImage)
    screen_removed = Signal(str)
    screen_updated = Signal(str, QImage)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.clients = {}

    def add_screen(self, screen_id, server_ip):
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
        if screen_id in self.clients:
            self.clients[screen_id].disconnect()
            del self.clients[screen_id]
            self.screen_removed.emit(screen_id)

    def get_client(self, screen_id):
        return self.clients.get(screen_id)

    def _on_frame_received(self, screen_id, image):
        self.screen_updated.emit(screen_id, image)

    def disconnect_all(self):
        for client in self.clients.values():
            client.disconnect()
        self.clients.clear()
