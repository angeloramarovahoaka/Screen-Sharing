import cv2
import imutils
import socket
import numpy as np
import time
import base64
import pyscreenshot as ImageGrab 
import threading
import json

# --- IMPORTS CORRIGÉS pour la simulation d'entrée ---
from pynput.mouse import Controller as MouseController, Button 
from pynput.keyboard import Controller as KeyboardController

# --- CONFIGURATION RÉSEAU ---
VIDEO_PORT = 9999
COMMAND_PORT = 9998
BUFFER_SIZE = 65536
# >>> REMPLACER PAR L'IP RÉELLE DU CLIENT <<<
HOST_IP_CLIENT = "192.168.11.24" 
ADDR_CLIENT_VIDEO = (HOST_IP_CLIENT, VIDEO_PORT)

# --- CONFIGURATION OPTIMISATION ET TRAME ---
# Taille de la trame envoyée (doit correspondre à celle attendue par le client)
WIDTH = 640 
JPEG_QUALITY = 70 

# --- OUTILS DE SIMULATION ---
mouse = MouseController()
keyboard = KeyboardController()
# >>> VÉRIFIER VOTRE RÉSOLUTION D'ÉCRAN RÉELLE <<<
SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1080 

# Dictionnaire de traduction des chaînes de boutons en objets pynput.Button
BUTTON_MAP = {
    "left": Button.left,
    "right": Button.right,
    "middle": Button.middle
}

# --- THREAD DE RÉCEPTION ET D'EXÉCUTION DES COMMANDES (TCP) ---

def command_listener():
    """Écoute les commandes du client sur le port TCP 9998."""
    
    COMMAND_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        # Écoute sur toutes les interfaces
        COMMAND_SOCKET.bind(('0.0.0.0', COMMAND_PORT)) 
        COMMAND_SOCKET.listen(1)
        print(f"📡 Écoute de commandes démarrée sur le port {COMMAND_PORT} (TCP).")
    except Exception as e:
        print(f"❌ ERREUR: Impossible de démarrer l'écoute des commandes: {e}")
        return

    while True:
        try:
            # Attend la connexion du client
            conn, addr = COMMAND_SOCKET.accept()
            print(f"Connexion de commande établie avec {addr}")
            
            # Boucle de réception des commandes après connexion
            while True:
                data = conn.recv(1024)
                if not data:
                    break 
                    
                command_str = data.decode('utf-8')
                
                # Le client envoie une chaîne JSON avec un délimiteur '\n'
                for command_json in command_str.split('\n'):
                    if not command_json:
                        continue
                        
                    try:
                        command = json.loads(command_json) 
                        cmd_type = command.get('type')
                        
                        if cmd_type == 'mouse':
                            action = command['action']
                            
                            # 1. Mise à l'échelle des coordonnées normalisées (0.0 à 1.0)
                            x = int(command['x'] * SCREEN_WIDTH)
                            y = int(command['y'] * SCREEN_HEIGHT)
                            
                            # Déplacement du curseur (toujours en premier)
                            mouse.position = (x, y)
                            
                            # 2. Exécution du clic/relâchement/pression
                            button_str = command.get('button')
                            pynput_button = BUTTON_MAP.get(button_str)

                            if action == 'click' and pynput_button:
                                mouse.click(pynput_button) 
                            elif action == 'press' and pynput_button:
                                mouse.press(pynput_button)
                            elif action == 'release' and pynput_button:
                                mouse.release(pynput_button)
                            elif action == 'scroll':
                                # Pour l'implémentation future du défilement
                                mouse.scroll(command.get('dx', 0), command.get('dy', 0))
                                
                        elif cmd_type == 'key':
                            # Implémentation future des frappes clavier
                            action = command['action']
                            key = command['key']
                            
                            if action == 'press':
                                keyboard.press(key)
                            elif action == 'release':
                                keyboard.release(key)
                        print(f"✅ Commande exécutée: {command}")
                                
                    except json.JSONDecodeError:
                        print(f"⚠️ Erreur de décodage JSON: {command_json}")
                    except Exception as e:
                        print(f"⚠️ Erreur lors de l'exécution de la commande: {e}")
                        
            conn.close()
            print(f"Connexion de commande avec {addr} terminée.")

        except Exception:
            time.sleep(1)


# --- THREAD PRINCIPAL (STREAMING VIDÉO - UDP) ---

def video_streamer():
    """Capture l'écran et envoie la trame au client via UDP."""
    
    VIDEO_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    while True:
        try:
            # A. Capture de l'écran 
            img_pil = ImageGrab.grab()

            # B. Conversion et Traitement 
            frame = np.array(img_pil, dtype=np.uint8)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame = imutils.resize(frame, width=WIDTH)
            
            # C. Compression et Encodage
            encoded, buffer = cv2.imencode(
                '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
            )
            b64encoded = base64.b64encode(buffer)
            
            # D. Envoi des données (UDP)
            VIDEO_SOCKET.sendto(b64encoded, ADDR_CLIENT_VIDEO)
            print(f"Trame envoyée à {ADDR_CLIENT_VIDEO}")
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(0.01)

    print("Arrêt du streaming vidéo.")
    VIDEO_SOCKET.close()


# --- DÉMARRAGE DES THREADS ---

if __name__ == '__main__':
    # Démarrer le thread d'écoute des commandes
    command_thread = threading.Thread(target=command_listener)
    command_thread.daemon = True 
    command_thread.start()
    
    # Démarrer le thread de streaming vidéo (principal)
    video_streamer()
    
    print("Serveur arrêté.")