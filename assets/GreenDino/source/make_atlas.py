"""Procedural stud-block texture atlas for the Green Dino.

1024x1024 atlas = 8x8 patches of 128px; each patch = 4x4 blocks of 32px.
Every block gets a bevel and a centred square Roblox-style stud (painted, not modelled).
"""
import json, os, random
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.dirname(os.path.abspath(__file__))
B = 32            # px per block
P = 4             # blocks per patch
S = 1024
rng = random.Random(7)

def hx(h): h = h.lstrip('#'); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def mul(c, f): return tuple(max(0, min(255, int(v * f))) for v in c)
def mix(a, b, t): return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))

PAL = {
  # sampled from the reference sheet (k-means), lifted to albedo
  'camo':    [('#35502a', 5), ('#26381f', 4), ('#4e6630', 3.5), ('#262b2a', 3.5), ('#303d33', 2.5), ('#4d3d29', 1.6), ('#6d8a32', 1.0), ('#3c4632', 2), ('#8a6a44', 0.9), ('#b08a5a', 0.5)],
  'legcamo': [('#2a3c26', 4), ('#2c3232', 4), ('#3e5a2c', 3), ('#4f4030', 2), ('#5c7436', 2), ('#243029', 2)],
  'cream':   [('#f2d19e', 5), ('#e8c28c', 4), ('#dfb57c', 2)],
  'tan':     [('#deae78', 4), ('#c99762', 3), ('#b88452', 2), ('#e8c490', 2), ('#7a5a3a', 0.8)],
  'red':     [('#b72d2a', 4), ('#a02624', 3), ('#c63a33', 2)],
  'tongue':  [('#cc4b46', 4), ('#d85a50', 2), ('#b83e3a', 2)],
  'darkred': [('#5e1416', 3), ('#4a0f12', 3), ('#722024', 2)],
  'dark':    [('#141414', 1)],
}

def pick(cat):
  items = PAL[cat]; tot = sum(w for _, w in items); r = rng.uniform(0, tot)
  for c, w in items:
    r -= w
    if r <= 0: return hx(c)
  return hx(items[-1][0])

def noise_fill(d, box, col, amt=10):
  x0, y0, x1, y1 = box
  for y in range(y0, y1):
    for x in range(x0, x1):
      if rng.random() < 0.35:
        f = 1 + rng.uniform(-amt, amt) / 255 * 2.2
        d.point((x, y), fill=mul(col, f))

def inlet(d, cx, cy, sz, col):
  """Roblox inlet stud (see stud reference images): recessed square, dark top wall, light bottom wall"""
  a0, b0, a1, b1 = cx - sz // 2, cy - sz // 2, cx + sz // 2, cy + sz // 2
  d.rectangle([a0, b0, a1, b1], fill=mul(col, 0.94))                 # recessed floor
  d.rectangle([a0, b0, a1, b0 + 1], fill=mul(col, 0.66))             # top wall in shadow
  d.rectangle([a0, b0, a0 + 1, b1], fill=mul(col, 0.76))             # left wall
  d.rectangle([a0 + 1, b1 - 1, a1, b1], fill=mul(col, 1.13))         # bottom wall catches light
  d.rectangle([a1 - 1, b0 + 1, a1, b1], fill=mul(col, 1.05))         # right wall

