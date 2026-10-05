"""python3 compare.py renders out.png view [view...]  - reference panel | render, trimmed to content and scaled to equal height"""
import sys, numpy as np
from PIL import Image
d, out, views = sys.argv[1], sys.argv[2], sys.argv[3:]
ref = Image.open('reference/bone_dragon_reference.webp').convert('RGB')
PAN = {'front': (0, 0, 512, 470), 'back': (512, 0, 1024, 470), 'left': (1024, 0, 1536, 470), 'right': (0, 500, 512, 940), 'top': (512, 500, 1024, 960), 'persp34': (1024, 500, 1536, 940)}
def trim(im, bg=None):
    a = np.asarray(im.convert('RGBA')); 
    if bg is None: m = a[..., 3] > 20
    else: m = (np.abs(a[..., :3].astype(int) - 236).sum(-1) > 40)
    ys, xs = np.where(m); return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
H = 560; rows = []
for v in views:
    r = trim(ref.crop(PAN[v]), bg=1)
    m = Image.open(f'{d}/{v}.png').convert('RGBA'); m = trim(m)
    bgi = Image.new('RGBA', m.size, (234, 234, 236, 255)); bgi.alpha_composite(m); m = bgi.convert('RGB')
    r = r.resize((int(r.width * H / r.height), H), Image.LANCZOS); m = m.resize((int(m.width * H / m.height), H), Image.LANCZOS)
    row = Image.new('RGB', (r.width + m.width + 10, H), (255, 255, 255)); row.paste(r, (0, 0)); row.paste(m, (r.width + 10, 0)); rows.append(row)
W = max(r.width for r in rows); s = Image.new('RGB', (W, H * len(rows)), (255, 255, 255))
for i, r in enumerate(rows): s.paste(r, (0, i * H))
s.save(out)
