"""
Configuration globale de l'application Screen Sharing
"""
import os

# --- CONFIGURATION RÉSEAU ---
VIDEO_PORT = 9999
COMMAND_PORT = 9998
DISCOVERY_PORT = 9997  # Port UDP pour la découverte des serveurs actifs
# Buffer UDP assez grand pour recevoir les frames (max ~65KB pour UDP)
BUFFER_SIZE = 131072  # 128KB buffer for socket recv

# --- CONFIGURATION VIDÉO ---
# Résolution réduite pour garder les paquets UDP sous ~60KB
# Increase default capture width for better image quality (can be overridden with SS_WIDTH)
DEFAULT_WIDTH = int(os.getenv("SS_WIDTH", "1280"))
# DEFAULT_HEIGHT is kept for backward compatibility, but we'll compute height dynamically when needed
DEFAULT_HEIGHT = int(os.getenv("SS_HEIGHT", "720"))
# Qualité JPEG (plus haut = meilleure image, plus de bande passante)
JPEG_QUALITY = int(os.getenv("SS_JPEG_QUALITY", "90"))

# --- CONFIGURATION UTILISATEUR ---
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
