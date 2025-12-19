"""
Logging configuration for client modules.
"""
import logging
import os
from logging.handlers import RotatingFileHandler, DatagramHandler

LOG_LEVEL = os.getenv("SS_LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("screenshare.client")
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    try:
        logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        file_path = os.path.join(logs_dir, "client.log")
        fh = RotatingFileHandler(file_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception:
        pass
    collector = os.getenv("SS_LOG_COLLECTOR")
    if collector:
        try:
            host, port = collector.split(":")
            dh = DatagramHandler(host, int(port))
            logger.addHandler(dh)
        except Exception:
            pass
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
