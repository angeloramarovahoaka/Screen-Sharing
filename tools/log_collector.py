"""
Simple UDP log collector for LogRecord pickles sent by logging.handlers.DatagramHandler.
Usage:
    python tools/log_collector.py [port]

It listens for UDP packets, tries to unpickle them to LogRecord and logs them locally.
"""
import sys
import socket
import logging
import pickle
import struct
from logging.handlers import DatagramHandler

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9020
BUFFER_SIZE = 65536

# Configure local logger
logger = logging.getLogger('log_collector')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# Also write to a file
fh = logging.FileHandler('collected_logs.log', encoding='utf-8')
fh.setFormatter(formatter)
logger.addHandler(fh)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', PORT))
logger.info(f"UDP log collector listening on 0.0.0.0:{PORT}")

try:
    while True:
        data, addr = sock.recvfrom(BUFFER_SIZE)
        # DatagramHandler typically sends a pickled LogRecord preceded by length for TCP; UDP usually is pickle of LogRecord
        try:
            # Try to unpickle
            record = pickle.loads(data)
            # If it's a LogRecord instance (or a dict), normalize
            if isinstance(record, logging.LogRecord):
                logger.handle(record)
            elif isinstance(record, dict):
                # create a LogRecord
                rec = logging.makeLogRecord(record)
                logger.handle(rec)
            else:
                # print raw
                logger.info(f"{addr} {record}")
        except Exception:
            # fallback: try to decode as utf-8 text
            try:
                text = data.decode('utf-8', errors='replace')
                logger.info(f"{addr} {text}")
            except Exception:
                logger.exception(f"Failed to process packet from {addr}")
except KeyboardInterrupt:
    logger.info('Collector stopped by user')
finally:
    sock.close()
