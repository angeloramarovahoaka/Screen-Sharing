import cv2
import socket
import numpy as np
import base64
import time
import math # Nécessaire pour les calculs de grille

# --- 1. Configuration Globale et Liste des IPs Attentues ---

BUFFER_SIZE = 65536
PORT = 9999
HOST_IP = '0.0.0.0' # Écoute sur toutes les interfaces

# >>> MODIFICATION REQUISE ICI : Liste des adresses IP des serveurs attendus
# Ajoutez simplement les IPs de tous les serveurs ici. 
# Le code ajustera automatiquement la mosaïque.
SOURCES_IPS = [
    "192.168.11.21", 
    "192.168.11.122",
    "192.168.11.33", # Exemple d'un 3ème écran
    "192.168.11.44"  # Exemple d'un 4ème écran
    # Ajoutez autant d'IP que nécessaire
] 

# --- 2. Configuration Socket ---
CLIENT_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
CLIENT_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
CLIENT_SOCKET.settimeout(0.01) # IMPORTANT : Rend le socket non-bloquant

try:
    CLIENT_SOCKET.bind((HOST_IP, PORT))
    print(f"✅ Client démarré. Écoute sur {HOST_IP}:{PORT} pour {len(SOURCES_IPS)} flux...")
except OSError as e:
    print(f"❌ ERREUR: Impossible de lier le socket. {e}")
    exit()

# Dictionnaire pour stocker la dernière trame reçue de chaque source
STREAM_FRAMES = {}
DEFAULT_WIDTH = 320 
DEFAULT_HEIGHT = int(DEFAULT_WIDTH * 9 / 16) 

# --- 3. Fonction d'Assemblage de Mosaïque SCALABLE ---

def build_scalable_mosaic(frames_dict, sources_ips, target_width, default_height):
    """
    Assemble toutes les trames reçues en une seule image mosaïque, 
    en adaptant dynamiquement la grille (N x M).
    """
    
    total_streams = len(sources_ips)
    
    # 1. Déterminer la géométrie de la grille (ex: 4 streams -> 2x2, 6 streams -> 2x3)
    # On calcule le nombre de colonnes pour former une grille quasi-carrée.
    cols = int(math.ceil(math.sqrt(total_streams)))
    rows = int(math.ceil(total_streams / cols))
    
    # Créer le cadre par défaut (placeholder)
    default_frame = np.zeros((default_height, target_width, 3), dtype=np.uint8)
    cv2.putText(default_frame, "EN ATTENTE...", (20, default_height // 2), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    
    current_frames = []
    
    # 2. Préparation et normalisation des trames
    for ip in sources_ips:
        frame = frames_dict.get(ip)
        
        if frame is None:
            # Utiliser le placeholder si aucune trame reçue
            temp_frame = default_frame.copy()
            cv2.putText(temp_frame, f"PC: {ip}", (20, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            current_frames.append(temp_frame)
        else:
            # Redimensionner et ajouter l'IP sur la trame reçue
            if frame.shape[1] != target_width or frame.shape[0] != default_height:
                 frame = cv2.resize(frame, (target_width, default_height))
            
            cv2.putText(frame, f"PC: {ip}", (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            current_frames.append(frame)

    # 3. Assemblage de la grille
    mosaic_rows = []
    
    for i in range(rows):
        start_index = i * cols
        end_index = (i + 1) * cols
        
        current_row_frames = current_frames[start_index:end_index]
        
        # Ajouter des placeholders pour compléter la dernière ligne si nécessaire
        while len(current_row_frames) < cols:
            temp_frame = default_frame.copy()
            cv2.putText(temp_frame, "VIDE", (target_width // 2 - 50, default_height // 2), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (50, 50, 50), 2)
            current_row_frames.append(temp_frame)

        # Empiler horizontalement (création d'une ligne)
        row_mosaic = np.hstack(current_row_frames)
        mosaic_rows.append(row_mosaic)
        
    # 4. Empiler verticalement les lignes
    if mosaic_rows:
        return np.vstack(mosaic_rows)
        
    return default_frame # Retourne le cadre par défaut si la liste d'IP est vide

# --- 4. Boucle de Réception et d'Affichage ---
print("Démarrage de la boucle de réception...")
while True:
    try:
        # A. Réception du paquet (non-bloquant)
        packet, addr = CLIENT_SOCKET.recvfrom(BUFFER_SIZE)
        source_ip = addr[0]
        
        # B. Décodage de la trame
        data = base64.b64decode(packet)
        npdata = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(npdata, 1)
        
        # C. Stockage de la trame si le décodage est réussi
        if frame is not None:
            STREAM_FRAMES[source_ip] = frame

    except socket.timeout:
        # Poursuit la boucle si aucun paquet n'est reçu dans le temps imparti
        pass 
        
    except KeyboardInterrupt:
        break
        
    except Exception as e:
        # Gérer les erreurs de décodage ou autres (optionnel)
        # print(f"⚠️ Erreur de traitement: {e}") 
        time.sleep(0.001)
        
    # D. Construction et Affichage de la Mosaïque (Toujours exécuté pour le rafraîchissement)
    mosaic_frame = build_scalable_mosaic(STREAM_FRAMES, SOURCES_IPS, DEFAULT_WIDTH, DEFAULT_HEIGHT)
    cv2.imshow(f"MONITEUR MULTI-ECRANS ({len(SOURCES_IPS)} flux)", mosaic_frame)
    
    # E. Gestion de l'arrêt
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
            
# --- 5. Nettoyage et Fin du Programme ---
print("Fermeture du socket et nettoyage...")
CLIENT_SOCKET.close()
cv2.destroyAllWindows()