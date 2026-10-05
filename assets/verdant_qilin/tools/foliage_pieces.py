"""Leaf pieces from the reference left view: SLIC superpixels merged by colour, clipped to the foliage mask (ref/foliage_mask.png),
each region -> polygon (+ luminance) in foliage_pieces.json.  Run tools/foliage_polys.py first."""
import json, numpy as np, cv2
from PIL import Image
from skimage.segmentation import slic
from skimage import graph
K = 4
im = Image.open('ref/left_view.png').convert('RGB'); big = np.asarray(im.resize((im.width * K, im.height * K), Image.LANCZOS))
mask = cv2.resize(cv2.imread('ref/foliage_mask.png', 0), (big.shape[1], big.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
sp = slic(big, n_segments=2600, compactness=8, sigma=1.0, start_label=0, enforce_connectivity=True)
seg = graph.cut_threshold(sp, graph.rag_mean_color(big.astype(float), sp), 20)
out = []; dbg = big.copy()
for lab in range(seg.max() + 1):
    m = ((seg == lab) & mask).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cs: continue
    c = max(cs, key=cv2.contourArea); a = cv2.contourArea(c) / K / K
    if a < 14: continue
    ap = cv2.approxPolyDP(c, 1.6 * K, True)[:, 0, :] / K
    if len(ap) < 3: continue
    if len(ap) > 9: ap = cv2.approxPolyDP(c, 3.2 * K, True)[:, 0, :] / K
    if len(ap) < 3: continue
    mm = (seg == lab) & mask
    r, g, b = [float(np.median(big[..., i][mm])) for i in range(3)]
    out.append(dict(pts=[[float(x), float(y)] for x, y in ap], lum=0.3 * r + 0.59 * g + 0.11 * b, area=a))
    cv2.polylines(dbg, [(ap * K).astype(np.int32)], True, (255, 255, 0), 1)
json.dump(out, open('foliage_pieces.json', 'w')); Image.fromarray(dbg).save('ref/pieces_debug.png'); print(len(out), 'pieces')
