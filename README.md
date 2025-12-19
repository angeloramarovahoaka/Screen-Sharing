# Screen Sharing — Remote Desktop (Local Network)

Ce dépôt contient une application de partage d'écran et de contrôle à distance conçue pour un réseau local. Elle inclut une interface GUI (PySide6) et une implémentation serveur/client simple pour transmettre des frames (UDP) et acheminer des commandes (TCP).

**Langage**: Python

---

**Table des matières**
- **Présentation**
- **Fonctionnalités**
- **Architecture réseau**
- **Protocoles & Format des messages**
- **Organisation du code**
- **Composants principaux**
- **Configuration & constantes**
- **Dépendances**
- **Installation et exécution**
- **Sécurité et limitations**
- **Extensibilité**
- **Dépannage rapide**

---

**Présentation**

Ce projet propose une application desktop permettant:
- de partager l'écran d'une machine (serveur)
- de se connecter à un écran partagé depuis une autre machine (client)
- d'afficher plusieurs écrans distants sous forme de miniatures
- de zoomer un écran et d'envoyer des commandes de souris et clavier au serveur

L'application combine une UI PySide6 et des modules réseau autonomes pour le streaming et la commande.

---

**Fonctionnalités**
- Authentification simple (fichier `app/config.py` — dictionnaire `USERS`).
- Découverte réseau (broadcast UDP) pour trouver des serveurs dans le LAN.
- Streaming vidéo: capture d'écran -> encodage JPEG -> envoi UDP.
- Commandes de contrôle: envoi JSON via TCP (souris/clavier).
- Multi-écrans: détection des moniteurs locaux, sélection de moniteur à partager.
- UI riche: liste de miniatures, zoom, contrôle (clic, mouvements, molette, combos clavier).

---

**Architecture réseau**

- Découverte: UDP broadcast sur le port `DISCOVERY_PORT` (par défaut `9997`). Le serveur envoie régulièrement une annonce JSON {type: "screen_share_announcement", name, ip, port, video_port} à `'255.255.255.255'` (fallback `'<broadcast>'`). Le client écoute `DISCOVERY_PORT` pour recueillir ces annonces.
- Streaming vidéo: le serveur envoie des frames JPEG encodées via UDP au `VIDEO_PORT` (par défaut `9999`). Les clients reçoivent par socket UDP.
- Commandes / Signaux de contrôle: canal TCP (server écoute `COMMAND_PORT`, par défaut `9998`). Le client se connecte en TCP pour envoyer commandes JSON et recevoir les notifications (ex: état du stream).

Topologie simplifiée:

Client <---- TCP (commandes) ---- Server
Client <---- UDP (video frames) -- Server
Server ---- UDP broadcast (annonces) ---> LAN

Notes:
- UDP est utilisé pour la vidéo car il est simple et tolérant aux pertes pour un flux d'écran (latence priorisée). L'application réalise un découpage simple: encode chaque frame en JPEG et envoie le binaire UDP (si taille > MTU, la classe `VideoStreamer` tente de downscaler).
- TCP est utilisé pour les commandes parce qu'on veut livraison fiable et ordre correct pour les actions clavier/souris.

---

**Protocoles & Format des messages**

- Découverte (UDP): JSON encodé en UTF-8
  - Exemple: {"type":"screen_share_announcement","name":"mymachine","ip":"192.168.1.10","port":9998,"video_port":9999}

- Enregistrement client -> serveur (TCP) : JSON + '\n'
  - Type: `register` — ex: {"type":"register","video_port":<port_local_udp>}

- Notifications serveur -> client (TCP) : JSON + '\n'
  - Ex: {"type":"stream","state":"started"}

- Commandes client -> serveur (TCP) : JSON + '\n'
  - Mouse: {"type":"mouse","action":"move|press|release|scroll","x":<0..1> ,"y":<0..1>,"button":"left|right|middle"}
  - Keyboard single: {"type":"key","action":"press|release","key":"a"}
  - Combo: {"type":"key","action":"combo","keys":["ctrl","c"]}

