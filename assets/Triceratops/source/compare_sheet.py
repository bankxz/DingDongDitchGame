"""
Compose render-vs-reference comparison sheets and approximate silhouette IoU.

    python3 compare_sheet.py

Needs Pillow + NumPy + OpenCV (opencv-python-headless). Reads ../previews/view_*.png,
writes ../previews/comparison_sheet.png, ../previews/model_sheet.png,
../previews/anim_<Action>.png and ../validation/silhouette_report.json.
"""
import glob
import json
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET = os.path.dirname(HERE)
PREV = os.path.join(ASSET, 'previews')
BG = (122, 121, 126)

# panel crops of the reference sheet (x0, y0, x1, y1), labels excluded
REF_PANELS = {
    'front': (20, 0, 600, 495),
    'right': (630, 0, 1530, 495),
    'left': (0, 545, 640, 955),
    'back': (655, 545, 1100, 955),
    'top': (1110, 545, 1530, 955),
}


def on_bg(path):
    im = Image.open(path).convert('RGBA')
    bg = Image.new('RGBA', im.size, BG + (255,))
    return Image.alpha_composite(bg, im).convert('RGB')


def fit(im, w, h):
    im = im.copy()
    im.thumbnail((w, h))
    out = Image.new('RGB', (w, h), BG)
    out.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return out


def ref_mask(rgb):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    m = ((hsv[..., 1] > 45) | (hsv[..., 2] > 215)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    big = max(cnts, key=cv2.contourArea)
    out = np.zeros_like(m)
    cv2.drawContours(out, [big], -1, 1, -1)
    return out


def norm_mask(m, size=256):
    ys, xs = np.nonzero(m)
    crop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return cv2.resize(crop.astype(np.uint8), (size, size), interpolation=cv2.INTER_NEAREST), \
        (xs.max() - xs.min() + 1) / (ys.max() - ys.min() + 1)


def main():
    ref = np.array(Image.open(os.path.join(HERE, 'reference_triceratops.webp')).convert('RGB'))
    W, H = 520, 400
    sheet = Image.new('RGB', (W * 2 + 30, (H + 30) * len(REF_PANELS) + 10), (60, 60, 64))
    d = ImageDraw.Draw(sheet)
    report = {}
    for i, (name, (x0, y0, x1, y1)) in enumerate(REF_PANELS.items()):
        r = Image.fromarray(ref[y0:y1, x0:x1])
        m = on_bg(os.path.join(PREV, f'view_{name}.png'))
        if name == 'left':
            m = m.transpose(Image.FLIP_LEFT_RIGHT)
        y = 10 + i * (H + 30)
        sheet.paste(fit(r, W, H), (10, y + 20))
        sheet.paste(fit(m, W, H), (W + 20, y + 20))
        d.text((12, y + 4), f'REFERENCE  {name}', fill=(255, 255, 255))
        d.text((W + 22, y + 4), f'BUILT MODEL  {name}' + (' (true left side, mirrored)' if name == 'left' else ''), fill=(255, 255, 255))

        rm, r_aspect = norm_mask(ref_mask(ref[y0:y1, x0:x1]))
        alpha = np.array(Image.open(os.path.join(PREV, f'view_{name}.png')).convert('RGBA'))[..., 3]
        mm, m_aspect = norm_mask((alpha > 128).astype(np.uint8))
        if name == 'left':           # sheet shows the same side twice; compare our true left mirrored
            mm = mm[:, ::-1]
        inter = np.logical_and(rm, mm).sum(); union = np.logical_or(rm, mm).sum()
        report[name] = dict(silhouette_iou_bbox_normalised=round(float(inter / union), 3),
                            ref_aspect_w_over_h=round(float(r_aspect), 3),
                            model_aspect_w_over_h=round(float(m_aspect), 3))
    sheet.save(os.path.join(PREV, 'comparison_sheet.png'))

    # clean 5-view model sheet in the same layout as the reference
    ms = Image.new('RGB', (1536, 1024), BG)
    dm = ImageDraw.Draw(ms)
    for name, (x0, y0, x1, y1) in REF_PANELS.items():
        ms.paste(fit(on_bg(os.path.join(PREV, f'view_{name}.png')), x1 - x0, y1 - y0), (x0, y0))
        dm.text((x0 + (x1 - x0) // 2 - 30, y1 + 12), f'{name.upper()} VIEW', fill=(255, 255, 255))
    ms.save(os.path.join(PREV, 'model_sheet.png'))

    # animation contact sheets
    frames = sorted(glob.glob(os.path.join(PREV, 'frames', '*.png')))
    by_action = {}
    for f in frames:
        by_action.setdefault(os.path.basename(f).split('_')[0], []).append(f)
    for act, fs in by_action.items():
        tw, th = 360, 270
        cs = Image.new('RGB', (tw * 4, th * ((len(fs) + 3) // 4)), BG)
        dc = ImageDraw.Draw(cs)
        for k, f in enumerate(fs):
            cs.paste(fit(on_bg(f), tw, th), ((k % 4) * tw, (k // 4) * th))
            dc.text(((k % 4) * tw + 6, (k // 4) * th + 6), os.path.basename(f)[:-4], fill=(255, 255, 255))
        cs.save(os.path.join(PREV, f'anim_{act}.png'))

    with open(os.path.join(ASSET, 'validation', 'silhouette_report.json'), 'w') as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
