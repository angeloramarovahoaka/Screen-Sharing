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

# >>> ASSUREZ-VOUS QUE C'EST LA BONNE IP DU SERVEUR <<<
HOST_IP_SERVER = "192.168.11.24" 

ADDR_SERVER_VIDEO = (HOST_IP_SERVER, VIDEO_PORT)

# --- SOCKETS ---
CLIENT_VIDEO_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
CLIENT_VIDEO_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
CLIENT_VIDEO_SOCKET.settimeout(0.01)

try:
    CLIENT_VIDEO_SOCKET.bind(('0.0.0.0', VIDEO_PORT))
    print(f"✅ Socket vidéo lié à 0.0.0.0:{VIDEO_PORT} pour la réception.")
except Exception as e:
    print(f"❌ ERREUR: Impossible de lier le socket vidéo: {e}. Vérifiez si le port est libre.")

CLIENT_COMMAND_SOCKET = None 
try:
    CLIENT_COMMAND_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    CLIENT_COMMAND_SOCKET.connect((HOST_IP_SERVER, COMMAND_PORT))
    print(f"📡 Connexion TCP établie avec le serveur {HOST_IP_SERVER}:{COMMAND_PORT}.")
except Exception as e:
    print(f"❌ ERREUR: Impossible de se connecter au socket de commande TCP: {e}")

# --- CONFIGURATION AFFICHAGE ---
DEFAULT_WIDTH = 640 
DEFAULT_HEIGHT = int(DEFAULT_WIDTH * 9 / 16) 
latest_frame = None

# --- GESTION DE L'ENVOI DE COMMANDES ---

def send_command(command_dict):
    """Sérialise le dictionnaire de commande en JSON et l'envoie via TCP."""
    if CLIENT_COMMAND_SOCKET is None:
        return
    try:
        # Ajout d'un saut de ligne comme délimiteur pour gérer les commandes en rafale
        message = json.dumps(command_dict) + '\n' 
        CLIENT_COMMAND_SOCKET.sendall(message.encode('utf-8'))
    except Exception:
        # Gérer les déconnexions silencieuses ici
        pass
        
# Mappage des événements OpenCV vers les actions et boutons pynput
# Note: pynput gère le mouvement et l'action press/release sur le même point
MOUSE_EVENT_MAP = {
    cv2.EVENT_LBUTTONDOWN: ('press', 'left'),
    cv2.EVENT_LBUTTONUP:   ('release', 'left'),
    cv2.EVENT_RBUTTONDOWN: ('press', 'right'),
    cv2.EVENT_RBUTTONUP:   ('release', 'right'),
    cv2.EVENT_MBUTTONDOWN: ('press', 'middle'),
    cv2.EVENT_MBUTTONUP:   ('release', 'middle'),
}
current_mouse_pos = (0.0, 0.0)

def mouse_callback(event, x, y, flags, param):
    """Traduit les événements de souris de la fenêtre OpenCV en commandes."""
    global current_mouse_pos
    
    if DEFAULT_WIDTH == 0 or DEFAULT_HEIGHT == 0:
        return
        
    normalized_x = x / DEFAULT_WIDTH
    normalized_y = y / DEFAULT_HEIGHT
    current_mouse_pos = (normalized_x, normalized_y) # Mise à jour de la position pour le mouvement
    
    # Gestion des clics et relâchements (Press/Release)
    if event in MOUSE_EVENT_MAP:
        action, button = MOUSE_EVENT_MAP[event]
        
        command = {
            'type': 'mouse',
            'action': action, # 'press' ou 'release'
            'button': button,
            'x': normalized_x,
            'y': normalized_y
        }
        send_command(command)
        
    # Gestion du mouvement (envoi continu si un bouton est maintenu ou s'il y a un grand delta)
    elif event == cv2.EVENT_MOUSEMOVE:
        # Envoi d'un événement de "mouvement" pour mettre à jour la position du curseur
        # sans nécessiter de clic.
        command = {
            'type': 'mouse',
            'action': 'move',
            'x': normalized_x,
            'y': normalized_y
        }
        send_command(command)
        
# --- BOUCLE PRINCIPALE (Réception Vidéo et Gestion Clavier) ---

WINDOW_NAME = f"REMOTE DESKTOP - {HOST_IP_SERVER}"
cv2.namedWindow(WINDOW_NAME)
cv2.setMouseCallback(WINDOW_NAME, mouse_callback)

try:
    CLIENT_VIDEO_SOCKET.sendto(b'START', ADDR_SERVER_VIDEO) 
except Exception:
    pass

print("Démarrage de la boucle de réception vidéo et commandes...")
while True:
    try:
        packet, addr = CLIENT_VIDEO_SOCKET.recvfrom(BUFFER_SIZE)
        
        data = base64.b64decode(packet)
        npdata = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(npdata, 1)
        
        if frame is not None:
            latest_frame = frame
        
    except socket.timeout:
        pass 
        
    except KeyboardInterrupt:
        break
        
    except Exception:
        time.sleep(0.001)

    # --- GESTION DU CLAVIER (cv2.waitKey) ---
    key_code = cv2.waitKey(1) & 0xFF
    
    if key_code == ord('q'):
        break # Quitter
    
    # Envoyer la frappe clavier au serveur
    elif key_code != 255 and key_code > 0: # 255 est le code "pas de touche pressée"
        try:
            # Convertir le code ASCII en caractère (ex: 97 -> 'a')
            char = chr(key_code) 
            
            # Envoyer la frappe pressée et relâchée immédiatement
            # Nous envoyons l'action 'press' et 'release' séparément pour plus de fiabilité
            send_command({'type': 'key', 'action': 'press', 'key': char})
            send_command({'type': 'key', 'action': 'release', 'key': char})
            
        except ValueError:
             # Gérer les codes non-ASCII ou spéciaux si nécessaire
             pass 

    # --- AFFICHAGE ---
    if latest_frame is not None:
        try:
            frame_resized = cv2.resize(latest_frame, (DEFAULT_WIDTH, DEFAULT_HEIGHT))
            cv2.imshow(WINDOW_NAME, frame_resized)
        except Exception:
            latest_frame = None 
    else:
        black_frame = np.zeros((DEFAULT_HEIGHT, DEFAULT_WIDTH, 3), dtype=np.uint8)
        cv2.putText(black_frame, "ATTENTE DE FLUX VIDEO...", (50, DEFAULT_HEIGHT // 2), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow(WINDOW_NAME, black_frame)
            
# --- NETTOYAGE ET FIN ---
print("Fermeture des sockets et nettoyage...")
CLIENT_VIDEO_SOCKET.close()
if CLIENT_COMMAND_SOCKET:
    CLIENT_COMMAND_SOCKET.close()
cv2.destroyAllWindows()