def block(d, x0, y0, w, h, col, moss=0.0, stud=True):
  """one stud cell: flat colour (no outline, like the reference) + centred inlet"""
  d.rectangle([x0, y0, x0 + w - 1, y0 + h - 1], fill=col)
  if stud: inlet(d, x0 + w // 2, y0 + h // 2, max(10, int(min(w, h) * 0.42)), col)

def patch_blocks(d, px, py, cat, big=0.35, moss=0.0):
  ox, oy = px * P * B, py * P * B
  used = [[False] * P for _ in range(P)]
  if False:  # single-size cells only (inlet grid is regular in the stud reference)
    bx, by = rng.randint(0, P - 2), rng.randint(0, P - 2)
    for a in range(2):
      for b in range(2): used[by + b][bx + a] = True
    block(d, ox + bx * B, oy + by * B, 2 * B, 2 * B, pick(cat), moss)
  for by in range(P):
    for bx in range(P):
      if used[by][bx]: continue
      col = pick(cat)
      m = moss if rng.random() < 0.5 else 0
      block(d, ox + bx * B, oy + by * B, B, B, col, m)

def stone_patch(d, px, py):
  """spike slab: flat stone with the same inlet studs; moss shows as whole green cells near the base"""
  ox, oy = px * P * B, py * P * B
  base = hx(rng.choice(['#b39c80', '#a8977f', '#9c8c78', '#bba486']))
  for by in range(P):
    for bx in range(P):
      c = base
      if rng.random() < 0.12 + 0.22 * (by / (P - 1)): c = hx(rng.choice(['#5f8a2a', '#6f9a30', '#4f7424']))
      block(d, ox + bx * B, oy + by * B, B, B, c)

def smooth_patch(d, px, py, col, dark, stud=True):
  """teeth / claws: one smooth cream element with a soft gradient and a single stud"""
  ox, oy = px * P * B, py * P * B; W = P * B
  for y in range(W):
    t = y / W
    d.line([ox, oy + y, ox + W - 1, oy + y], fill=mix(col, dark, t * 0.25))
  if stud and False:
    for (cx, cy) in [(W // 2, W // 2)]:
      s = 22; a0, b0 = ox + cx - s // 2, oy + cy - s // 2
      d.rectangle([a0 + 3, b0 + 3, a0 + s + 3, b0 + s + 3], fill=mul(col, 0.8))
      d.rectangle([a0, b0, a0 + s, b0 + s], fill=mul(col, 1.03))
      d.line([a0, b0, a0 + s, b0], fill=mul(col, 1.15)); d.line([a0 + s, b0, a0 + s, b0 + s], fill=mul(col, 0.72))

def eye_patch(d, px, py):
  ox, oy = px * P * B, py * P * B
  for by in range(P):
    for bx in range(P):
      x0, y0 = ox + bx * B, oy + by * B
      d.rectangle([x0, y0, x0 + B - 1, y0 + B - 1], fill=hx('#7a2a10'))
      d.rectangle([x0 + 3, y0 + 3, x0 + B - 4, y0 + B - 4], fill=hx('#e05a10'))
      d.rectangle([x0 + 7, y0 + 7, x0 + B - 8, y0 + B - 8], fill=hx('#ffa21e'))
      d.rectangle([x0 + 11, y0 + 11, x0 + B - 12, y0 + B - 12], fill=hx('#ffe07a'))

LAYOUT = {}
def alloc(cat, n):
  start = sum(len(v) for v in LAYOUT.values())
  LAYOUT[cat] = list(range(start, start + n))

for cat, n in [('camo', 18), ('legcamo', 6), ('cream', 8), ('tan', 6), ('red', 3), ('tongue', 2), ('darkred', 2),
               ('stone', 10), ('eye', 1), ('dark', 1), ('tooth', 3), ('claw', 3), ('camomoss', 1)]:
  alloc(cat, n)
assert sum(len(v) for v in LAYOUT.values()) <= 64

img = Image.new('RGB', (S, S), (0, 0, 0))
emi = Image.new('L', (S, S), 0)
d = ImageDraw.Draw(img)
for cat, ids in LAYOUT.items():
  for p in ids:
    px, py = p % 8, p // 8
    if cat == 'camo':      patch_blocks(d, px, py, 'camo', 0)
    elif cat == 'camomoss': patch_blocks(d, px, py, 'camo', 0)
    elif cat == 'legcamo': patch_blocks(d, px, py, 'legcamo', 0)
    elif cat == 'cream':   patch_blocks(d, px, py, 'cream', 0.25)
    elif cat == 'tan':     patch_blocks(d, px, py, 'tan', 0.3)
    elif cat in ('red', 'tongue', 'darkred', 'dark'): patch_blocks(d, px, py, cat, 0.2)
    elif cat == 'stone':   stone_patch(d, px, py)
    elif cat == 'eye':
      eye_patch(d, px, py)
      ImageDraw.Draw(emi).rectangle([px * 128, py * 128, px * 128 + 127, py * 128 + 127], fill=255)
    elif cat == 'tooth':   smooth_patch(d, px, py, hx('#f6dcae'), hx('#c9a070'))
    elif cat == 'claw':    smooth_patch(d, px, py, hx('#f4d6a2'), hx('#b8905e'))

img.save(os.path.join(OUT, '..', 'GreenDino_Color.png'))
emi.save(os.path.join(OUT, '..', 'GreenDino_Emissive.png'))
json.dump(LAYOUT, open(os.path.join(OUT, 'atlas_regions.json'), 'w'), indent=1)
print('atlas ok', {k: len(v) for k, v in LAYOUT.items()})
