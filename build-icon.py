from PIL import Image
import sys

img = Image.open('assets/icon.ico')
img = img.resize((256, 256), Image.LANCZOS)
img.save(sys.argv[1])
