"""Multiview fit: reference view mask vs flat render mask (bbox-registered). Writes overlay + json."""
import sys, os, json
import numpy as np
from PIL import Image
ref = np.array(Image.open(sys.argv[1]).convert("RGB")).astype(int)
rd = sys.argv[2]
BG = np.array([27, 31, 41])
BOX = {"left": (20, 395, 705, 603), "front": (615, 15, 990, 352), "back": (995, 15, 1420, 352), "top": (35, 650, 690, 840)}
def labels(a, bg, thr):
    d = np.abs(a - bg).sum(-1); fg = d > thr
    L = np.zeros(a.shape[:2], np.uint8); L[fg] = 2
    L[fg & (a[..., 0] > 120) & (a[..., 0] > a[..., 2])] = 1
    L[fg & (a[..., 1] > 140) & (a[..., 2] > 170) & (a[..., 0] < 140)] = 3
    return L
def crop_bbox(L):
    ys, xs = np.nonzero(L); return L[ys.min():ys.max()+1, xs.min():xs.max()+1], (xs.min(), ys.min(), xs.max(), ys.max())
rep = {}
for v, (x0, y0, x1, y1) in BOX.items():
    p = os.path.join(rd, f"flat_{v}.png")
    if not os.path.exists(p): continue
    Lr, bb_r = crop_bbox(labels(ref[y0:y1, x0:x1], BG, 45))
    rn = np.array(Image.open(p).convert("RGB")).astype(int)
    Ln, bb_n = crop_bbox(labels(rn, np.array([0, 0, 0]), 30))
    H, W = 300, int(300 * Lr.shape[1] / Lr.shape[0])
    A = np.array(Image.fromarray(Lr).resize((W, H), Image.NEAREST))
    B = np.array(Image.fromarray(Ln).resize((W, H), Image.NEAREST))
    ma, mb = A > 0, B > 0
    iou = (ma & mb).sum() / (ma | mb).sum()
    lab_agree = ((A == B) & ma & mb).sum() / max((ma & mb).sum(), 1)
    ov = np.zeros((H, W, 3), np.uint8)
    ov[ma & ~mb] = (255, 60, 60); ov[mb & ~ma] = (60, 255, 60); ov[ma & mb] = (200, 200, 200)
    ov[ma & mb & (A != B)] = (255, 200, 0)
    Image.fromarray(ov).save(os.path.join(rd, f"overlay_{v}.png"))
    rep[v] = dict(iou=round(float(iou), 3), label_agreement=round(float(lab_agree), 3),
                  ref_aspect=round(Lr.shape[1] / Lr.shape[0], 3), render_aspect=round(Ln.shape[1] / Ln.shape[0], 3))
json.dump(rep, open(os.path.join(rd, "multiview_fit_report.json"), "w"), indent=1)
print(json.dumps(rep, indent=1))
