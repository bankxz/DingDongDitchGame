"""Reference-vs-render sheet.  python3 compare.py [out.png]   (needs renders/*.png)"""
import sys, os
from PIL import Image, ImageDraw
H = os.path.dirname(os.path.abspath(__file__)); ref = Image.open(os.path.join(H, 'ref/ref.png')).convert('RGB')
crops = {'hero': (0, 100, 740, 1000), 'front': (750, 10, 1110, 465), 'back': (1118, 10, 1448, 465),
         'left': (750, 475, 1100, 765), 'right': (1103, 475, 1448, 765), 'top': (750, 775, 1115, 1070), 'bottom': (1125, 775, 1448, 1070)}
names = sys.argv[2:] or list(crops); out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(H, 'compare.png')
RH = 420; rows = []
for n in names:
    a = ref.crop(crops[n]); b = Image.open(os.path.join(H, 'renders', n + '.png')).convert('RGB')
    a = a.resize((int(a.width * RH / a.height), RH), Image.LANCZOS); b = b.resize((int(b.width * RH / b.height), RH), Image.LANCZOS)
    r = Image.new('RGB', (a.width + b.width + 6, RH), (255, 0, 255)); r.paste(a, (0, 0)); r.paste(b, (a.width + 6, 0))
    ImageDraw.Draw(r).text((6, 6), n, fill=(255, 255, 0)); rows.append(r)
cols = 2; w = max(r.width for r in rows); sh = Image.new('RGB', (w * cols, RH * ((len(rows) + cols - 1) // cols)), (30, 30, 30))
for i, r in enumerate(rows): sh.paste(r, ((i % cols) * w, (i // cols) * RH))
sh.save(out); print(out, sh.size)
