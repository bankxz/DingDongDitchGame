"""Builds the 1024x1024 stud texture atlas for the Ice Dragon.

Stud relief comes from dudeax/Roblox-HD-Studs (MIT) 'Studs 2x2' AO diffuse +
normal maps; the relief is baked into the colour so it reads with a plain
MeshPart.TextureID, and a matching normal atlas is written for SurfaceAppearance.
"""
import json, sys, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

STUDS = sys.argv[1]            # path to Roblox-HD-Studs checkout
OUT = sys.argv[2]              # output dir
S = 1024
PX = 32                        # pixels per stud inside the atlas

PAL = {
    'navy':  (0x07, 0x35, 0x88),
    'royal': (0x16, 0x57, 0xfc),
    'cyan':  (0x4d, 0xd9, 0xfe),
    'ice':   (0xd8, 0xef, 0xff),
    'gold':  (0xff, 0xcd, 0x53),
    'white': (0xee, 0xf3, 0xfa),
    'red':   (0xb8, 0x14, 0x3a),
}

# slot name -> (x, y, w, h) in pixels, origin top-left
SLOTS = {
    'navy':   (0, 0, 512, 512),
    'white':  (512, 0, 512, 256),
    'ice':    (512, 256, 512, 256),
    'royal':  (0, 512, 512, 256),
    'gold':   (512, 512, 256, 128),
    'goldS':  (768, 512, 256, 128),   # gold with studs
    'crystal':(0, 768, 256, 256),
    'red':    (256, 768, 128, 128),
    'tooth':  (384, 768, 128, 128),
    'eye':    (256, 896, 128, 128),
    'gem':    (384, 896, 128, 128),
    'dark':   (512, 640, 128, 128),   # throat / nostrils
    'royalS': (0, 768 - 0, 0, 0),
}
del SLOTS['royalS']
STUDDED = {'navy', 'white', 'ice', 'royal', 'goldS'}

def load(p, size):
    return np.asarray(Image.open(p).convert('RGBA').resize((size, size), Image.LANCZOS)).astype(np.float32) / 255.0

tile = 2 * PX                                   # 2x2 studs per source tile
ao = load(os.path.join(STUDS, '2x2 Textures/Diffuse Maps/Studs 2x2 AO Diffuse.png'), tile)[..., 0]
nrm = load(os.path.join(STUDS, '2x2 Textures/Smooth/Studs 2x2 Normal.png'), tile)[..., :3] * 2 - 1
L = np.array([-0.45, 0.55, 0.70]); L /= np.linalg.norm(L)   # light from top-left, OpenGL-style +Y up
lam = np.clip((nrm * L).sum(-1), 0, 1)
flat = float(L[2])
shade_tile = np.clip(0.80 + 0.20 * ao, 0, 1) * (1.0 + 0.9 * (lam - flat))
inlet = load(os.path.join(STUDS, '2x2 Textures/Diffuse Maps/Inlets 2x2 AO Diffuse.png'), tile)[..., 0]
stud_mask = np.clip((inlet.max() - inlet) / max(1e-6, inlet.max() - inlet.min()) * 1.6, 0, 1)
TOP_TINT = {'navy': ((0x1a, 0x4c, 0xb8), 0.55)}   # brighter blue stud tops like the reference blocks

img = np.zeros((S, S, 3), np.float32)
nmap = np.zeros((S, S, 3), np.float32); nmap[...] = (0.5, 0.5, 1.0)
col = lambda c: np.array(c, np.float32) / 255.0

