import cv2, imutils, socket
import numpy as np
import time
import base64

BUFFER_SIZE = 65536
SERVER_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
SERVER_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE)
HOST_NAME = socket.gethostname()
HOST_IP = "192.168.11.122"
print("HOST IP:", HOST_IP)
PORT = 9999
socket_address = (HOST_IP, PORT)
SERVER_SOCKET.bind(socket_address)
print("Listening at:", socket_address)
vid = cv2.VideoCapture(0)
fps,st,frame_count, cnt = (0,0,20,0)
while True:
    msg, addr = SERVER_SOCKET.recvfrom(BUFFER_SIZE)
    print("Received message from:", addr)
    print("Message 1:", msg)
    WIDTH=400
    while (vid.isOpened()):
        print("Sending video...", msg)
        _, frame = vid.read()
        frame = imutils.resize(frame, width=WIDTH)
        encoded, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        b64encoded = base64.b64encode(buffer)
        SERVER_SOCKET.sendto(b64encoded, addr)
        cv2.imshow("Sending...", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            SERVER_SOCKET.close()
            break
    