- Vidéo (UDP): paquet(s) contenant un JPEG binaire. Le client tente un cv2.imdecode direct; si l'encodage est base64, il décodera.

---

**Organisation du code**

Racine du projet:
- `main.py` : point d'entrée (lance l'application PySide6)
- `requirements.txt` : (liste des dépendances attendues)
- `app/` : code principal
  - `config.py` : constantes réseau, état global `app_state`, comptes utilisateurs
  - `client/` : modules côté client (réception vidéo, scanner de découverte)
    - `screen_client.py` : `ScreenClient` — socket UDP pour vidéo, socket TCP commandes
    - `multi_screen_client.py` : `MultiScreenClient` — gère plusieurs `ScreenClient`
    - `discovery.py` : `DiscoveryScanner` — écoute UDP discovery
    - `logging_config.py` : configuration du logger client
  - `server/` : modules côté serveur (capture & exécution commandes)
    - `screen_server.py` : `ScreenServer` — orchestre streaming et commandes (threads)
    - `video_streamer.py` : `VideoStreamer` — capture écran, encode JPEG, envoie UDP
    - `monitor_manager.py` : `MonitorManager` — détection et sélection des moniteurs
    - `command_handler.py` : `CommandHandler` — exécute mouvements souris et touches via `pynput` / ctypes
    - `discovery.py` : `DiscoveryBroadcaster` — envoie les annonces réseau
    - `keyboard_utils.py` : mapping touches et helpers natifs Windows pour Win/arrow keys
  - `ui/` : interface graphique PySide6
    - `main_window.py`, `ui_login.py`, `ui_style.py`, `dialogs/`, `screens/` (widgets viewer, thumbnail, etc.)

Outils:
- `tools/` : utilitaires comme `log_collector.py`, `rebuild_pycaches.py`.

---

**Composants principaux (rôle & interactions)**

- `ScreenServer` (server/screen_server.py)
  - Démarre un listener TCP (`COMMAND_PORT`) pour recevoir connexions des clients et conserver la connexion TCP ouverte pour notifications.
  - Contient `VideoStreamer` (envoie UDP frames) et `CommandHandler` (exécute commandes reçues).
  - Diffuse (DiscoveryBroadcaster) l'annonce UDP tant que le streaming est actif.

- `VideoStreamer` (server/video_streamer.py)
  - Capture écran avec `pyscreenshot`/PIL ou `mss` si disponible.
  - Redimensionne les frames (utilise `imutils`) à `DEFAULT_WIDTH` et encode en JPEG via `cv2.imencode`.
  - Tente une réduction progressive si la taille JPEG dépasse la limite pratique pour UDP (~60000 octets dans le code).
  - Envoie les bytes JPEG via UDP vers chaque client enregistré.

- `CommandHandler` (server/command_handler.py)
  - Reçoit commandes JSON et exécute via `pynput.mouse.Controller` et `pynput.keyboard.Controller`.
  - Pour les flèches et la touche Windows, utilise des appels natifs Windows (`ctypes`) pour fiabilité.
  - Supporte combos atomiques (liste de touches modificateur + touche principale).

- `MonitorManager` (server/monitor_manager.py)
  - Détecte moniteurs via `mss` ou via Qt (`QGuiApplication.screens()`), calcule bboxes, et expose `get_capture_bbox()`.

- `ScreenClient` (client/screen_client.py)
  - Ouvre un socket UDP local pour recevoir frames et un socket TCP vers le serveur pour envoyer commandes et s'enregistrer.
  - `connect_to_server` envoie {type: 'register', video_port: <port>} — le serveur doit alors adresser son flux UDP vers ce port.
  - Décode les frames reçues en BGR via `cv2.imdecode`, convertit en `QImage` et émet `frame_received`.

- UI: `MainWindow`, `LoginWindow`, `ScreenViewer`, `ScreenListWidget` — intègrent la logique pour démarrer/arrêter streaming local et se connecter à des serveurs distants.

---

**Configuration & constantes importantes**
- Ports (valeurs par défaut dans `app/config.py`):
  - `VIDEO_PORT = 9999` (UDP)
  - `COMMAND_PORT = 9998` (TCP)
  - `DISCOVERY_PORT = 9997` (UDP broadcast)
