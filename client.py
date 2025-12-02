import cv2
import socket
import numpy as np
import base64
import time
import json
import threading 

# --- CONFIGURATION RÉSEAU ---
VIDEO_PORT = 9999
COMMAND_PORT = 9998
BUFFER_SIZE = 65536

# Remplacer par l'IP réelle du SERVEUR
HOST_IP_SERVER = "192.168.11.24" 

# Adresse UDP pour la vidéo
ADDR_SERVER_VIDEO = (HOST_IP_SERVER, VIDEO_PORT)

# --- SOCKET VIDÉO (UDP) ---
CLIENT_VIDEO_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
CLIENT_VIDEO_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
CLIENT_VIDEO_SOCKET.settimeout(0.01) # Non-bloquant

# >>> CORRECTION : Lier le socket UDP du client pour la réception <<<
try:
    CLIENT_VIDEO_SOCKET.bind(('0.0.0.0', VIDEO_PORT))
    print(f"✅ Socket vidéo lié à 0.0.0.0:{VIDEO_PORT} pour la réception.")
except Exception as e:
    print(f"❌ ERREUR: Impossible de lier le socket vidéo: {e}. Vérifiez si le port est libre.")
    # Le programme peut continuer mais la réception est compromise

# --- SOCKET DE COMMANDE (TCP) ---
try:
    CLIENT_COMMAND_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    CLIENT_COMMAND_SOCKET.connect((HOST_IP_SERVER, COMMAND_PORT))
    print(f"📡 Connexion TCP établie avec le serveur {HOST_IP_SERVER}:{COMMAND_PORT}.")
except Exception as e:
    print(f"❌ ERREUR: Impossible de se connecter au socket de commande TCP: {e}")
    CLIENT_COMMAND_SOCKET = None 

# --- CONFIGURATION AFFICHAGE ---
DEFAULT_WIDTH = 640 
DEFAULT_HEIGHT = int(DEFAULT_WIDTH * 9 / 16) 
latest_frame = None

# ... (Les fonctions send_command et mouse_callback restent inchangées) ...

def send_command(command_dict):
    if CLIENT_COMMAND_SOCKET is None:
        return
    try:
        message = json.dumps(command_dict) + '\n'
        CLIENT_COMMAND_SOCKET.sendall(message.encode('utf-8'))
    except Exception:
        pass
        
def mouse_callback(event, x, y, flags, param):
    if DEFAULT_WIDTH == 0 or DEFAULT_HEIGHT == 0:
        return
    normalized_x = x / DEFAULT_WIDTH
    normalized_y = y / DEFAULT_HEIGHT
    
    if event == cv2.EVENT_LBUTTONDOWN:
        command = {
            'type': 'mouse',
            'action': 'click',
            'button': 'left',
            'x': normalized_x,
            'y': normalized_y
        }
        send_command(command)

# --- BOUCLE PRINCIPALE (Réception Vidéo) ---

WINDOW_NAME = f"REMOTE DESKTOP - {HOST_IP_SERVER}"
cv2.namedWindow(WINDOW_NAME)
cv2.setMouseCallback(WINDOW_NAME, mouse_callback)

try:
    # Envoyer un message initial (UDP)
    CLIENT_VIDEO_SOCKET.sendto(b'START', ADDR_SERVER_VIDEO) 
except Exception as e:
    print(f"⚠️ ERREUR: Impossible d'envoyer le message de démarrage UDP: {e}")

print("Démarrage de la boucle de réception vidéo...")
while True:
    try:
        packet, addr = CLIENT_VIDEO_SOCKET.recvfrom(BUFFER_SIZE)
        
        # B. Décodage de la trame
        data = base64.b64decode(packet)
        npdata = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(npdata, 1)
        
        if frame is not None:
            latest_frame = frame
            # print(f"Trame reçue et décodée (Taille: {frame.shape})") # Diagnostic
        else:
            # print("⚠️ Paquet reçu mais décodage échoué (frame is None)") # Diagnostic
            pass
        
    except socket.timeout:
        # Le client n'a rien reçu, il continue d'afficher la dernière trame
        pass 
        
    except KeyboardInterrupt:
        print("Arrêt demandé par l'utilisateur.")
        break
        
    except Exception as e:
        # print(f"⚠️ Erreur critique dans la boucle de réception: {e}")
        time.sleep(0.001)

    # --- AFFICHAGE ---
    if latest_frame is not None:
        try:
            frame_resized = cv2.resize(latest_frame, (DEFAULT_WIDTH, DEFAULT_HEIGHT))
            cv2.imshow(WINDOW_NAME, frame_resized)
        except Exception as e:
            print(f"❌ ERREUR: Échec du redimensionnement/affichage: {e}")
            latest_frame = None 
    else:
        # Afficher le cadre noir
        black_frame = np.zeros((DEFAULT_HEIGHT, DEFAULT_WIDTH, 3), dtype=np.uint8)
        cv2.putText(black_frame, "ATTENTE DE FLUX VIDEO...", (50, DEFAULT_HEIGHT // 2), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow(WINDOW_NAME, black_frame)
        
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
            
# --- NETTOYAGE ET FIN ---
print("Fermeture des sockets et nettoyage...")
CLIENT_VIDEO_SOCKET.close()
if CLIENT_COMMAND_SOCKET:
    CLIENT_COMMAND_SOCKET.close()
cv2.destroyAllWindows()