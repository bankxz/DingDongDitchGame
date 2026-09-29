"""Painted stud texture atlas for the Green Dino.

1024x1024 atlas = 4x4 patches of 256px; each patch = 4x4 stud cells of 64px (drawn at 2x, Lanczos-downsampled).
Each category has ONE continuous base colour (no per-cell colour squares, so it doesn't read as pixel art).
Organic detail -- soft camo blotches, grain, moss -- is painted inside each cell and fades out before the
cell edge, so any two cells placed side by side on the mesh join seamlessly. On top, every cell gets a
Roblox "inlet" stud (recessed square) shaded over the colour underneath.
"""
import json, os
import numpy as np
from PIL import Image

OUT = os.path.dirname(os.path.abspath(__file__))
SS = 2                 # supersample factor
C = 64 * SS            # px per stud cell while drawing
P = 4                  # cells per patch side
NP = 4                 # patches per atlas side
S = C * P * NP
rng = np.random.default_rng(7)

def hx(h): h = h.lstrip('#'); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float) / 255.0

yy, xx = np.mgrid[0:C, 0:C].astype(float) + 0.5
EDGE = np.minimum(np.minimum(xx, C - xx), np.minimum(yy, C - yy)) / C          # 0 at border -> 0.5 centre
WINDOW = np.clip((EDGE - 0.05) / 0.17, 0, 1) ** 2 * (3 - 2 * np.clip((EDGE - 0.05) / 0.17, 0, 1))  # fades to 0 at edges

def blur(a, sigma):
  """separable gaussian blur (numpy only)"""
  r = int(3 * sigma); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2); k /= k.sum()
  a = np.apply_along_axis(lambda m: np.convolve(np.pad(m, r, mode='reflect'), k, 'valid'), 0, a)
  return np.apply_along_axis(lambda m: np.convolve(np.pad(m, r, mode='reflect'), k, 'valid'), 1, a)

def blob_mask(n_lobes, rad, sigma):
  m = np.zeros((C, C))
  cx, cy = rng.uniform(0.22, 0.78, 2) * C
  for _ in range(n_lobes):
    ox, oy = rng.normal(0, rad * 0.45, 2)
    r = rad * rng.uniform(0.55, 1.0)
    m = np.maximum(m, ((xx - cx - ox) ** 2 + (yy - cy - oy) ** 2 < r * r).astype(float))
  return np.clip(blur(m, sigma), 0, 1)

def grain(amount, sigma=1.2):
  g = blur(rng.normal(0, 1, (C, C)), sigma); g /= (g.std() + 1e-6)
  return 1 + amount * g                          # fine high-frequency grain: no visible seam between any two cells

# ---------------------------------------------------------------- per-category cell painters
BASE = {
  'camo': hx('#3b5a2d'), 'legcamo': hx('#314a28'), 'cream': hx('#f0d09c'), 'tan': hx('#d7a870'),
  'red': hx('#b52e2a'), 'tongue': hx('#cc4d47'), 'darkred': hx('#5c1618'), 'stone': hx('#b09a80'),
  'tooth': hx('#f4dcae'),
}
BLOTCH = {   # (colours, blobs per cell range, radius range (fraction of cell), opacity)
  'camo':    ([hx('#2b4022'), hx('#4f6a30'), hx('#33403a'), hx('#465a31'), hx('#56492f')], (0, 2), (0.2, 0.32), 0.5),
  'legcamo': ([hx('#23341d'), hx('#43592b'), hx('#2e3530'), hx('#4a3e2c')], (0, 2), (0.2, 0.32), 0.5),
  'tan':     ([hx('#c49058'), hx('#e2bb85'), hx('#b8824e')], (0, 2), (0.15, 0.28), 0.5),
  'cream':   ([hx('#e6c28b'), hx('#f7dcb0')], (0, 2), (0.18, 0.3), 0.35),
  'red':     ([hx('#9a2222'), hx('#c53c35')], (0, 2), (0.18, 0.3), 0.4),
  'tongue':  ([hx('#b83e3a'), hx('#dd625a')], (0, 2), (0.18, 0.3), 0.4),
  'darkred': ([hx('#45100f'), hx('#72201f')], (0, 2), (0.18, 0.3), 0.4),
  'stone':   ([hx('#9c8a73'), hx('#c4b092'), hx('#a39079')], (0, 2), (0.2, 0.32), 0.45),
}
MOSS = [hx('#5e8a2a'), hx('#72a034'), hx('#4d7424')]

