import cv2
import imutils
import socket
import numpy as np
import time
import base64
import pyscreenshot as ImageGrab 
import threading
import json
from pynput.mouse import Controller as MouseController, Button 
from pynput.keyboard import Controller as KeyboardController, Key 

# --- CONFIGURATION RÉSEAU ---
# ... (Configuration réseau inchangée) ...
VIDEO_PORT = 9999
COMMAND_PORT = 9998
BUFFER_SIZE = 65536
HOST_IP_CLIENT = "192.168.11.42" 
ADDR_CLIENT_VIDEO = (HOST_IP_CLIENT, VIDEO_PORT)

# --- CONFIGURATION OPTIMISATION ET TRAME ---
WIDTH = 640 
JPEG_QUALITY = 70 

# --- OUTILS DE SIMULATION ---
mouse = MouseController()
keyboard = KeyboardController()
# >>> VÉRIFIER VOTRE RÉSOLUTION D'ÉCRAN RÉELLE (IMPORTANT) <<<
SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1080 

# Dictionnaire de traduction des chaînes de boutons en objets pynput.Button
BUTTON_MAP = {
    "left": Button.left,
    "right": Button.right,
    "middle": Button.middle
}

# Fonction pour obtenir l'objet touche pynput (caractère ou touche spéciale)
def get_pynput_key(key_name):
    """Convertit une chaîne (ex: 'ctrl_l' ou 'a') en objet pynput Key ou caractère."""
    try:
        # 1. Essayer de mapper les touches spéciales (Ex: 'enter', 'shift', 'ctrl_l', 'cmd')
        return getattr(Key, key_name)
    except AttributeError:
        # 2. Si ce n'est pas une touche spéciale, la renvoyer comme un caractère simple (Ex: 'a', '1', 'C')
        return key_name 

# --- THREAD DE RÉCEPTION ET D'EXÉCUTION DES COMMANDES (TCP) ---

def command_listener():
    
    COMMAND_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        COMMAND_SOCKET.bind(('0.0.0.0', COMMAND_PORT)) 
        COMMAND_SOCKET.listen(1)
        print(f"📡 Écoute de commandes démarrée sur le port {COMMAND_PORT} (TCP).")
    except Exception as e:
        print(f"❌ ERREUR: Impossible de démarrer l'écoute des commandes: {e}")
        return

    while True:
        try:
            conn, addr = COMMAND_SOCKET.accept()
            print(f"Connexion de commande établie avec {addr}")
            
            while True:
                data = conn.recv(1024)
                if not data:
                    break 
                    
                command_str = data.decode('utf-8')
                
                for command_json in command_str.split('\n'):
                    if not command_json:
                        continue
                        
                    try:
                        command = json.loads(command_json) 
                        cmd_type = command.get('type')
                        
                        if cmd_type == 'mouse':
                            action = command['action']
                            
                            # Mise à l'échelle des coordonnées et déplacement du curseur
                            if action != 'scroll':
                                x = int(command['x'] * SCREEN_WIDTH)
                                y = int(command['y'] * SCREEN_HEIGHT)
                                mouse.position = (x, y) 

                            if action == 'move':
                                continue 
                                
                            elif action == 'scroll':
                                # Gestion du défilement
                                mouse.scroll(command.get('dx', 0), command.get('dy', 0))
                                
                            else: # 'press' ou 'release'
                                button_str = command.get('button')
                                pynput_button = BUTTON_MAP.get(button_str)

                                if pynput_button:
                                    if action == 'press':
                                        mouse.press(pynput_button)
                                    elif action == 'release':
                                        mouse.release(pynput_button)
                                    
                        elif cmd_type == 'key':
                            action = command['action']
                            key_name = command['key'] # Nom de la touche (ex: 'ctrl_l', 'a')
                            
                            pynput_key = get_pynput_key(key_name)
                            
                            if pynput_key:
                                if action == 'press':
                                    keyboard.press(pynput_key)
                                elif action == 'release':
                                    keyboard.release(pynput_key)
                                
                    except json.JSONDecodeError:
                        pass
                    except Exception as e:
                        # Gérer les touches non reconnues par pynput (peut arriver avec certaines combinaisons OS)
                        # print(f"⚠️ Erreur lors de l'exécution de la commande: {e}") 
                        pass
                        
            conn.close()
            print(f"Connexion de commande avec {addr} terminée.")

        except Exception:
            time.sleep(1)

# --- THREAD PRINCIPAL (STREAMING VIDÉO - UDP) ---
# ... (Fonction video_streamer inchangée) ...
def video_streamer():
    
    VIDEO_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("▶️ Le thread de streaming vidéo est actif et commence à envoyer...")

    while True:
        try:
            img_pil = ImageGrab.grab()
            frame = np.array(img_pil, dtype=np.uint8)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame = imutils.resize(frame, width=WIDTH)
            
            encoded, buffer = cv2.imencode(
                '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
            )
            b64encoded = base64.b64encode(buffer)
            
            VIDEO_SOCKET.sendto(b64encoded, ADDR_CLIENT_VIDEO)
            
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(0.01)

    print("Arrêt du streaming vidéo.")
    VIDEO_SOCKET.close()


# --- DÉMARRAGE DES THREADS ---

if __name__ == '__main__':
    command_thread = threading.Thread(target=command_listener)
    command_thread.daemon = True 
    command_thread.start()
    
    video_streamer()
    
    print("Serveur arrêté.")