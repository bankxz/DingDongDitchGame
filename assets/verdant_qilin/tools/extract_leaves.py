"""Extract leaves from the LEFT VIEW of the reference sheet: SLIC superpixels -> colour-merge -> keep leaf-coloured
segments -> fit an oriented rectangle each (base, tip, width, colour slot).  Writes leaves_left.json (1x crop px)."""
import sys, json, numpy as np, cv2
from skimage.segmentation import slic
from skimage import graph
from PIL import Image
src, out, dbg = sys.argv[1], sys.argv[2], sys.argv[3]
VIEW = sys.argv[4] if len(sys.argv) > 4 else 'left'
CROP = {'left': (750, 480, 1115, 770), 'front': (750, 10, 1110, 470), 'back': (1120, 10, 1448, 470), 'top': (750, 775, 1115, 1075)}[VIEW]
im = Image.open(src).convert('RGB').crop(CROP); K = 4
big = np.asarray(im.resize((im.width * K, im.height * K), Image.LANCZOS))
sp = slic(big, n_segments=2600, compactness=8, sigma=1.0, start_label=0, enforce_connectivity=True)
hsv = cv2.cvtColor(big, cv2.COLOR_RGB2HSV)
# zones (1x px) that are NOT leaves even if green: thigh block, muzzle/face, torso side
EXCL = [(163, 150, 214, 208), (4, 100, 46, 128)]
def anchor(cx, cy):
    if cx > 228: return (245, 152)          # tail
    if cy > 205: return (cx, 300)           # leg leaves: base is the lower end
    if cx < 150 and cy < 150: return (75, 118)   # head / mane
    return (110, 182)                        # body
leaves = []; dbgim = big.copy(); claimed = np.zeros(big.shape[:2], bool)
RAG = graph.rag_mean_color(big.astype(float), sp)
for TH, SOL, MINA in ((22, 0.72, 400), (12, 0.62, 200)):
  seg = graph.cut_threshold(sp, RAG, TH)
  for lab in range(seg.max() + 1):
      m = (seg == lab).astype(np.uint8)
      a = int(m.sum())
      if a < MINA or a > 9000: continue
      ys, xs = np.nonzero(m); cx, cy = xs.mean() / K, ys.mean() / K
      if claimed[int(ys.mean()), int(xs.mean())]: continue
      if any(x0 <= cx <= x1 and y0 <= cy <= y1 for x0, y0, x1, y1 in EXCL): continue
      h, s, v = [float(np.median(hsv[..., i][m > 0])) for i in range(3)]
      if s < 100 or v < 45: continue
      if not (26 <= h <= 85): continue                       # green family only
      if h <= 47 and v < 170: continue                       # olive torso / body block
      cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
      c = max(cnts, key=cv2.contourArea)
      hull = cv2.convexHull(c)
      if cv2.contourArea(c) / max(cv2.contourArea(hull), 1) < SOL: continue      # ragged merge, not a leaf
      P = c[:, 0, :].astype(float); ctr = P.mean(0)
      ev, evec = np.linalg.eigh(np.cov((P - ctr).T)); d = evec[:, 1]; nrm = evec[:, 0]
      pr = (P - ctr) @ d; pw = (P - ctr) @ nrm
      l = pr.max() - pr.min(); w = pw.max() - pw.min()
      if l > 5.5 * w: continue
      mid = ctr + d * (pr.max() + pr.min()) / 2
      e1, e2 = mid + d * l / 2, mid - d * l / 2
      ax, ay = anchor(cx, cy)
      base, tip = (e1, e2) if np.hypot(e1[0] / K - ax, e1[1] / K - ay) < np.hypot(e2[0] / K - ax, e2[1] / K - ay) else (e2, e1)
      r, g_, b = [float(np.median(big[..., i][m > 0])) for i in range(3)]
      lum = 0.3 * r + 0.59 * g_ + 0.11 * b
      claimed |= m.astype(bool)
      leaves.append(dict(bx=base[0] / K, by=base[1] / K, tx=tip[0] / K, ty=tip[1] / K, w=w / K, lum=lum, area=a / K / K, rgb=[r, g_, b]))
      cv2.line(dbgim, tuple(int(x) for x in base), tuple(int(x) for x in tip), (255, 0, 0), 2)
      cv2.circle(dbgim, tuple(int(x) for x in tip), 5, (255, 255, 0), -1)
json.dump(leaves, open(out, 'w'))
Image.fromarray(dbgim).save(dbg); print(len(leaves), 'leaves')
