# CODE DU SERVEUR B (PC AVEC IP 192.168.11.122) - IDEM QUE PC 21
import cv2
import imutils
import socket
import numpy as np
import time
import base64
import pyscreenshot as ImageGrab 
from PIL import Image 

# --- 1. Configuration du Réseau et du Socket ---
BUFFER_SIZE = 65536
SERVER_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# REMPLACEZ l'IP ci-dessous par l'adresse IP de l'ordinateur qui FAIT l'AFFICHAGE CENTRAL
HOST_IP_CLIENT = "192.168.11.14" # <--- REMPLACER PAR L'IP RÉELLE DU CLIENT
print(f"✅ Serveur PC 122. Envoi vers: {HOST_IP_CLIENT}")
PORT = 9999
addr_client = (HOST_IP_CLIENT, PORT)

# --- 2. Configuration de l'Optimisation ---
WIDTH = 320 
JPEG_QUALITY = 60 

# --- 3. Boucle de Partage d'Écran ---
print(f"Démarrage du streaming vers {HOST_IP_CLIENT}...")
while True:
    try:
        # A. Capture de l'écran 
        img_pil = ImageGrab.grab()

        # B. Conversion PIL -> NumPy -> BGR
        frame = np.array(img_pil, dtype=np.uint8)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # C. Redimensionnement
        frame = imutils.resize(frame, width=WIDTH)
        
        # D. Compression et Encodage
        encoded, buffer = cv2.imencode(
            '.jpg', 
            frame, 
            [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        )
        b64encoded = base64.b64encode(buffer)
        
        # E. Envoi des données
        SERVER_SOCKET.sendto(b64encoded, addr_client)
        
        # F. Gestion de l'arrêt
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    except KeyboardInterrupt:
        print("\nStreaming interrompu par l'utilisateur.")
        break
    except Exception as e:
        # print(f"⚠️ Erreur durant le streaming: {e}")
        time.sleep(0.01)

# --- 4. Nettoyage et Fin du Programme ---
print("Fermeture du socket et nettoyage...")
SERVER_SOCKET.close()
cv2.destroyAllWindows()