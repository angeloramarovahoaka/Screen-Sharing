"""
Classe principale du serveur de partage d'écran
"""
import socket
import threading
import json
import time
import logging
import os
from typing import Dict, Optional
from PySide6.QtCore import QObject, Signal

from ..config import VIDEO_PORT, COMMAND_PORT
from .monitor_manager import MonitorManager
from .video_streamer import VideoStreamer
from .command_handler import CommandHandler
from .discovery import DiscoveryBroadcaster

logger = logging.getLogger("screenshare.server")


class ScreenServer(QObject):
    """
    Serveur de partage d'écran.
    Envoie le flux vidéo et reçoit les commandes de contrôle.
    """
    
    # Signaux Qt
    status_changed = Signal(str)
    client_connected = Signal(str)
    client_disconnected = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Gestionnaires
        self.monitor_manager = MonitorManager()
        self.video_streamer = VideoStreamer(self.monitor_manager)
        self.command_handler = CommandHandler(
            self.monitor_manager.screen_width,
            self.monitor_manager.screen_height
        )
        self.discovery = None  # Initialisé au démarrage
        
        # État
        self.is_running = False
        self.is_streaming = False
        
        # Sockets
        self.command_socket = None
        
        # Threads
        self.video_thread = None
        self.command_thread = None
        
        # Connexions TCP actives (pour les notifications serveur -> client)
        self._command_conns: Dict[str, socket.socket] = {}
        self._command_conns_lock = threading.Lock()
        
        # Nom du partageur
        self._sharer_name = None
    
    # =========================================================================
    # Propriétés déléguées aux gestionnaires
    # =========================================================================
    
    @property
    def screen_width(self) -> int:
        return self.monitor_manager.screen_width
    
    @property
    def screen_height(self) -> int:
        return self.monitor_manager.screen_height
    
    @property
    def connected_clients(self) -> dict:
        return self.video_streamer.connected_clients
    
    @connected_clients.setter
    def connected_clients(self, value: dict):
        self.video_streamer.connected_clients = value
    
    # =========================================================================
    # API publique - Moniteurs
    # =========================================================================
    
    def get_monitors(self) -> list:
        """Retourne la liste des moniteurs disponibles."""
        return self.monitor_manager.get_monitors()
    
    def set_monitor(self, monitor_id: int) -> bool:
        """Définit le moniteur à capturer."""
        result = self.monitor_manager.set_monitor(monitor_id)
        # Mettre à jour le command handler avec la géométrie (offset + taille)
        mi = self.monitor_manager.monitor_info or {}
        self.command_handler.update_screen_geometry(
            mi.get('left', 0),
            mi.get('top', 0),
            self.monitor_manager.screen_width,
            self.monitor_manager.screen_height
        )
        return result
    
    @property
    def monitor_info(self):
        """Info du moniteur sélectionné."""
        return self.monitor_manager.monitor_info
    
    # =========================================================================
    # API publique - Démarrage/Arrêt
    # =========================================================================
    
    def start(self, client_ip: str = None, sharer_name: str = None):
        """Démarre le serveur (écoute commandes seulement, pas de streaming auto).
        
        Args:
            client_ip: IP d'un client initial (optionnel)
            sharer_name: Nom affiché pour la découverte réseau
        """
        self._sharer_name = sharer_name or DiscoveryBroadcaster.get_hostname()
        self.is_running = True
        
        # Si une IP client est fournie, l'ajouter
        if client_ip:
            self.add_client(client_ip)
            logger.info(f"Starting ScreenServer for client {client_ip}")
        else:
            logger.info("Starting ScreenServer (waiting for clients to register via TCP)")
        
        # Démarrer le thread des commandes
        self.command_thread = threading.Thread(target=self._command_listener, daemon=True)
        self.command_thread.start()
        
        self.status_changed.emit("Serveur démarré (prêt pour streaming)")
        logger.info("Serveur démarré - en attente de demande de streaming")
    
    def stop(self):
        """Arrête le serveur."""
        self.is_running = False
        self.is_streaming = False
        logger.info("Stopping ScreenServer")
        
        # Notifier les viewers
        self._broadcast_control({"type": "stream", "state": "stopped"})
        
        # Arrêter le streaming
        self.stop_streaming()
        
        # Fermer le socket de commandes
        if self.command_socket:
            try:
                self.command_socket.close()
            except Exception:
                pass
            self.command_socket = None
        
        # Fermer les connexions de commandes actives
        with self._command_conns_lock:
            for _, conn in list(self._command_conns.items()):
                try:
                    conn.close()
                except Exception:
                    pass
            self._command_conns.clear()
        
        self.status_changed.emit("Serveur arrêté")
        logger.info("Serveur arrêté")
    
    def start_streaming(self):
        """Démarre le streaming vidéo."""
        if self.is_streaming:
            logger.warning("Streaming already active")
            return
        
        self.is_streaming = True
        
        # Démarrer le video streamer
        self.video_streamer.start()
        
        # Démarrer le thread de streaming
        self.video_thread = threading.Thread(target=self._video_loop, daemon=True)
        self.video_thread.start()
        
        # Démarrer la découverte réseau
        self.discovery = DiscoveryBroadcaster(self._sharer_name)
        self.discovery.start()
        
        self.status_changed.emit("Streaming vidéo démarré")
        logger.info("Video streaming started on demand")
        
        self._broadcast_control({"type": "stream", "state": "started"})
    
    def stop_streaming(self):
        """Arrête le streaming vidéo."""
        self.is_streaming = False
        
        # Arrêter la découverte
        if self.discovery:
            self.discovery.stop()
            self.discovery = None
        
        # Arrêter le video streamer
        self.video_streamer.stop()
        
        self.status_changed.emit("Streaming vidéo arrêté")
        logger.info("Video streaming stopped")
        
        self._broadcast_control({"type": "stream", "state": "stopped"})
    
    # =========================================================================
    # API publique - Gestion des clients
    # =========================================================================
    
    def add_client(self, client_ip: str):
        """Ajoute un client pour recevoir le flux vidéo."""
        client_id = f"{client_ip}:{VIDEO_PORT}"
        self.video_streamer.add_client(client_id, (client_ip, VIDEO_PORT))
        self.client_connected.emit(client_id)
    
    def remove_client(self, client_id: str):
        """Retire un client."""
        self.video_streamer.remove_client(client_id)
        self.client_disconnected.emit(client_id)
    
    # =========================================================================
    # Threads internes
    # =========================================================================
    
    def _video_loop(self):
        """Boucle principale de streaming vidéo."""
        try:
            logger.info("Video streamer thread started")
            
            while self.is_running and self.is_streaming:
                success = self.video_streamer.capture_and_send()
                if not success:
                    break
                time.sleep(0.01)  # ~100 FPS max
                
        except Exception as e:
            self.error_occurred.emit(f"Erreur vidéo: {e}")
            logger.exception(f"Video streamer fatal error: {e}")
    
    def _command_listener(self):
        """Thread d'écoute des commandes TCP."""
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
                    
                    # Enregistrer le client pour le flux vidéo
                    self.video_streamer.add_client(client_id, (addr[0], VIDEO_PORT))
                    self.client_connected.emit(client_id)
                    logger.info(f"Accepted command connection from {addr}; client_id={client_id}")
                    
                    # Garder la connexion TCP pour les notifications
                    with self._command_conns_lock:
                        self._command_conns[client_id] = conn
                    
                    # Traiter les commandes dans un thread dédié
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
                        logger.debug(f"Error in command_listener: {e}")
                        time.sleep(0.1)
                        
        except Exception as e:
            self.error_occurred.emit(f"Erreur commandes: {e}")
            logger.exception(f"Command listener fatal error: {e}")
        finally:
            if self.command_socket:
                self.command_socket.close()
    
    def _handle_client_commands(self, conn: socket.socket, addr: tuple, client_id: str):
        """Gère les commandes d'un client spécifique."""
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
                    logger.exception("Failed to decode command bytes")
                    continue
                
                for command_json in command_str.split('\n'):
                    if not command_json:
                        continue
                    
                    try:
                        command = json.loads(command_json)
                        self._process_command(command, client_id, addr)
                    except json.JSONDecodeError:
                        logger.warning(f"JSON decode error: {command_json}")
                    except Exception as e:
                        logger.exception(f"Error executing command: {e}")
                        
        except Exception as e:
            logger.exception(f"Exception in client handler for {client_id}: {e}")
        finally:
            conn.close()
            with self._command_conns_lock:
                self._command_conns.pop(client_id, None)
            self.video_streamer.remove_client(client_id)
            self.client_disconnected.emit(client_id)
            logger.info(f"Closed command connection for {client_id}")
    
    def _process_command(self, command: dict, client_id: str, addr: tuple):
        """Traite une commande reçue.
        
        Args:
            command: Commande JSON parsée
            client_id: ID du client
            addr: Adresse du client
        """
        if command.get('type') == 'register':
            # Enregistrement du client avec son port vidéo
            try:
                video_port = int(command.get('video_port', VIDEO_PORT))
                self.video_streamer.add_client(client_id, (addr[0], video_port))
                logger.info(f"Registered client {client_id} -> {(addr[0], video_port)}")
                
                # Démarrer le streaming si pas déjà actif
                if not self.is_streaming:
                    logger.info("Auto-starting streaming for registered client")
                    self.start_streaming()
            except Exception as e:
                logger.exception(f"Failed to process register: {e}")
        else:
            # Commande de contrôle (souris, clavier)
            self.command_handler.execute(command)
    
    def _broadcast_control(self, message: dict):
        """Envoie un message à tous les clients connectés."""
        try:
            payload = (json.dumps(message) + "\n").encode("utf-8")
        except Exception:
            return
        
        stale = []
        with self._command_conns_lock:
            for client_id, conn in list(self._command_conns.items()):
                try:
                    conn.sendall(payload)
                except Exception:
                    stale.append(client_id)
            
            for client_id in stale:
                try:
                    conn = self._command_conns.pop(client_id, None)
                    if conn:
                        conn.close()
                except Exception:
                    pass