for name, (x, y, w, h) in SLOTS.items():
    base = name.rstrip('S') if name in ('goldS',) else name
    if name in STUDDED:
        c = col(PAL[base if base in PAL else 'navy'])
        reps = (h // tile + 1, w // tile + 1)
        sh = np.tile(shade_tile, reps)[:h, :w]
        nn = np.tile(nrm, reps + (1,))[:h, :w]
        cc = np.broadcast_to(c, (h, w, 3)).copy()
        if name in TOP_TINT:
            tc, a = TOP_TINT[name]
            m = np.tile(stud_mask, reps)[:h, :w][..., None] * a
            cc = cc * (1 - m) + col(tc)[None, None] * m
        img[y:y+h, x:x+w] = np.clip(cc * sh[..., None], 0, 1)
        nmap[y:y+h, x:x+w] = nn * 0.5 + 0.5

def draw_slot(name, fn):
    x, y, w, h = SLOTS[name]
    im = Image.new('RGB', (w, h)); d = ImageDraw.Draw(im); fn(d, w, h, im)
    img[y:y+h, x:x+w] = np.asarray(im).astype(np.float32) / 255.0

def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def gold(d, w, h, im):
    for j in range(h):
        t = j / (h - 1)
        d.line([(0, j), (w, j)], fill=lerp((0xff, 0xe0, 0x80), (0xd8, 0x98, 0x20), t))
    d.rectangle([0, 0, w - 1, h - 1], outline=(0xb0, 0x78, 0x10), width=3)
draw_slot('gold', gold)

def crystal(d, w, h, im):
    # v=0 (bottom row) is shard base, v=1 (top) is the tip; u across a facet
    for j in range(h):
        t = 1 - j / (h - 1)                       # 0 base -> 1 tip
        for i in range(w):
            u = abs(i / (w - 1) - 0.5) * 2        # 0 centre ridge -> 1 facet edge
            c = lerp((0x1c, 0x8c, 0xf0), (0x4d, 0xd9, 0xfe), min(1, t * 1.3))
            c = lerp(c, (0xe6, 0xfb, 0xff), max(0, 1 - u * 3.2) * 0.75)     # bright ridge
            c = lerp(c, (0xff, 0xff, 0xff), max(0, (u - 0.9) * 10) * 0.8)   # glowing facet edge
            c = lerp(c, (0xff, 0xff, 0xff), max(0, t - 0.75) * 1.6)         # white hot tip
            d.point((i, j), fill=c)
    # internal fracture lines like the reference shards
    for a, b in [((w*0.5, h), (w*0.2, h*0.35)), ((w*0.5, h*0.7), (w*0.85, h*0.3)), ((w*0.3, h*0.9), (w*0.5, h*0.05))]:
        d.line([a, b], fill=(0xd0, 0xf6, 0xff), width=2)
draw_slot('crystal', crystal)

def red(d, w, h, im):
    for j in range(h):
        d.line([(0, j), (w, j)], fill=lerp((0x7a, 0x06, 0x22), (0xd0, 0x20, 0x48), j / (h - 1)))
draw_slot('red', red)

def tooth(d, w, h, im):
    for j in range(h):
        d.line([(0, j), (w, j)], fill=lerp((0xff, 0xff, 0xff), (0xc6, 0xd0, 0xde), j / (h - 1)))
draw_slot('tooth', tooth)

def eye(d, w, h, im):
    im.paste((0x4d, 0xd9, 0xfe), [0, 0, w, h])
    for r in range(w // 2, 0, -1):
        t = 1 - r / (w / 2)
        d.ellipse([w/2 - r, h/2 - r, w/2 + r, h/2 + r], fill=lerp((0x4d, 0xd9, 0xfe), (0xff, 0xff, 0xff), t ** 0.7))
draw_slot('eye', eye)

def gem(d, w, h, im):
    im.paste((0x2a, 0xb4, 0xfb), [0, 0, w, h])
    c = (w / 2, h / 2)
    tris = [((0, 0), (w, 0)), ((w, 0), (w, h)), ((w, h), (0, h)), ((0, h), (0, 0))]
    shades = [(0x9a, 0xee, 0xff), (0x4d, 0xd9, 0xfe), (0x16, 0x8c, 0xf0), (0x6c, 0xe2, 0xff)]
    for (a, b), s in zip(tris, shades):
        d.polygon([a, b, c], fill=s)
    d.line([(0, 0), (w, h)], fill=(0xe8, 0xfc, 0xff), width=2)
    d.line([(w, 0), (0, h)], fill=(0xe8, 0xfc, 0xff), width=2)
draw_slot('gem', gem)

def dark(d, w, h, im):
    im.paste((0x3a, 0x02, 0x14), [0, 0, w, h])
draw_slot('dark', dark)

Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, 'IceDragon_Color.png'))
Image.fromarray((np.clip(nmap, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, 'IceDragon_Normal.png'))
json.dump({'size': S, 'px_per_stud': PX, 'slots': SLOTS, 'studded': sorted(STUDDED)},
          open(os.path.join(OUT, 'atlas_regions.json'), 'w'), indent=1)
print('atlas written')
