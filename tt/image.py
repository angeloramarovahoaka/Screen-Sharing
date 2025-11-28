from PIL import Image
import time

while True:
    try:
        img = Image.open("latest_frame.jpg")
        img.show()
        break
    except:
        time.sleep(0.1)
