"""Build a 1024x1024 colour atlas (+ matching normal atlas) for stud-style Roblox models.

Usage:
  python3 make_stud_atlas.py <Roblox-HD-Studs checkout> <atlas_config.json> <out_dir>

Studded swatches bake the Roblox stud relief (dudeax/Roblox-HD-Studs, MIT) into the
colour so the look survives a plain MeshPart.TextureID; the normal atlas is optional
for SurfaceAppearance. Other swatch kinds: flat, gradient, gold, crystal, eye, gem.
Writes <out>/Color.png, <out>/Normal.png and <out>/atlas_regions.json (slot rects,
px_per_stud, studded slot names) which stud_kit.py reads.
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

STUDS, CFG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
cfg = json.load(open(CFG)); os.makedirs(OUT, exist_ok=True)
S = cfg.get('size', 1024); PX = cfg.get('px_per_stud', 32); STRENGTH = cfg.get('stud_strength', 0.5)
hexc = lambda h: tuple(int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
pal = {k: hexc(v) for k, v in cfg.get('palette', {}).items()}
col = lambda c: np.array(pal.get(c, hexc(c) if isinstance(c, str) and c.startswith('#') else (128, 128, 128)), np.float32) / 255
lerp = lambda a, b, t: tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def load(p, size):
    return np.asarray(Image.open(p).convert('RGBA').resize((size, size), Image.LANCZOS)).astype(np.float32) / 255

tile = 2 * PX                                                   # source tiles are 2x2 studs
ao = load(os.path.join(STUDS, '2x2 Textures/Diffuse Maps/Studs 2x2 AO Diffuse.png'), tile)[..., 0]
inlet = load(os.path.join(STUDS, '2x2 Textures/Diffuse Maps/Inlets 2x2 AO Diffuse.png'), tile)[..., 0]
nrm = load(os.path.join(STUDS, '2x2 Textures/Smooth/Studs 2x2 Normal.png'), tile)[..., :3] * 2 - 1
L = np.array([-0.45, 0.55, 0.70]); L /= np.linalg.norm(L)          # baked light from top-left
lam = np.clip((nrm * L).sum(-1), 0, 1)
shade = np.clip(0.80 + 0.20 * ao, 0, 1) * (1.0 + 0.9 * (lam - L[2]))
shade = 1.0 + STRENGTH * (shade - 1.0)                              # stud opacity / strength
stud_mask = np.clip((inlet.max() - inlet) / max(1e-6, inlet.max() - inlet.min()) * 1.6, 0, 1)
nrm_s = nrm * STRENGTH + np.array([0, 0, 1.0]) * (1 - STRENGTH)
nrm_s /= np.linalg.norm(nrm_s, axis=-1, keepdims=True)

img = np.zeros((S, S, 3), np.float32); img[...] = col(next(iter(pal), '#000000')) if pal else 0
nmap = np.zeros((S, S, 3), np.float32); nmap[...] = (0.5, 0.5, 1.0)
emi = np.zeros((S, S, 3), np.float32)

def paint(rect, fn):
    x, y, w, h = rect
    im = Image.new('RGB', (w, h)); fn(ImageDraw.Draw(im), w, h, im)
    img[y:y + h, x:x + w] = np.asarray(im).astype(np.float32) / 255

def crystal(spec):
    base, tipc = hexc(spec.get('base', '#1c8cf2')), hexc(spec.get('tip', '#7cdcff'))
    def fn(d, w, h, im):
        for j in range(h):
            t = 1 - j / (h - 1)
            for i in range(w):
                c = lerp(base, tipc, t ** 0.8)
                c = lerp(c, (0x9c, 0xe6, 0xff), max(0, 1 - abs(i / (w - 1) - 0.5) * 4) * 0.35)
                d.point((i, j), fill=c)
        P = lambda u, v: (u * (w - 1), (1 - v) * (h - 1))
        # facet edges for BOTH shard UV layouts in stud_kit.shard (4-tri blade and 12-tri hero)
        edges = [((0, 0), (.5, 1)), ((1, 0), (.5, 1)), ((0, .32), (.5, 1)), ((1, .32), (.5, 1)),
                 ((.2, 0), (0, .32)), ((.8, 0), (1, .32)), ((0, .32), (1, .32)), ((0, 0), (1, 0))]
        halo = im.copy(); hd = ImageDraw.Draw(halo)
        for a, b in edges: hd.line([P(*a), P(*b)], fill=(0x7c, 0xe8, 0xff), width=9)
        im.paste(Image.blend(im, halo.filter(ImageFilter.GaussianBlur(3)), 0.7))
        d = ImageDraw.Draw(im)
        for a, b in [((.5, .05), (.5, .95)), ((.2, .18), (.5, .6)), ((.82, .12), (.55, .55))]:
            d.line([P(*a), P(*b)], fill=(0xa8, 0xee, 0xff), width=2)
        for a, b in edges: d.line([P(*a), P(*b)], fill=(0xf2, 0xfd, 0xff), width=3)
    return fn

def eye(spec):
    glow = hexc(spec.get('glow', '#2eb8fa')); i0, i1 = (hexc(c) for c in spec.get('iris', ['#3ac4ff', '#e4fdff']))
    pupil = hexc(spec.get('pupil', '#051036')); A = spec.get('aspect', 2.3)
    def fn(d, w, h, im):
        im.paste(glow, [0, 0, w, h]); cx, cy = w * 0.56, h * 0.5
        for k in range(60, 0, -1):
            t = 1 - k / 60; rx, ry = w * .55 * k / 60, h * .55 * k / 60
            d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=lerp(glow, (0xf6, 0xff, 0xff), min(1, t * 1.8)))
        iry = h * .42; irx = iry / A                      # pre-squashed so the iris reads round on a w:h=A surface
        for k in range(30, 0, -1):
            d.ellipse([cx - irx * k / 30, cy - iry * k / 30, cx + irx * k / 30, cy + iry * k / 30], fill=lerp(i0, i1, 1 - k / 30))
        pry = h * .34; prx = max(2.0, pry * .16 / A)
        d.ellipse([cx - prx, cy - pry, cx + prx, cy + pry], fill=pupil)
        d.ellipse([cx + irx * .25, cy - iry * .55, cx + irx * .7, cy - iry * .3], fill=(255, 255, 255))
    return fn

def gem(spec):
    base = hexc(spec.get('base', '#2ab4fb')); lite = hexc(spec.get('lite', '#9aeeff'))
    mid = hexc(spec.get('mid', '#4dd9fe')); dark = hexc(spec.get('dark', '#168cf0'))
    def fn(d, w, h, im):
        im.paste(base, [0, 0, w, h]); c = (w / 2, h / 2)
        for (a, b), s in zip([((0, 0), (w, 0)), ((w, 0), (w, h)), ((w, h), (0, h)), ((0, h), (0, 0))],
                             [lite, mid, dark, lerp(mid, lite, .4)]):
            d.polygon([a, b, c], fill=s)
        d.line([(0, 0), (w, h)], fill=(0xe8, 0xfc, 0xff), width=2); d.line([(w, 0), (0, h)], fill=(0xe8, 0xfc, 0xff), width=2)
        for k in range(20, 0, -1):
            r = w * .32 * k / 20; d.ellipse([c[0]-r, c[1]-r, c[0]+r, c[1]+r], fill=lerp((0xf4,0xff,0xf4), lerp(mid, lite, .5), k / 20))
    return fn

def gradient(a, b):
    def fn(d, w, h, im):
        for j in range(h): d.line([(0, j), (w, j)], fill=lerp(a, b, j / max(1, h - 1)))
    return fn

def gold(spec):
    def fn(d, w, h, im):
        gradient((0xff, 0xe0, 0x80), (0xd8, 0x98, 0x20))(d, w, h, im)
        d.rectangle([0, 0, w - 1, h - 1], outline=(0xb0, 0x78, 0x10), width=3)
    return fn


def leaf_swatch(spec, rect):
    """Faceted kite leaf: studs on the surface, glowing rim + facet ridges (also written to the emissive map)."""
    x, y, w, h = rect; SS = 4
    base = col(spec['color']); k = spec.get('emit', 1.0)
    big = tile // 2 if False else 64 * 2                       # stud tile (2x2 studs) = 128 px -> ~4 studs across a leaf
    shade_l = np.asarray(Image.fromarray((np.clip(shade, 0, 1.4) / 1.4 * 255).astype(np.uint8)).resize((big, big), Image.LANCZOS)).astype(np.float32) / 255 * 1.4
    reps = (h // big + 1, w // big + 1)
    sh = np.tile(shade_l, reps)[:h, :w]
    pts = [(w / 2, h - 4), (w - 4, h * 0.56), (w / 2, 4), (4, h * 0.56)]       # base, right, tip, left
    ctr = (w / 2, h * 0.47)
    m = Image.new('L', (w * SS, h * SS), 0); ImageDraw.Draw(m).polygon([(px * SS, py * SS) for px, py in pts], fill=255)
    inner = m.filter(ImageFilter.GaussianBlur(6 * SS)).point(lambda v: 255 if v > 232 else 0).filter(ImageFilter.GaussianBlur(2 * SS))
    msk = np.asarray(m.resize((w, h), Image.LANCZOS)).astype(np.float32) / 255
    inn = np.asarray(inner.resize((w, h), Image.LANCZOS)).astype(np.float32) / 255
    rim = np.clip(msk - inn, 0, 1)
    # facet tones (lit / shaded halves) so the ridge reads even without lighting
    tone = np.ones((h, w), np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    tone *= np.where(xx < w / 2, 0.93, 1.06)
    tone *= np.where(yy < h * 0.47, 1.0, 0.96)
    c = np.broadcast_to(base, (h, w, 3)) * (sh * tone)[..., None]
    lite = np.array([0.82, 1.0, 0.45], np.float32)
    ridge = Image.new('L', (w, h), 0); rd = ImageDraw.Draw(ridge)
    for p in pts: rd.line([ctr, p], fill=255, width=3)
    rd.line([pts[0], pts[2]], fill=255, width=3)
    rg = np.asarray(ridge.filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255
    glow = np.clip(rim * 1.0 + rg * 0.55, 0, 1)[..., None]
    c = c * (1 - 0.4 * glow) + (base * 0.5 + lite * 0.5) * 0.4 * glow
    out = np.where(msk[..., None] > 0.5, c, base * 0.5)
    img[y:y + h, x:x + w] = np.clip(out, 0, 1)
    emi[y:y + h, x:x + w] = np.clip((base * 0.4 + lite * 0.6) * glow * k, 0, 1) * (msk[..., None] > 0.5)
    nmap[y:y + h, x:x + w] = np.tile(nrm_s, (h // tile + 1, w // tile + 1, 1))[:h, :w] * 0.5 + 0.5

studded = []
for name, spec in cfg['slots'].items():
    x, y, w, h = spec['rect']; kind = spec['kind']
    if kind == 'studs':
        studded.append(name)
        reps = (h // tile + 1, w // tile + 1)
        cc = np.broadcast_to(col(spec['color']), (h, w, 3)).copy()
        if 'top_tint' in spec:                               # brighter stud tops (optional)
            tc, a = spec['top_tint']
            m = np.tile(stud_mask, reps)[:h, :w][..., None] * a
            cc = cc * (1 - m) + col(tc)[None, None] * m
        img[y:y + h, x:x + w] = np.clip(cc * np.tile(shade, reps)[:h, :w][..., None], 0, 1)
        nmap[y:y + h, x:x + w] = np.tile(nrm_s, reps + (1,))[:h, :w] * 0.5 + 0.5
    elif kind == 'flat': img[y:y + h, x:x + w] = col(spec['color'])
    elif kind == 'gradient': paint(spec['rect'], gradient(hexc(spec['from']), hexc(spec['to'])))
    elif kind == 'gold': paint(spec['rect'], gold(spec))
    elif kind == 'crystal': paint(spec['rect'], crystal(spec))
    elif kind == 'eye': paint(spec['rect'], eye(spec)); emi[y:y + h, x:x + w] = img[y:y + h, x:x + w]
    elif kind == 'gem': paint(spec['rect'], gem(spec)); emi[y:y + h, x:x + w] = img[y:y + h, x:x + w]
    elif kind == 'leaf': leaf_swatch(spec, spec['rect'])
    elif kind == 'image':
        im = Image.open(spec['path']).convert('RGB').resize((w, h), Image.LANCZOS); a = np.asarray(im).astype(np.float32) / 255
        img[y:y + h, x:x + w] = a
        lum = a @ np.array([.3, .59, .11], np.float32); sat = a.max(-1) - a.min(-1)
        emi[y:y + h, x:x + w] = a * np.clip((lum - 0.55) / 0.3, 0, 1)[..., None] * (sat > 0.25)[..., None] * spec.get('emit', 0.8)
    else: raise SystemExit(f'unknown slot kind {kind}')

Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, 'Color.png'))
Image.fromarray((np.clip(emi, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, 'Emissive.png'))
Image.fromarray((np.clip(nmap, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, 'Normal.png'))
json.dump({'size': S, 'px_per_stud': PX, 'slots': {k: v['rect'] for k, v in cfg['slots'].items()}, 'studded': studded},
          open(os.path.join(OUT, 'atlas_regions.json'), 'w'), indent=1)
print('atlas written:', OUT, 'studded slots:', studded)
