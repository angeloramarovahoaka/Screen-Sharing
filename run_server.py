"""
Serveur autonome de partage d'écran
Lancez ce script sur la machine dont vous voulez partager l'écran

Usage:
    python run_server.py [client_ip]
    
Exemple:
    python run_server.py 192.168.1.100
"""
import sys
import argparse
from app.server_module import ScreenServer
from app.config import VIDEO_PORT, COMMAND_PORT


def main():
    parser = argparse.ArgumentParser(description="Serveur de partage d'écran")
    parser.add_argument(
        "client_ip",
        nargs="?",
        default="127.0.0.1",
        help="Adresse IP du client qui recevra le flux (défaut: 127.0.0.1)"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1920,
        help="Largeur de l'écran (défaut: 1920)"
    )
    parser.add_argument(
        "--height",
        type=int,
        default=1080,
        help="Hauteur de l'écran (défaut: 1080)"
    )
    parser.add_argument(
        "--log-collector",
        type=str,
        default=None,
        help="Optional log collector in format host:port to forward logs"
    )
    parser.add_argument(
        "--webcam",
        action="store_true",
        help="Utiliser la webcam au lieu de la capture d'écran"
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("🖥️  SERVEUR DE PARTAGE D'ÉCRAN")
    print("=" * 50)
    print(f"📡 Port vidéo (UDP): {VIDEO_PORT}")
    print(f"📡 Port commandes (TCP): {COMMAND_PORT}")
    print(f"🎯 Client cible: {args.client_ip}")
    print(f"📐 Résolution: {args.width}x{args.height}")
    print("=" * 50)
    print()
    
    # Créer et démarrer le serveur
    server = ScreenServer()
    server.screen_width = args.width
    server.screen_height = args.height
    server.use_webcam = args.webcam

    # If a log collector was provided, export env var so modules forward logs
    if args.log_collector:
        import os
        os.environ['SS_LOG_COLLECTOR'] = args.log_collector
        print(f"📣 Forwarding logs to collector: {args.log_collector}")
    
    # Connecter les signaux pour afficher les messages
    server.status_changed.connect(lambda s: print(f"📢 {s}"))
    server.client_connected.connect(lambda c: print(f"✅ Client connecté: {c}"))
    server.client_disconnected.connect(lambda c: print(f"❌ Client déconnecté: {c}"))
    server.error_occurred.connect(lambda e: print(f"⚠️ Erreur: {e}"))
    
    # Démarrer le serveur (écoute des commandes seulement)
    server.start(args.client_ip)
    
    print("▶️ Serveur démarré (en attente de connexions).")
    print("📝 Le streaming vidéo démarrera automatiquement quand un client se connectera.")
    print("   Pour forcer le streaming maintenant, utilisez l'interface graphique.")
    print()
    
    try:
        # Garder le script en vie
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        print("🛑 Arrêt du serveur...")
        server.stop()
        print("👋 Au revoir!")


if __name__ == "__main__":
    main()
