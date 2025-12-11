import cv2, imutils, socket
import numpy as np
import time
import base64

BUFFER_SIZE = 65536
CLIENT_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
CLIENT_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
HOST_NAME = socket.gethostname()
HOST_IP =  "192.168.11.122"
print("HOST IP:", HOST_IP)
PORT = 9999
message = b'Hello, Server!'
CLIENT_SOCKET.sendto(message, (HOST_IP, PORT))

while True:
    packet, _ = CLIENT_SOCKET.recvfrom(BUFFER_SIZE)
    data = base64.b64decode(packet)
    npdata = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(npdata, 1)
    cv2.imshow("RECEIVING VIDEO", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        CLIENT_SOCKET.close()
        break
