"""python3 overlay.py renders out.png view... : silhouette overlay, reference=red, render=cyan, both=dark"""
import sys, numpy as np
from PIL import Image
sys.path.insert(0, 'tools')
d, out, views = sys.argv[1], sys.argv[2], sys.argv[3:]
ref = Image.open('reference/bone_dragon_reference.webp').convert('RGB')
PAN = {'front': (0, 0, 512, 440), 'back': (512, 0, 1024, 440), 'left': (1024, 0, 1536, 440), 'right': (0, 500, 512, 940), 'top': (512, 500, 1024, 940), 'persp34': (1024, 500, 1536, 940)}
H = 600; rows = []
for v in views:
    r = np.asarray(ref.crop(PAN[v]))
    rm = (np.abs(r.astype(int) - np.array([236, 236, 238])).sum(-1) > 45)
    ys, xs = np.where(rm); rim = Image.fromarray((rm * 255).astype(np.uint8)).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    m = np.asarray(Image.open(f'{d}/{v}.png').convert('RGBA'))[..., 3] > 30
    ys, xs = np.where(m); mim = Image.fromarray((m * 255).astype(np.uint8)).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    W = int(max(rim.width * H / rim.height, 100)); rim = rim.resize((W, H)); mim = mim.resize((W, H))
    a, b = np.asarray(rim) > 100, np.asarray(mim) > 100
    img = np.full((H, W, 3), 255, np.uint8); img[a & ~b] = (230, 60, 60); img[b & ~a] = (40, 200, 220); img[a & b] = (60, 60, 70)
    rows.append(Image.fromarray(img))
W = sum(r.width for r in rows); s = Image.new('RGB', (W + 10 * len(rows), H), (255, 255, 255)); x = 0
for r in rows: s.paste(r, (x, 0)); x += r.width + 10
s.save(out)
