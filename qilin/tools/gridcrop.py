"""python3 gridcrop.py view out.png x0 y0 x1 y1 [zoom=2] [step=25]  -- crop of ref panel upscaled with labelled grid.
view in {left,right,front,back,top,bottom}; coordinates are in the 2.5x panel crop space used in ref/<view>.png"""
import sys
from PIL import Image, ImageDraw
v, out = sys.argv[1], sys.argv[2]; x0, y0, x1, y1 = map(int, sys.argv[3:7]); z = float(sys.argv[7]) if len(sys.argv) > 7 else 2; st = int(sys.argv[8]) if len(sys.argv) > 8 else 25
im = Image.open(f'ref/{v}.png').convert('RGB').crop((x0, y0, x1, y1)); im = im.resize((int(im.width * z), int(im.height * z)), Image.LANCZOS)
d = ImageDraw.Draw(im)
for x in range((x0 // st + 1) * st, x1, st):
    X = (x - x0) * z; d.line([(X, 0), (X, im.height)], fill=(255, 255, 0) if x % 100 == 0 else (255, 255, 255, 90), width=1); d.text((X + 2, 2), str(x), fill=(255, 255, 0))
for y in range((y0 // st + 1) * st, y1, st):
    Y = (y - y0) * z; d.line([(0, Y), (im.width, Y)], fill=(255, 255, 0) if y % 100 == 0 else (255, 255, 255), width=1); d.text((2, Y + 2), str(y), fill=(255, 255, 0))
im.save(out)
