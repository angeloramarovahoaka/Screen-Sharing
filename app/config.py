"""
Configuration globale de l'application Screen Sharing
"""
import os

# --- CONFIGURATION RÉSEAU ---
VIDEO_PORT = 9999
COMMAND_PORT = 9998
AUDIO_PORT = 9997
# Buffer UDP assez grand pour recevoir les frames (max ~65KB pour UDP)
BUFFER_SIZE = 131072  # 128KB buffer for socket recv

# --- CONFIGURATION VIDÉO ---
# Résolution réduite pour garder les paquets UDP sous ~60KB
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 360
# Qualité JPEG réduite pour des paquets plus petits
JPEG_QUALITY = 50  # Lower quality = smaller packets, better cross-network performance

# Utiliser la webcam au lieu de la capture d'écran
USE_WEBCAM = True

# --- CONFIGURATION AUDIO ---
AUDIO_RATE = 44100
AUDIO_CHANNELS = 1
AUDIO_CHUNK = 1024

# --- CONFIGURATION UTILISATEUR ---
# Simulation simple d'utilisateurs (dans une vraie app, utiliser une BDD)
USERS = {
    "admin": "admin123",
    "user1": "password1",
    "user2": "password2"
}

# --- ÉTAT DE L'APPLICATION ---
class AppState:
    """État global de l'application"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.current_user = None
            cls._instance.connected_screens = {}
            cls._instance.is_streaming = False
            cls._instance.is_in_call = False
        return cls._instance
    
    def login(self, username):
        self.current_user = username
        
    def logout(self):
        self.current_user = None
        self.connected_screens = {}
        self.is_streaming = False
        self.is_in_call = False
        
    def is_logged_in(self):
        return self.current_user is not None
    
    def add_screen(self, screen_id, screen_info):
        self.connected_screens[screen_id] = screen_info
        
    def remove_screen(self, screen_id):
        if screen_id in self.connected_screens:
            del self.connected_screens[screen_id]

# Instance globale de l'état
app_state = AppState()
