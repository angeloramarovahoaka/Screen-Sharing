import socket
import threading

HOST = "0.0.0.0"   # écoute sur toutes les interfaces
PORT = 5000

clients = {}  # conn -> ip


def handle_client(conn, addr):
    ip_client = addr[0]
    print(f"[+] Client connecté : {ip_client}")

    clients[conn] = ip_client
    print_clients()

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
    except:
        pass
    finally:
        print(f"[-] Client déconnecté : {ip_client}")
        clients.pop(conn, None)
        print_clients()
        conn.close()


def print_clients():
    print("\n=== CLIENTS CONNECTÉS ===")
    for ip in clients.values():
        print(f"✔ {ip}")
    print("========================\n")


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()

    print(f"Serveur démarré sur le port {PORT}")
    print("En attente de clients...\n")

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(
            target=handle_client, args=(conn, addr), daemon=True
        )
        thread.start()


if __name__ == "__main__":
    main()
