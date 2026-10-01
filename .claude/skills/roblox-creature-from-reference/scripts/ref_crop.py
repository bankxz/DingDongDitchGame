"""Enlarge a reference crop (or a region of a sheet) so details are visible.
python ref_crop.py in.png out.png [scale=4] [x0 y0 x1 y1]"""
import sys
from PIL import Image

im = Image.open(sys.argv[1]).convert('RGB')
k = float(sys.argv[3]) if len(sys.argv) > 3 else 4
if len(sys.argv) > 7:
    im = im.crop(tuple(int(v) for v in sys.argv[4:8]))
im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS).save(sys.argv[2])
print(sys.argv[2], im.size)
