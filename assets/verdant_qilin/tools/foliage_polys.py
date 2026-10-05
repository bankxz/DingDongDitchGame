"""Foliage silhouettes from the reference LEFT view -> polygons (1x px of ref/left_view.png) per group, saved to foliage_polys.json."""
import numpy as np, cv2, json, sys
from PIL import Image
im = np.asarray(Image.open('ref/left_view.png').convert('RGB')); K = 3
big = cv2.resize(im, None, fx=K, fy=K, interpolation=cv2.INTER_CUBIC)
r, g, b = [big[..., i].astype(int) for i in range(3)]
hsv = cv2.cvtColor(big, cv2.COLOR_RGB2HSV); h, s, v = [hsv[..., i].astype(int) for i in range(3)]
m = (g > b + 6) & (g >= r - 4) & (v > 38) & (s > 60)
m &= ~((h <= 44) & (v < 175) & (r > g * 0.85))            # olive / brown body
def zero(x0, y0, x1, y1): m[int(y0 * K):int(y1 * K), int(x0 * K):int(x1 * K)] = False
zero(100, 150, 232, 216)      # torso / thigh block
zero(0, 0, 8, 290); zero(0, 0, 365, 8); zero(0, 270, 365, 290); zero(340, 0, 365, 290)
zero(0, 92, 52, 130)         # muzzle + face
zero(110, 205, 232, 290)      # far legs
m = m.astype(np.uint8) * 255
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((13, 13), np.uint8))
m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
mask_big = m.copy()
cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
out = []; dbg = big.copy()
for c in cnts:
    if cv2.contourArea(c) < 90 * K * K: continue
    ap = cv2.approxPolyDP(c, 2.2 * K, True)[:, 0, :] / K
    cx, cy = ap.mean(0)
    grp = 'tail' if cx > 228 else ('leg' if cy > 200 else ('mane' if cx < 150 and cy < 150 else 'body'))
    out.append(dict(group=grp, pts=[[float(x), float(y)] for x, y in ap]))
    cv2.polylines(dbg, [(ap * K).astype(np.int32)], True, (255, 0, 0), 2)
cv2.imwrite('ref/foliage_mask.png', mask_big)
json.dump(out, open('foliage_polys.json', 'w'))
Image.fromarray(dbg).save(sys.argv[1] if len(sys.argv) > 1 else 'ref/foliage_debug.png'); print([(o['group'], len(o['pts'])) for o in out])
