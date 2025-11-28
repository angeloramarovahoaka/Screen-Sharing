import socket
import struct
import io
from PIL import Image

UDP_PORT = 5005
frames = {}

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("", UDP_PORT))

print("Listening...")

current_frame = -1

while True:
    packet, addr = sock.recvfrom(65535)

    # decode header
    frame_id, packet_id, total_packets = struct.unpack("!IHH", packet[:8])
    payload = packet[8:]

    if frame_id not in frames:
        frames[frame_id] = [None] * total_packets

    frames[frame_id][packet_id] = payload

    # check if image is complete
    if all(part is not None for part in frames[frame_id]):
        full_image = b"".join(frames[frame_id])

        # save or send to front
        with open("latest_frame.jpg", "wb") as f:
            f.write(full_image)

        # cleanup
        if frame_id - 1 in frames:
            del frames[frame_id - 1]

        print(f"Frame {frame_id} reassembled!")
