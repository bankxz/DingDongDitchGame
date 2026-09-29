"""Side-by-side + silhouette IoU of renders vs the reference sheet panels.

python3 tools/blender/compare_to_reference.py <ref_dir> <render_dir> <mask_dir> <out_png>
ref_dir holds <view>.png and <view>_mask.png crops of the reference sheet.
IoU is computed after normalising both silhouettes to their bounding boxes (camera-scale independent).
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

ref_dir, ren_dir, mask_dir, out_png = sys.argv[1:5]
VIEWS = ["hero", "front", "back", "left", "right", "top", "bottom"]
report = {}
rows = []
for v in VIEWS:
    rp, xp = os.path.join(ref_dir, v + ".png"), os.path.join(ren_dir, v + ".png")
    if not (os.path.exists(rp) and os.path.exists(xp)):
        continue
    ref = Image.open(rp).convert("RGB")
    ren = Image.open(xp).convert("RGB").resize(ref.size)
    mp = os.path.join(mask_dir, v + ".png")
    iou = None
    if os.path.exists(mp) and v not in ("hero",):
        rm = cv2.imread(os.path.join(ref_dir, v + "_mask.png"), 0) > 0
        a = np.array(Image.open(mp).convert("RGBA"))[..., 3] > 20

        def norm(m):
            ys, xs = np.nonzero(m)
            c = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8) * 255
            return cv2.resize(c, (256, 256), interpolation=cv2.INTER_NEAREST) > 0, (xs.max() - xs.min()) / max(1, ys.max() - ys.min())

        rn, rasp = norm(rm)
        an, aasp = norm(a)
        iou = float((rn & an).sum() / max(1, (rn | an).sum()))
        report[v] = {"iou_bbox_normalised": round(iou, 3), "aspect_ref": round(float(rasp), 3),
                     "aspect_render": round(float(aasp), 3)}
        ov = np.zeros((256, 256, 3), np.uint8)
        ov[rn] = (255, 60, 60)
        ov[an] += np.array((0, 200, 255), np.uint8)
        Image.fromarray(ov).save(os.path.join(mask_dir, v + "_overlay.png"))
    h = 300
    wr = int(ref.width * h / ref.height)
    row = Image.new("RGB", (wr * 2 + 30, h + 26), (20, 20, 28))
    row.paste(ref.resize((wr, h)), (0, 26))
    row.paste(ren.resize((wr, h)), (wr + 30, 26))
    d = ImageDraw.Draw(row)
    d.text((6, 6), "REFERENCE: " + v.upper(), fill=(255, 255, 255))
    d.text((wr + 36, 6), "MODEL: " + v.upper() + (f"   silhouette IoU {iou:.2f}" if iou is not None else ""),
           fill=(255, 255, 255))
    rows.append(row)
W = max(r.width for r in rows)
sheet = Image.new("RGB", (W, sum(r.height for r in rows)), (20, 20, 28))
y = 0
for r in rows:
    sheet.paste(r, (0, y))
    y += r.height
sheet.save(out_png)
print(json.dumps(report, indent=1))
