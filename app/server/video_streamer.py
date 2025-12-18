"""
Streamer vidéo - Capture et envoi des frames
"""
import cv2
import imutils
import numpy as np
import socket
import time
import logging

try:
    import pyscreenshot as ImageGrab
except ImportError:
    from PIL import ImageGrab

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

from ..config import DEFAULT_WIDTH, JPEG_QUALITY

logger = logging.getLogger("screenshare.server.video")

# Taille maximale UDP
MAX_UDP_PAYLOAD = 60000


class VideoStreamer:
    """Gère la capture d'écran et l'envoi des frames vidéo."""
    
    def __init__(self, monitor_manager):
        """Initialise le streamer vidéo.
        
        Args:
            monitor_manager: Instance de MonitorManager pour la capture
        """
        self.monitor_manager = monitor_manager
        self.socket = None
        self.is_streaming = False
        self.connected_clients = {}  # {client_id: (ip, port)}
        self._mss_context = None
        
        # Stats
        self.frame_count = 0
        self.last_log_time = time.time()
    
    def start(self):
        """Démarre le streaming (crée le socket)."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.is_streaming = True
        self.frame_count = 0
        self.last_log_time = time.time()
        
        # Initialiser mss si disponible et moniteur spécifique sélectionné
        if HAS_MSS and self.monitor_manager.selected_monitor > 0:
            try:
                self._mss_context = mss.mss()
                logger.info("Using mss for screen capture")
            except Exception as e:
                logger.warning(f"Failed to create mss context: {e}, falling back to PIL")
                self._mss_context = None
        
        logger.info("Video streamer started")
    
    def stop(self):
        """Arrête le streaming."""
        self.is_streaming = False
        
        if self._mss_context:
            try:
                self._mss_context.close()
            except Exception:
                pass
            self._mss_context = None
        
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None
        
        logger.info("Video streamer stopped")
    
    def add_client(self, client_id: str, address: tuple):
        """Ajoute un client pour recevoir le flux.
        
        Args:
            client_id: Identifiant unique du client
            address: Tuple (ip, port)
        """
        self.connected_clients[client_id] = address
    
    def remove_client(self, client_id: str):
        """Retire un client.
        
        Args:
            client_id: Identifiant du client à retirer
        """
        if client_id in self.connected_clients:
            del self.connected_clients[client_id]
    
    def capture_and_send(self) -> bool:
        """Capture une frame et l'envoie aux clients.
        
        Returns:
            True si succès, False si erreur fatale
        """
        if not self.is_streaming or not self.socket:
            return False
        
        try:
            # Capturer la frame
            frame = self._capture_frame()
            if frame is None:
                return True  # Pas d'erreur fatale, juste pas de frame
            
            # Redimensionner
            frame = imutils.resize(frame, width=DEFAULT_WIDTH)
            
            # Encoder en JPEG
            jpeg_bytes = self._encode_frame(frame)
            if jpeg_bytes is None:
                return True
            
            # Envoyer aux clients
            self._send_to_clients(jpeg_bytes)
            
            # Log périodique
            self._log_stats()
            
            return True
            
        except Exception as e:
            logger.debug(f"Error in capture_and_send: {e}")
            return True
    
    def _capture_frame(self) -> np.ndarray:
        """Capture une frame de l'écran.
        
        Returns:
            Frame en format BGR numpy array, ou None en cas d'erreur
        """
        capture_bbox = self.monitor_manager.get_capture_bbox()
        use_mss = self._mss_context is not None and self.monitor_manager.selected_monitor > 0
        
        try:
            if use_mss:
                return self._capture_with_mss()
            else:
                return self._capture_with_pil(capture_bbox)
        except Exception as e:
            logger.debug(f"Capture failed: {e}")
            # Fallback vers PIL
            return self._capture_with_pil(capture_bbox)
    
    def _capture_with_mss(self) -> np.ndarray:
        """Capture avec mss.
        
        Returns:
            Frame en format BGR
        """
        monitor = self._mss_context.monitors[self.monitor_manager.selected_monitor]
        sct_img = self._mss_context.grab(monitor)
        frame = np.array(sct_img, dtype=np.uint8)
        # mss retourne BGRA, convertir en BGR
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    
    def _capture_with_pil(self, bbox: tuple = None) -> np.ndarray:
        """Capture avec PIL/pyscreenshot.
        
        Args:
            bbox: Bounding box optionnelle (left, top, right, bottom)
            
        Returns:
            Frame en format BGR
        """
        if bbox:
            img_pil = ImageGrab.grab(bbox=bbox)
        else:
            img_pil = ImageGrab.grab()
        frame = np.array(img_pil, dtype=np.uint8)
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    
    def _encode_frame(self, frame: np.ndarray) -> bytes:
        """Encode une frame en JPEG.
        
        Args:
            frame: Frame BGR à encoder
            
        Returns:
            Bytes JPEG, ou None en cas d'erreur
        """
        encode_params = [
            cv2.IMWRITE_JPEG_QUALITY, int(JPEG_QUALITY),
            cv2.IMWRITE_JPEG_OPTIMIZE, 1,
            cv2.IMWRITE_JPEG_PROGRESSIVE, 1,
        ]
        
        encoded, buffer = cv2.imencode('.jpg', frame, encode_params)
        if not encoded:
            logger.debug("cv2.imencode returned False")
            return None
        
        jpeg_bytes = buffer.tobytes()
        
        # Si trop gros pour UDP, réduire progressivement
        if len(jpeg_bytes) > MAX_UDP_PAYLOAD:
            jpeg_bytes = self._downscale_to_fit(frame, encode_params)
        
        return jpeg_bytes
    
    def _downscale_to_fit(self, frame: np.ndarray, encode_params: list) -> bytes:
        """Réduit la taille de la frame jusqu'à tenir dans UDP.
        
        Args:
            frame: Frame originale
            encode_params: Paramètres d'encodage JPEG
            
        Returns:
            Bytes JPEG de taille réduite
        """
        cur_w = frame.shape[1]
        jpeg_bytes = None
        
        while cur_w > 200:
            cur_w = max(200, int(cur_w * 0.9))
            try:
                smaller = imutils.resize(frame, width=cur_w)
                encoded, buffer = cv2.imencode('.jpg', smaller, encode_params)
                if not encoded:
                    break
                jpeg_bytes = buffer.tobytes()
                
                if len(jpeg_bytes) <= MAX_UDP_PAYLOAD:
                    logger.debug(f"Downscaled to {cur_w} => {len(jpeg_bytes)} bytes")
                    break
            except Exception as e:
                logger.debug(f"Downscale error: {e}")
                break
        
        return jpeg_bytes
    
    def _send_to_clients(self, jpeg_bytes: bytes):
        """Envoie les données à tous les clients connectés.
        
        Args:
            jpeg_bytes: Données JPEG à envoyer
        """
        for client_id, client_addr in list(self.connected_clients.items()):
            if not self.is_streaming or not self.socket:
                break
            
            try:
                self.socket.sendto(jpeg_bytes, client_addr)
                self.frame_count += 1
                
                if self.frame_count % 100 == 0:
                    logger.info(f"Sent {self.frame_count} frames (latest to {client_addr})")
                    
            except OSError as e:
                logger.exception(f"Error sending to {client_addr}: {e}")
                win_err = getattr(e, 'winerror', None)
                if win_err == 10038:
                    logger.error("Socket invalid (10038) — stopping video streamer")
                    self.is_streaming = False
                    break
            except Exception as e:
                logger.exception(f"Unexpected error sending to {client_addr}: {e}")
    
    def _log_stats(self):
        """Log les statistiques périodiques."""
        if time.time() - self.last_log_time > 10:
            logger.info(
                f"Video streamer stats: frames_sent={self.frame_count}, "
                f"clients={len(self.connected_clients)}"
            )
            self.last_log_time = time.time()
