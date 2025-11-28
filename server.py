import cv2
import imutils
import socket
import numpy as np
import time
import base64
import pyscreenshot as ImageGrab # Importation de pyscreenshot
from PIL import Image # Nécessaire pour les manipulations d'image

# --- Configuration du Socket ---
BUFFER_SIZE = 65536
SERVER_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
SERVER_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)

# REMPLACEZ l'IP ci-dessous par l'adresse IP de l'ordinateur qui FAIT le partage d'écran
HOST_IP = "192.168.11.122" 
print("HOST IP:", HOST_IP)
PORT = 9999
socket_address = (HOST_IP, PORT)
SERVER_SOCKET.bind(socket_address)
print("Listening at:", socket_address)

# --- Configuration de la Capture d'Écran ---
# Définir la largeur de la trame redimensionnée pour l'envoi
WIDTH = 400 

# --- Attente de la première connexion du client ---
addr = None
print("Waiting for client request...")
while addr is None:
    try:
        # Le serveur attend qu'un client lui envoie un message pour connaître son adresse (addr)
        msg, addr = SERVER_SOCKET.recvfrom(BUFFER_SIZE)
        print(f"Received request from: {addr}. Starting screen sharing...")
        print(f"Initial Message: {msg.decode()}")
    except KeyboardInterrupt:
        print("\nServer shutting down.")
        SERVER_SOCKET.close()
        exit()
    except Exception as e:
        # S'assurer qu'il n'y a pas d'erreur de socket bloquant si vous testez rapidement
        time.sleep(0.1)


# --- Boucle de Partage d'Écran ---
while True:
    try:
        # 1. Capture de l'écran avec pyscreenshot
        # 'grab()' prend une capture de l'écran entier et retourne un objet PIL Image.
        img_pil = ImageGrab.grab() 

        # 2. Conversion de PIL Image à NumPy Array (BGR pour OpenCV)
        # Convertir l'image PIL en un tableau NumPy
        frame = np.array(img_pil, dtype=np.uint8)
        
        # Pillow capture en RGB (Rouge, Vert, Bleu). OpenCV attend du BGR.
        # Nous devons donc convertir l'espace couleur pour OpenCV.
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # 3. Traitement
        # Redimensionner l'image pour un meilleur débit
        frame = imutils.resize(frame, width=WIDTH)
        
        # 4. Compression et Encodage
        # Compresser en JPEG avec une qualité de 80%
        encoded, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        # Encoder en Base64 pour l'envoi via UDP
        b64encoded = base64.b64encode(buffer)
        
        # 5. Envoi
        SERVER_SOCKET.sendto(b64encoded, addr)
        
        # 6. Affichage local (Optionnel)
        cv2.imshow(f"Sharing Screen to {addr[0]}:{addr[1]}", frame)
        
        # 7. Gestion de l'arrêt
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    except KeyboardInterrupt:
        print("\nServer shutting down.")
        break
    except Exception as e:
        print(f"An error occurred during streaming: {e}")
        time.sleep(0.1)


# --- Nettoyage ---
SERVER_SOCKET.close()
cv2.destroyAllWindows()