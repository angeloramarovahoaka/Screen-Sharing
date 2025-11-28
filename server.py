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
SERVER_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)

# REMPLACEZ l'IP ci-dessous par l'adresse IP de l'ordinateur qui FAIT le partage d'écran
HOST_IP = "192.168.11.122" 
print("HOST IP:", HOST_IP)
PORT = 9999
socket_address = (HOST_IP, PORT)

try:
    SERVER_SOCKET.bind(socket_address)
    print("Listening at:", socket_address)
except OSError as e:
    print(f"ERROR: Could not bind to socket {socket_address}. Check if the IP is correct and if the port is free.")
    print(f"System error: {e}")
    exit()

# --- 2. Configuration de l'Optimisation ---
# Largeur des trames envoyées (Optimisation de Vitesse)
WIDTH = 320 
# Qualité JPEG (0-100) (Optimisation de Vitesse)
JPEG_QUALITY = 60 

# --- 3. Attente de la première connexion du client ---
addr = None
print("Waiting for client request to start streaming...")
while addr is None:
    try:
        # Le serveur attend qu'un client lui envoie un message pour connaître son adresse (addr)
        msg, addr = SERVER_SOCKET.recvfrom(BUFFER_SIZE)
        print(f"Received request from: {addr}. Starting screen sharing...")
        # Ligne de vérification optionnelle: print(f"Initial Message: {msg.decode()}")
        break
    except KeyboardInterrupt:
        print("\nServer shutting down.")
        SERVER_SOCKET.close()
        exit()
    except Exception:
        # Attendre un peu avant de réessayer si rien n'est reçu
        time.sleep(0.1)


# --- 4. Boucle de Partage d'Écran ---
while True:
    try:
        # A. Capture de l'écran avec pyscreenshot
        # Utilisation de 'scrot' comme backend pour une meilleure performance sur Linux (s'il est installé)
        # Sinon, 'grab()' utilisera le backend par défaut.
        img_pil = ImageGrab.grab()

        # B. Conversion de PIL Image à NumPy Array (BGR pour OpenCV)
        frame = np.array(img_pil, dtype=np.uint8)
        # Pillow capture en RGB. Conversion nécessaire en BGR pour OpenCV.
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # C. Traitement (Redimensionnement pour l'optimisation)
        frame = imutils.resize(frame, width=WIDTH)
        
        # D. Compression et Encodage (Réduction de la qualité JPEG pour l'optimisation)
        encoded, buffer = cv2.imencode(
            '.jpg', 
            frame, 
            [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        )
        # Encoder en Base64 pour l'envoi via UDP
        b64encoded = base64.b64encode(buffer)
        
        # E. Envoi des données
        SERVER_SOCKET.sendto(b64encoded, addr)
        
        # F. Affichage local (Optionnel)
        cv2.imshow(f"Sharing Screen to {addr[0]}:{addr[1]}", frame)
        
        # G. Gestion de l'arrêt
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    except KeyboardInterrupt:
        print("\nStreaming interrupted by user.")
        break
    except Exception as e:
        # Afficher l'erreur pour le débogage, mais ne pas interrompre le flux immédiatement
        # (souvent des erreurs transitoires)
        print(f"An error occurred during streaming: {e}")
        time.sleep(0.01) # Petite pause pour éviter de surcharger en cas d'erreur constante


# --- 5. Nettoyage et Fin du Programme ---
print("Closing socket and cleaning up...")
SERVER_SOCKET.close()
cv2.destroyAllWindows()