- `BUFFER_SIZE = 131072`
- `DEFAULT_WIDTH`, `DEFAULT_HEIGHT`, `JPEG_QUALITY` (taille & qualité d'encodage)

---

**Dépendances**
- Python 3.8+ recommandé
- Bibliothèques principales:
  - `PySide6` (interface graphique)
  - `opencv-python` (cv2) pour encodage/décodage JPEG
  - `numpy`
  - `pynput` (injection clavier/souris côté serveur)
  - Optionnel: `mss` (capture écran multi-moniteur plus performante)
  - Optionnel: `pyscreenshot` ou PIL (fallback)

Ajoutez ces paquets dans `requirements.txt` si nécessaire.

---

**Installation & exécution (Windows PowerShell)**

1) Créez et activez un venv (optionnel mais recommandé):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

2) Installer dépendances (exemple minimal):

```powershell
pip install PySide6 opencv-python numpy pynput mss pillow
```

3) Lancer l'application GUI:

```powershell
python main.py
```

4) Utilisation:
- Sur la machine qui partage: ouvrez l'app, connectez-vous (ex: `admin/admin123`), puis cliquez `Partager mon écran` pour démarrer le serveur et le broadcast.
- Sur la machine cliente: ouvrez l'app, `Ajouter écran` puis sélectionnez un serveur trouvé ou entrez l'IP manuellement. La miniature et la connexion apparaîtront.

---

**Sécurité & limitations**
- Authentification: très basique (dictionnaire `USERS` en clair). Ne pas utiliser en production sans chiffrement et stockage sécurisé des identifiants.
- Chiffrement: tout le trafic est en clair (UDP pour vidéo, TCP pour commandes). Sur un réseau non fiable, il faut encapsuler via TLS (TCP) et chiffrement pour vidéo (SRTP ou TLS+DTLS ou tunnel VPN).
- Performance: envoi de frames JPEG intégrales via UDP est simple mais peut provoquer des pertes et des fragments UDP si la taille excède MTU. Le code tente de downscaler pour respecter une taille raisonnable mais n'implémente pas la segmentation/réassemblage robuste. Pour un usage sérieux, utiliser WebRTC / RTP ou un protocole avec contrôle d'erreur.
- Contrôle clavier/souris: `pynput` et appels natifs Windows sont utilisés — ils exigent des droits suffisants côté serveur.

---

**Extensibilité & idées d'amélioration**
- Utiliser WebRTC pour streaming (latence + NAT traversal + chiffrement)
- Ajouter TLS pour le canal commande (sécuriser les commandes)
- Mettre en place authentification multi-utilisateur et ACL (qui peut contrôler quel écran)
- Implémenter compression et fragmentation UDP côté serveur/ client pour frames > MTU
- Ajouter enregistrement côté serveur ou client
- Améliorer la QoS: adaptation dynamique de la qualité/ framerate selon latence/perte

---

**Dépannage rapide**
- Pas de vidéo reçu sur client: vérifier firewall Windows (autoriser UDP sortant/entrant sur `VIDEO_PORT`), vérifier que le serveur envoie bien (`VideoStreamer._send_to_clients` log), vérifier que le client s'est correctement `register` (envoyé via TCP) et que le port UDP local est correct.
- Commands non exécutées: vérifier connexion TCP (`COMMAND_PORT`), vérifier droits d'injection clavier/souris sur la machine serveur.
- Découverte non trouvée: vérifier que votre réseau autorise broadcast; sur certains réseaux ou VLANs, les broadcasts sont bloqués.

---

Si vous voulez, je peux:
- générer un `requirements.txt`/`pyproject.toml` précis à partir des imports;
- ajouter des instructions détaillées pour packager en exécutable Windows (PyInstaller);
- sécuriser le canal commande (ex: wrapper TLS simple) et documenter le changement.

---

Fichier principal d'exécution: `main.py`.

Merci — dites-moi si vous souhaitez que j'ajoute un guide pas-à-pas pour déploiement ou des exemples de messages réseau. 
