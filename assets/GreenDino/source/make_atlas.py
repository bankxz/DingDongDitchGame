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

def block(d, x0, y0, w, h, col, moss=0.0, stud=True):
  """one studded block occupying w*h px starting at x0,y0"""
  x1, y1 = x0 + w - 1, y0 + h - 1
  d.rectangle([x0, y0, x1, y1], fill=col)
  noise_fill(d, (x0, y0, x1 + 1, y1 + 1), col)
  if moss > 0:
    mc = hx(rng.choice(['#62902a', '#74a032', '#557f26']))
    for _ in range(int(w * h * moss / 6)):
      mx, my = rng.randint(x0, x1), rng.randint(y0, y0 + h // 2)
      r = rng.randint(1, 3)
      d.ellipse([mx - r, my - r, mx + r, my + r], fill=mc)
  # bevel: light top/left, dark bottom/right, dark gap line
  d.line([x0 + 1, y0 + 1, x1 - 1, y0 + 1], fill=mul(col, 1.28))
  d.line([x0 + 1, y0 + 1, x0 + 1, y1 - 1], fill=mul(col, 1.18))
  d.line([x0 + 1, y1 - 1, x1 - 1, y1 - 1], fill=mul(col, 0.62))
  d.line([x1 - 1, y0 + 1, x1 - 1, y1 - 1], fill=mul(col, 0.7))
  d.rectangle([x0, y0, x1, y1], outline=mul(col, 0.38))
  if stud:
    s = max(8, int(min(w, h) * 0.34))
    cx, cy = x0 + w // 2, y0 + h // 2
    a0, b0, a1, b1 = cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2
    d.rectangle([a0 + 2, b0 + 2, a1 + 2, b1 + 2], fill=mul(col, 0.72))  # drop shadow
    d.rectangle([a0, b0, a1, b1], fill=mul(col, 1.06))
    d.line([a0, b0, a1, b0], fill=mul(col, 1.32)); d.line([a0, b0, a0, b1], fill=mul(col, 1.25))
    d.line([a0, b1, a1, b1], fill=mul(col, 0.66)); d.line([a1, b0, a1, b1], fill=mul(col, 0.7))

def patch_blocks(d, px, py, cat, big=0.35, moss=0.0):
  ox, oy = px * P * B, py * P * B
  used = [[False] * P for _ in range(P)]
  if rng.random() < big:  # one 2x2 chunky block, like the shoulder plates in the ref
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
  """spike slab: tall stone faces, cracks, moss at the base (see DETAIL (SPIKES))"""
  ox, oy = px * P * B, py * P * B; W = P * B
  base = hx(rng.choice(['#b39c80', '#a8977f', '#9c8c78', '#bba486']))
  d.rectangle([ox, oy, ox + W - 1, oy + W - 1], fill=base)
  noise_fill(d, (ox, oy, ox + W, oy + W), base, 14)
  cols = rng.choice([2, 2, 3])
  xs = sorted(rng.sample(range(24, W - 24), cols - 1)) if cols > 1 else []
  edges = [0] + xs + [W]
  for a, b in zip(edges, edges[1:]):
    c = mul(base, rng.uniform(0.86, 1.08))
    d.rectangle([ox + a, oy, ox + b - 1, oy + W - 1], fill=c)
    noise_fill(d, (ox + a, oy, ox + b, oy + W), c, 14)
    d.line([ox + a + 1, oy, ox + a + 1, oy + W], fill=mul(c, 1.22))
    d.line([ox + b - 2, oy, ox + b - 2, oy + W], fill=mul(c, 0.62))
    d.line([ox + b - 1, oy, ox + b - 1, oy + W], fill=mul(c, 0.4))
    # a couple of studs per slab
    for _ in range(rng.randint(1, 2)):
      cx = ox + (a + b) // 2 + rng.randint(-4, 4); cy = oy + rng.randint(20, W - 30); s = 10
      d.rectangle([cx - s // 2 + 2, cy - s // 2 + 2, cx + s // 2 + 2, cy + s // 2 + 2], fill=mul(c, 0.72))
      d.rectangle([cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2], fill=mul(c, 1.05))
      d.line([cx - s // 2, cy - s // 2, cx + s // 2, cy - s // 2], fill=mul(c, 1.3))
      d.line([cx + s // 2, cy - s // 2, cx + s // 2, cy + s // 2], fill=mul(c, 0.68))
  # horizontal cracks
  for _ in range(rng.randint(1, 3)):
    y = oy + rng.randint(15, W - 15)
    d.line([ox + rng.randint(0, 40), y, ox + rng.randint(60, W), y + rng.randint(-3, 3)], fill=mul(base, 0.55))
  # moss at base + streaks, like the reference
  mcs = [hx('#5f8a2a'), hx('#76a034'), hx('#4a6e22')]
  for _ in range(110):
    mx = ox + rng.randint(0, W - 1)
    my = oy + int(W - abs(rng.gauss(0, 30)))
    r = rng.randint(2, 5); d.ellipse([mx - r, my - r, mx + r, my + r], fill=rng.choice(mcs))
  for _ in range(rng.randint(1, 3)):
    mx = ox + rng.randint(10, W - 10); my = oy + rng.randint(10, W // 2)
    for k in range(18):
      r = rng.randint(2, 4)
      d.ellipse([mx - r, my + k * 2 - r, mx + r + rng.randint(0, 3), my + k * 2 + r], fill=rng.choice(mcs))

def smooth_patch(d, px, py, col, dark, stud=True):
  """teeth / claws: one smooth cream element with a soft gradient and a single stud"""
  ox, oy = px * P * B, py * P * B; W = P * B
  for y in range(W):
    t = y / W
    d.line([ox, oy + y, ox + W - 1, oy + y], fill=mix(col, dark, t * 0.55))
  noise_fill(d, (ox, oy, ox + W, oy + W), col, 6)
  d.rectangle([ox, oy, ox + W - 1, oy + W - 1], outline=mul(dark, 0.8))
  if stud:
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
    if cat == 'camo':      patch_blocks(d, px, py, 'camo', 0.4, moss=0.7 if rng.random() < 0.35 else 0)
    elif cat == 'camomoss': patch_blocks(d, px, py, 'camo', 0.3, moss=1.5)
    elif cat == 'legcamo': patch_blocks(d, px, py, 'legcamo', 0.3, moss=0.5 if rng.random() < 0.3 else 0)
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
