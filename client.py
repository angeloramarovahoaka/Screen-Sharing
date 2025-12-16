import socket
import time

SERVER_IP = "192.168.11.183"  # IP DU SERVEUR
SERVER_PORT = 5000

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

print("Connexion au serveur...")
client.connect((SERVER_IP, SERVER_PORT))
print("Connecté au serveur.")

try:
    while True:
        time.sleep(1)  # garde la connexion ouverte
except KeyboardInterrupt:
    print("Déconnexion...")
finally:
    client.close()