def paint_cell(cat):
  img = np.ones((C, C, 3)) * BASE[cat]
  cols, (n0, n1), (r0, r1), op = BLOTCH.get(cat, ([], (0, 0), (0, 0), 0))
  for _ in range(rng.integers(n0, n1 + 1)):
    m = blob_mask(rng.integers(2, 5), rng.uniform(r0, r1) * C, C * 0.06) * WINDOW * op
    col = cols[rng.integers(len(cols))]
    img = img * (1 - m[..., None]) + col * m[..., None]
  if cat in ('camo', 'stone') and rng.random() < (0.12 if cat == 'camo' else 0.35):   # moss tufts
    m = blob_mask(rng.integers(3, 6), rng.uniform(0.12, 0.2) * C, C * 0.04) * WINDOW * 0.65
    img = img * (1 - m[..., None]) + MOSS[rng.integers(3)] * m[..., None]
  img *= grain(0.025 if cat != 'tooth' else 0.012, 0.9)[..., None]
  if cat != 'tooth': inlet(img)
  return img

def inlet(img):
  """Roblox inlet stud (stud reference images): recessed square, shadowed top wall, lit bottom wall.
  Applied as shading over whatever colour is underneath."""
  sz = int(C * 0.42); t = max(3, sz // 9)
  a0 = (C - sz) // 2; a1 = a0 + sz
  sh = np.ones((C, C))
  sh[a0:a1, a0:a1] = 0.93                     # floor
  sh[a0:a0 + t, a0:a1] = 0.64                 # top wall (shadow)
  sh[a0:a1, a0:a0 + t] = 0.76                 # left wall
  sh[a1 - t:a1, a0 + t:a1] = 1.14             # bottom wall (catches light)
  sh[a0 + t:a1 - t, a1 - t:a1] = 1.05         # right wall
  img *= sh[..., None]

def eye_cell():
  d = np.hypot(xx - C / 2, yy - C / 2) / (C / 2)                          # round glow
  core, mid, rim = hx('#fff0a0'), hx('#ffa21e'), hx('#b8400e')
  t = np.clip(d, 0, 1)[..., None]
  img = np.where(t < 0.45, core * (1 - t / 0.45) + mid * (t / 0.45), mid * (1 - (t - 0.45) / 0.55) + rim * ((t - 0.45) / 0.55))
  return img

# ---------------------------------------------------------------- layout (explicit so caps get seamless strips)
LAYOUT = {'camo': [0, 1, 2], 'legcamo': [3, 11], 'cream': [4, 5], 'tan': [6, 7], 'red': [8], 'tongue': [9],
          'darkred': [10], 'stone': [12, 13], 'eye': [14], 'tooth': [15]}
DRAWN = list(LAYOUT)
atlas = np.zeros((S, S, 3)); emi = np.zeros((S, S))
for cat in DRAWN:
  for p in LAYOUT[cat]:
    px, py = p % NP, p // NP
    for by in range(P):
      for bx in range(P):
        y0, x0 = (py * P + by) * C, (px * P + bx) * C
        atlas[y0:y0 + C, x0:x0 + C] = eye_cell() if cat == 'eye' else paint_cell(cat)
        if cat == 'eye': emi[y0:y0 + C, x0:x0 + C] = 1
LAYOUT.update({'claw': LAYOUT['tooth'], 'dark': LAYOUT['darkred'], 'camomoss': LAYOUT['camo']})   # shared patches

def save(a, path, mode):
  im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), mode)
  im.resize((S // SS, S // SS), Image.LANCZOS).save(path)
save(atlas, os.path.join(OUT, '..', 'GreenDino_Color.png'), 'RGB')
save(emi, os.path.join(OUT, '..', 'GreenDino_Emissive.png'), 'L')
json.dump(LAYOUT, open(os.path.join(OUT, 'atlas_regions.json'), 'w'), indent=1)
print('atlas ok', {k: len(v) for k, v in LAYOUT.items()})
