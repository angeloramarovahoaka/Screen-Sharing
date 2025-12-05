"""
Script de test de connexion TCP pour diagnostiquer les problèmes de pare-feu
Usage: python test_connection.py <server_ip>
"""
import socket
import sys

def test_tcp_connection(server_ip, port=9998):
    """Teste la connexion TCP vers un serveur"""
    print(f"🔍 Test de connexion TCP vers {server_ip}:{port}")
    print("=" * 60)
    
    try:
        # Créer socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10.0)
        
        print(f"📡 Tentative de connexion...")
        sock.connect((server_ip, port))
        
        local_addr = sock.getsockname()
        remote_addr = sock.getpeername()
        
        print(f"✅ SUCCÈS!")
        print(f"   Local:  {local_addr[0]}:{local_addr[1]}")
        print(f"   Remote: {remote_addr[0]}:{remote_addr[1]}")
        print(f"\n✨ Le serveur {server_ip}:{port} est accessible!")
        print(f"   Le problème ne vient PAS du réseau ou du pare-feu.")
        
        sock.close()
        return True
        
    except socket.timeout:
        print(f"❌ TIMEOUT après 10 secondes")
        print(f"\n🔥 CAUSES PROBABLES:")
        print(f"   1. Le serveur n'est pas lancé sur {server_ip}")
        print(f"   2. Le pare-feu bloque le port {port}")
        print(f"   3. Problème de routage réseau")
        return False
        
    except ConnectionRefusedError as e:
        print(f"❌ CONNEXION REFUSÉE (errno {e.errno})")
        print(f"\n🔥 CAUSES PROBABLES:")
        print(f"   1. Le serveur n'écoute pas sur le port {port}")
        print(f"   2. Le serveur n'est pas lancé")
        print(f"   3. Le serveur écoute sur 127.0.0.1 au lieu de 0.0.0.0")
        return False
        
    except OSError as e:
        if e.errno == 10061:  # Windows
            print(f"❌ REFUS ACTIF DE CONNEXION (Windows errno 10061)")
            print(f"\n🔥 CAUSES PROBABLES:")
            print(f"   1. Le pare-feu Windows bloque le port {port}")
            print(f"   2. Le serveur n'est pas lancé")
            print(f"\n💡 SOLUTION (sur le serveur Windows):")
            print(f"   Exécutez en PowerShell (admin):")
            print(f'   New-NetFirewallRule -DisplayName "ScreenShare TCP {port}" -Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow')
        elif e.errno == 113:  # Linux
            print(f"❌ AUCUNE ROUTE VERS L'HÔTE (Linux errno 113)")
            print(f"\n🔥 CAUSES PROBABLES:")
            print(f"   1. Le pare-feu Linux bloque le port {port}")
            print(f"   2. Problème de routage réseau")
            print(f"\n💡 SOLUTION (sur le serveur Linux):")
            print(f"   sudo ufw allow {port}/tcp")
        else:
            print(f"❌ ERREUR RÉSEAU (errno {e.errno}): {e}")
        return False
        
    except Exception as e:
        print(f"❌ ERREUR INATTENDUE: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_connection.py <server_ip> [port]")
        print("Exemple: python test_connection.py 192.168.11.19")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9998
    
    success = test_tcp_connection(server_ip, port)
    sys.exit(0 if success else 1)
