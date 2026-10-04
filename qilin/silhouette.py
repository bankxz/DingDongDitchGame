"""Silhouette fit vs the reference panels.  python3 silhouette.py   -> prints bbox aspect / IoU per view, writes overlay.png
red = reference only, green = render only, yellow = both.  Render is scaled+aligned to the reference bbox
(height-normalised) so it measures SHAPE; the aspect-ratio line shows proportion error directly."""
import os, sys, numpy as np
from PIL import Image
H = os.path.dirname(os.path.abspath(__file__))
ref = np.asarray(Image.open(os.path.join(H, 'ref/ref.png')).convert('RGB')).astype(float)
# inner panel crops (margins skip borders + title chips)
crops = {'front': (765, 62, 1098, 458), 'back': (1132, 62, 1436, 458), 'left': (765, 505, 1090, 758),
         'right': (1115, 505, 1440, 758), 'top': (772, 822, 1108, 1032), 'bottom': (1140, 822, 1435, 1032)}
def mask_ref(c):
    x0, y0, x1, y1 = c; a = ref[y0:y1, x0:x1]
    bg = np.median(np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3)]), 0)
    return np.linalg.norm(a - bg, axis=2) > 38
def mask_img(p):
    a = np.asarray(Image.open(p).convert('RGB')).astype(float); bg = np.array([a[2, 2]])[0]
    return np.linalg.norm(a - bg, axis=2) > 30
def bbox(m):
    ys, xs = np.where(m); return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
def norm(m, size):
    x0, y0, x1, y1 = bbox(m); im = Image.fromarray((m[y0:y1, x0:x1] * 255).astype(np.uint8)).resize(size, Image.BILINEAR)
    return np.asarray(im) > 127
names = sys.argv[1:] or list(crops); tiles = []
for n in names:
    mr = mask_ref(crops[n]); mi = mask_img(os.path.join(H, 'renders', n + '.png'))
    br, bi = bbox(mr), bbox(mi); ar = (br[2] - br[0]) / (br[3] - br[1]); ai = (bi[2] - bi[0]) / (bi[3] - bi[1])
    S = (400, int(400 / ar)); a = norm(mr, S); b = norm(mi, S)
    iou = (a & b).sum() / max(1, (a | b).sum())
    print(f'{n:7s} aspect ref {ar:.2f} mine {ai:.2f} ({(ai/ar-1)*100:+.0f}%)  IoU(bbox-normalised) {iou:.2f}')
    o = np.zeros(S[::-1] + (3,), np.uint8); o[a] += np.array([200, 0, 0], np.uint8); o[b] += np.array([0, 200, 0], np.uint8)
    tiles.append(Image.fromarray(o))
Wd = sum(t.width for t in tiles) + 8 * len(tiles); Hh = max(t.height for t in tiles)
sh = Image.new('RGB', (Wd, Hh)); x = 0
for t in tiles: sh.paste(t, (x, 0)); x += t.width + 8
sh.save(os.path.join(H, 'overlay.png'))
