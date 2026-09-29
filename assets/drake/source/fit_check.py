"""Silhouette fit check: reference crop vs render (IoU after bbox registration) + overlay.

python3 fit_check.py ref.png render_dir out_dir
"""
import json
import os
import sys

import numpy as np
from PIL import Image

REF, RDIR, OUT = sys.argv[1:4]
CROPS = {"front": (10, 0, 400, 390), "back": (420, 0, 740, 390), "three_quarter": (740, 0, 1448, 395),
         "left": (0, 412, 740, 605), "right": (740, 412, 1448, 605), "top": (40, 628, 1420, 772)}


def mask(im):
    a = np.asarray(im.convert("RGB")).astype(int)
    sat = a.max(2) - a.min(2)
    lum = a.mean(2)
    return (sat > 38) | (lum > 110)


def norm(m, size=256):
    ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    crop = m[y0:y1 + 1, x0:x1 + 1]
    h, w = crop.shape
    s = size / max(h, w)
    im = Image.fromarray((crop * 255).astype(np.uint8)).resize((max(1, int(w * s)), max(1, int(h * s))))
    canvas = np.zeros((size, size), bool)
    arr = np.asarray(im) > 127
    oy, ox = (size - arr.shape[0]) // 2, (size - arr.shape[1]) // 2
    canvas[oy:oy + arr.shape[0], ox:ox + arr.shape[1]] = arr
    return canvas, (x1 - x0) / (y1 - y0)


ref = Image.open(REF)
report = {}
tiles = []
for name, box in CROPS.items():
    rm, rasp = norm(mask(ref.crop(box)))
    p = os.path.join(RDIR, f"{name}.png")
    if not os.path.exists(p):
        continue
    mm, masp = norm(mask(Image.open(p)))
    iou = (rm & mm).sum() / max((rm | mm).sum(), 1)
    report[name] = {"iou": round(float(iou), 3), "ref_aspect_w_over_h": round(float(rasp), 3), "model_aspect": round(float(masp), 3)}
    ov = np.zeros((256, 256, 3), np.uint8)
    ov[rm & ~mm] = (255, 80, 80)    # reference only  -> red
    ov[mm & ~rm] = (80, 160, 255)   # model only      -> blue
    ov[rm & mm] = (230, 230, 230)
    tiles.append(ov)
os.makedirs(OUT, exist_ok=True)
Image.fromarray(np.concatenate(tiles, 1)).save(os.path.join(OUT, "overlay.png"))
json.dump(report, open(os.path.join(OUT, "fit_report.json"), "w"), indent=1)
print(json.dumps(report, indent=1))
