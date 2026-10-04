"""Auto-rotoscope leaves from a reference view: segment -> keep green regions -> fit rotated ellipses.
python3 leafseg.py view  -> writes /tmp/seg_<view>.png overlay + ref/leaves_<view>.json"""
import sys, json, cv2, numpy as np
from skimage.segmentation import felzenszwalb
v = sys.argv[1]; scale = float(sys.argv[2]) if len(sys.argv) > 2 else 120
im = cv2.imread(f'ref/{v}.png'); rgb = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
blur = cv2.bilateralFilter(rgb, 7, 40, 7)
seg = felzenszwalb(blur, scale=scale, sigma=1.0, min_size=80)
hsv = cv2.cvtColor(blur, cv2.COLOR_RGB2HSV)
out = im.copy(); leaves = []
for sid in np.unique(seg):
    m = (seg == sid); a = int(m.sum())
    if a < 150 or a > 14000: continue
    h, s, vv = (hsv[m][:, 0].mean(), hsv[m][:, 1].mean(), hsv[m][:, 2].mean())
    mean = rgb[m].mean(0)
    green = 30 < h < 50 and s > 90 and vv > 40       # opencv hue 0-180 -> green/lime ~ 30-50
    cream = 8 < h < 22 and s < 110 and vv > 150
    brown = 5 < h < 22 and s > 90 and 40 < vv < 150
    kind = 'leaf' if green else 'cream' if cream else 'brown' if brown else 'other'
    cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(cnts, key=cv2.contourArea)
    if len(c) < 5: continue
    (cx, cy), (w, hh), ang = cv2.minAreaRect(c)
    L, W = max(w, hh), min(w, hh); 
    if kind == 'leaf':
        if W < 8 or L / max(W, 1) > 4.5: continue
        leaves.append(dict(cx=cx, cy=cy, L=L, W=W, ang=ang if w >= hh else ang + 90, rgb=[int(x) for x in mean], area=a))
        box = cv2.boxPoints(((cx, cy), (w, hh), ang)).astype(int); cv2.polylines(out, [box], True, (0, 255, 255), 1)
json.dump(leaves, open(f'ref/leaves_{v}.json', 'w'))
cv2.imwrite(f'/tmp/seg_{v}.png', out); print(v, len(leaves), 'leaf regions')
