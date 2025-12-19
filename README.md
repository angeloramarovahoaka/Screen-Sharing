# Screen-Sharing — Remote Desktop / Screen Broadcast

Ce dépôt contient une application Python/PySide6 pour partager l'écran d'une machine (serveur) et y accéder depuis un client. Le projet sépare l'interface utilisateur (client GUI), la logique client léger (réception vidéo + commandes) et la logique serveur (capture, encodage, diffusion). Il est conçu pour fonctionner en LAN via un petit protocole de contrôle (TCP) et streaming vidéo (UDP).

--

**Table des matières**
- **Présentation**
- **Fonctionnalités**
- **Architecture code & réseau**
- **Arborescence principale**
- **Modules clés**
- **Protocoles & ports**
- **Exemples d'exécution**
- **Outils d'entretien**
- **Dépannage courant**

--

**Présentation**

Screen-Sharing est une application de bureau pour partager l'écran d'une machine et permettre à d'autres machines (clients) de regarder et d'envoyer des commandes (souris/clavier). Elle vise la simplicité, faible latence et la modularité pour tests et évolutions.

**Fonctionnalités principales**
- UI de gestion (login, liste d'écrans, zoom sur un écran)
- Serveur de capture et streaming vidéo
- Client récepteur vidéo + couche de commande (TCP) pour souris/clavier
- Sélection du moniteur à partager (tous/écran principal/secondaire)
- Encodage JPEG et segmentation pour transmission UDP
- Découverte et forwarding des logs (optionnel)

**Architecture (Code + Réseau)**

1) Vue d'ensemble

- Côté serveur (processus `ScreenServer`): capture d'écran, encodage, envoi UDP des frames, écoute d'un socket TCP pour commandes et enregistrement des clients.
- Côté client (processus `ScreenClient` dans l'UI): réception UDP des frames, décodage et affichage (QImage), gestion d'un socket TCP bidirectionnel pour envoyer/recevoir commandes et messages de contrôle.
- UI (PySide6): fenêtre principale (`MainWindow`), dialogues (`dialogs`), widgets d'affichage des écrans (`screens/*`). Le client utilise `ScreenClient` pour communiquer avec un serveur distant.

2) Flux réseau

- Vidéo: UDP — serveur -> client(s) sur `VIDEO_PORT` (paramètre). Les frames sont encodées en JPEG et envoyées par paquets UDP. Le code gère le redimensionnement pour tenir dans la MTU.
- Commandes / contrôle: TCP — client -> serveur sur `COMMAND_PORT`. Ce canal sert aussi à l'enregistrement initial (`register`) et aux notifications de contrôle (ex: `{"type":"stream","state":"started"}`).
- Découverte: en option le serveur peut broadcaster une présence (DiscoveryBroadcaster) pour découverte réseau locale.

3) Interaction et événements

- Quand un client se connecte il envoie `register` indiquant son port vidéo. Le serveur démarre le streaming si besoin.
- Le serveur émet des signaux Qt (`status_changed`, `client_connected`, `client_disconnected`, `error_occurred`) qui sont connectés à l'UI lorsque le serveur tourne dans le même processus.
- Lorsqu'un partage s'arrête, le serveur diffuse un message de contrôle `{"type":"stream","state":"stopped"}`; les clients émettent alors `stream_state_changed` et l'UI ferme la vue/retire la vignette.

**Arborescence clé**

- `main.py` — Entrée principale (UI).  
- `run_server.py` — Script autonome pour exécuter uniquement le serveur.  
- `app/` — Code applicatif:
  - `app/ui/` — Widgets et fenêtres (MainWindow, dialogs, screens, style)
  - `app/client/` — `screen_client.py`, `multi_screen_client.py`, `discovery.py`
  - `app/server/` — `screen_server.py`, `video_streamer.py`, `monitor_manager.py`, `command_handler.py`, `discovery.py`
  - `app/config.py` — constantes et état global
- `tools/` — utilitaires : nettoyage des `__pycache__`, scripts pour rebuild/compile
- `logs/` — fichiers de logs générés localement

**Modules & responsabilité**

- `monitor_manager.py` — détection des moniteurs (via `mss`) et calcul des bounding boxes pour la capture (supporte `0` = tous écrans).
- `video_streamer.py` — capture (PIL/mss), encodage JPEG (OpenCV), downsizing pour tenir dans les limites UDP, et envoi aux clients.
- `screen_server.py` — orchestration : écoute TCP pour commandes, gestion des connexions clients et threads de streaming, discovery.
- `command_handler.py` — exécute les actions (souris, clavier) reçues via TCP sur la machine partageuse.
- `screen_client.py` — reçoit, décode et émet signaux d'image vers l'UI ; gère le socket de contrôle.
- `ui/*` — widgets PySide6 pour la liste des écrans, viewer (zoom), dialogues et barre d'outils.

**Protocoles & ports par défaut**
- `VIDEO_PORT` (UDP) — flux vidéo (défini dans `app/config.py`)
- `COMMAND_PORT` (TCP) — commandes et messages de contrôle

Considérations réseau :
- UDP n'est pas fiable — le code est conçu pour tolérer pertes de paquets et reconstruire frames.
- Le serveur peut accepter plusieurs clients ; attention à la bande passante en LAN si plusieurs récepteurs.

**Dépendances (extraites de `requirements.txt`)**
- Python 3.10+ (ou 3.11/3.12 selon votre environnement)
- `PySide6` — interface graphique
- `pyscreenshot` / `mss` — capture d'écran
- `opencv-python` — encodage/decodage d'images (cv2)
- `numpy` — manipulation d'images

Installez-les avec:
```powershell
pip install -r requirements.txt
```

**Commandes utiles**

- Lancer l'UI (client + capacité serveur locale) :
```powershell
python main.py
```
- Lancer le serveur autonome :
```powershell
python run_server.py [client_ip]
```
- Nettoyer tous les `__pycache__` (PowerShell):
```powershell
.\tools\remove_pycaches.ps1 -Root . -Delete
```
- Nettoyer et recompiler (script utilitaire fourni) :
```powershell
python .\tools\rebuild_pycaches.py --clean --compile
```

**Comportement important**
- Quand un client annonce `stream: stopped`, le client UI ferme la vue zoom et retire la vignette — cela évite d'afficher des écrans inactifs.
- Si `PySide6` n'est pas installé, l'importation échoue avant l'UI; installer les dépendances résout le problème.

**Dépannage rapide**
- Erreur `ModuleNotFoundError: No module named 'app.server'` : vérifiez que `app/server` existe dans votre branche ; si absent, restaurez-le depuis la branche contenant la couche serveur.
- Erreur `ModuleNotFoundError: No module named 'PySide6'` : installez `PySide6`.
- Latence / frames manquantes : vérifier la MTU/bande passante UDP et l'utilisation CPU du server (encodage JPEG coûteux). Ajuster `DEFAULT_WIDTH` et `JPEG_QUALITY` dans `app/config.py`.

**Développement & Contribuer**
- Respectez la séparation UI ↔ client ↔ serveur. Préférez signaux (Qt) ou callbacks pour notifier l'UI d'événements serveur.
- Ajoutez tests unitaires pour `monitor_manager` et `command_handler` si vous modifiez la logique système. Le streaming est plus simple à tester manuellement ou via mocks.

--

Si vous voulez, je peux :
- ajouter un diagramme d'architecture (ASCII ou image) dans ce README, ou
- commiter et push ce README pour vous, ou
- compléter la section « Déploiement / CI » pour automatiser builds et tests.

---
Fichier généré automatiquement par l'assistant — modifiez au besoin pour refléter vos réglages et ports personnalisés.
