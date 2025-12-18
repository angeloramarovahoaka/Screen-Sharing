"""
Module Serveur - Partage d'écran et réception des commandes

Ce module est un point d'entrée de rétrocompatibilité.
La logique est maintenant dans le sous-module `app.server`.
"""
import logging
import os
from logging.handlers import RotatingFileHandler, DatagramHandler

# Réexporter la classe ScreenServer depuis le module refactorisé
from .server import ScreenServer

# --- Logging configuration (gardé pour rétrocompatibilité) ---
LOG_LEVEL = os.getenv("SS_LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("screenshare.server")
if not logger.handlers:
    # Console handler
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Rotating handler (logs/server.log)
    try:
        logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        file_path = os.path.join(logs_dir, "server.log")
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

# Exposer ScreenServer au niveau du module pour rétrocompatibilité
__all__ = ['ScreenServer']