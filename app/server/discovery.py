"""
Broadcast de découverte réseau - Annonce du serveur sur le réseau local
"""
import socket
import json
import time
import threading
import logging

from ..config import COMMAND_PORT, VIDEO_PORT, DISCOVERY_PORT

logger = logging.getLogger("screenshare.server.discovery")


class DiscoveryBroadcaster:
    """Gère le broadcast UDP pour annoncer le serveur sur le réseau."""
    
    def __init__(self, sharer_name: str = "Unknown"):
        """Initialise le broadcaster.
        
        Args:
            sharer_name: Nom affiché pour la découverte réseau
        """
        self.sharer_name = sharer_name
        self._socket = None
        self._thread = None
        self._running = False
    
    @staticmethod
    def get_local_ip() -> str:
        """Récupère l'adresse IP locale.
        
        Returns:
            Adresse IP locale ou "127.0.0.1" en cas d'erreur
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    @staticmethod
    def get_hostname() -> str:
        """Récupère le nom de la machine.
        
        Returns:
            Nom de la machine ou "Unknown" en cas d'erreur
        """
        try:
            return socket.gethostname()
        except Exception:
            return "Unknown"
    
    def start(self):
        """Démarre le broadcast de découverte."""
        if self._thread and self._thread.is_alive():
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self._thread.start()
        logger.info("Discovery broadcast started")
    
    def stop(self):
        """Arrête le broadcast de découverte."""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        logger.info("Discovery broadcast stopped")
    
    def _broadcast_loop(self):
        """Boucle principale de broadcast."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            local_ip = self.get_local_ip()
            
            # Fix Windows: bind à l'IP locale pour éviter les problèmes d'interface
            try:
                self._socket.bind((local_ip, 0))
                logger.info(f"Discovery socket bound to interface: {local_ip}")
            except Exception as e:
                logger.warning(f"Could not bind discovery socket to {local_ip}: {e}")
            
            while self._running:
                try:
                    self._send_announcement(local_ip)
                except Exception as e:
                    logger.debug(f"Discovery broadcast error: {e}")
                
                time.sleep(2)  # Broadcast toutes les 2 secondes
                
        except Exception as e:
            logger.exception(f"Discovery broadcaster error: {e}")
        finally:
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
    
    def _send_announcement(self, local_ip: str):
        """Envoie un message d'annonce.
        
        Args:
            local_ip: Adresse IP locale à annoncer
        """
        announcement = json.dumps({
            "type": "screen_share_announcement",
            "name": self.sharer_name,
            "ip": local_ip,
            "port": COMMAND_PORT,
            "video_port": VIDEO_PORT
        })
        
        data = announcement.encode('utf-8')
        
        # Sur Windows, utiliser '255.255.255.255' qui fonctionne mieux
        try:
            self._socket.sendto(data, ('255.255.255.255', DISCOVERY_PORT))
        except Exception:
            # Fallback standard
            self._socket.sendto(data, ('<broadcast>', DISCOVERY_PORT))
        
        logger.debug(f"Sent discovery broadcast: {announcement}")
