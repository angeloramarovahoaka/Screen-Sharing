import cv2
import socket
import numpy as np
import base64
import time
import json
from pynput import keyboard 
from pynput import mouse # AJOUTÉ

# --- CONFIGURATION RÉSEAU ---
VIDEO_PORT = 9999
COMMAND_PORT = 9998
BUFFER_SIZE = 65536
HOST_IP_SERVER = "192.168.11.19" 
ADDR_SERVER_VIDEO = (HOST_IP_SERVER, VIDEO_PORT)

# --- SOCKETS ---
CLIENT_VIDEO_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
CLIENT_VIDEO_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
CLIENT_VIDEO_SOCKET.settimeout(0.01)

try:
    CLIENT_VIDEO_SOCKET.bind(('0.0.0.0', VIDEO_PORT))
    print(f"✅ Socket vidéo lié à 0.0.0.0:{VIDEO_PORT} pour la réception.")
except Exception:
    pass

CLIENT_COMMAND_SOCKET = None 
try:
    CLIENT_COMMAND_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    CLIENT_COMMAND_SOCKET.connect((HOST_IP_SERVER, COMMAND_PORT))
    print(f"📡 Connexion TCP établie avec le serveur {HOST_IP_SERVER}:{COMMAND_PORT}.")
except Exception:
    pass

# --- CONFIGURATION AFFICHAGE ---
DEFAULT_WIDTH = 640 
DEFAULT_HEIGHT = int(DEFAULT_WIDTH * 9 / 16) 
latest_frame = None
WINDOW_NAME = f"REMOTE DESKTOP - {HOST_IP_SERVER}"

# --- GESTION DE L'ENVOI DE COMMANDES ---

def send_command(command_dict):
    if CLIENT_COMMAND_SOCKET is None:
        return
    try:
        message = json.dumps(command_dict) + '\n' 
        CLIENT_COMMAND_SOCKET.sendall(message.encode('utf-8'))
    except Exception:
        pass
        
# --- GESTION DES COMMANDES CLAVIER (pynput listener) ---

def get_key_name(key):
    if hasattr(key, 'char') and key.char is not None:
        return key.char
    elif isinstance(key, keyboard.Key):
        return str(key).split('.')[-1]
    return None

def on_press(key):
    key_name = get_key_name(key)
    if key_name:
        send_command({'type': 'key', 'action': 'press', 'key': key_name})

def on_release(key):
    key_name = get_key_name(key)
    if key_name == 'q':
        return
    if key_name:
        send_command({'type': 'key', 'action': 'release', 'key': key_name})

keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
keyboard_listener.daemon = True
keyboard_listener.start()


# --- GESTION DU DÉFILEMENT (pynput listener) ---

def on_scroll(x, y, dx, dy):
    """Envoie la commande de défilement de la molette."""
    command = {
        'type': 'mouse',
        'action': 'scroll',
        'dx': dx,
        'dy': dy 
    }
    send_command(command)
    
mouse_listener = mouse.Listener(on_scroll=on_scroll)
mouse_listener.daemon = True
mouse_listener.start()


# --- GESTION DES COMMANDES SOURIS (Callback OpenCV) ---

MOUSE_EVENT_MAP = {
    cv2.EVENT_LBUTTONDOWN: ('press', 'left'),
    cv2.EVENT_LBUTTONUP:   ('release', 'left'),
    cv2.EVENT_RBUTTONDOWN: ('press', 'right'),
    cv2.EVENT_RBUTTONUP:   ('release', 'right'),
    cv2.EVENT_MBUTTONDOWN: ('press', 'middle'),
    cv2.EVENT_MBUTTONUP:   ('release', 'middle'),
}

def mouse_callback(event, x, y, flags, param):
    if DEFAULT_WIDTH == 0 or DEFAULT_HEIGHT == 0:
        return
        
    normalized_x = x / DEFAULT_WIDTH
    normalized_y = y / DEFAULT_HEIGHT
    
    # 1. Gestion des clics/relâchements
    if event in MOUSE_EVENT_MAP:
        action, button = MOUSE_EVENT_MAP[event]
        command = {
            'type': 'mouse',
            'action': action, 
            'button': button,
            'x': normalized_x,
            'y': normalized_y
        }
        send_command(command)
        
    # 2. Gestion du mouvement
    elif event == cv2.EVENT_MOUSEMOVE:
        command = {
            'type': 'mouse',
            'action': 'move',
            'x': normalized_x,
            'y': normalized_y
        }
        send_command(command)
        
    # 3. L'événement EVENT_MOUSEWHEEL est désormais IGNORÉ ici
    #    pour éviter le zoom d'OpenCV. Il est géré par pynput.Listener.


# --- BOUCLE PRINCIPALE (Réception Vidéo et Affichage) ---

# cv2.namedWindow(WINDOW_NAME)
# cv2.setMouseCallback(WINDOW_NAME, mouse_callback)

cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL) # Utiliser WINDOW_NORMAL

# Redimensionner la fenêtre à la taille désirée immédiatement après la création
cv2.resizeWindow(WINDOW_NAME, DEFAULT_WIDTH, DEFAULT_HEIGHT)

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

    # --- AFFICHAGE ET GESTION QUITTER (Q) ---
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
        
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
            
# --- NETTOYAGE ET FIN ---
keyboard_listener.stop() 
mouse_listener.stop() # Arrêter le listener de souris
print("Fermeture des sockets et nettoyage...")
CLIENT_VIDEO_SOCKET.close()
if CLIENT_COMMAND_SOCKET:
    CLIENT_COMMAND_SOCKET.close()
cv2.destroyAllWindows()