"""Generate the Ancient Dragon texture atlas (colour, normal, emission).

Rows 0-2: one swatch per palette colour, carrying a soft stud relief (rounded studs, bevelled seams)
at low colour contrast so it reads as surface detail, not pixels.
Row 3: the wing membrane gradient with anti-aliased glowing runes, the rune plates, and the eyeball.
Glyphs are drawn supersampled with PIL so every edge is smooth.
"""
import os, sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(__file__))
from spec import *

OUT = os.path.join(os.path.dirname(__file__), '..', 'textures')
rng = np.random.default_rng(7)
col = np.zeros((ATLAS, ATLAS, 3), np.float32)
hgt = np.zeros((ATLAS, ATLAS), np.float32)
emi = np.zeros((ATLAS, ATLAS), np.float32)
SS = 4                                              # supersampling for vector drawing


def smooth(e0, e1, x):
    k = np.clip((x - e0) / (e1 - e0), 0, 1)
    return k * k * (3 - 2 * k)


def soft_noise(h, w, scale, amp):
    n = rng.normal(0, 1, (max(2, h // scale + 2), max(2, w // scale + 2))).astype(np.float32)
    img = Image.fromarray(((n - n.min()) / (np.ptp(n) + 1e-6) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return 1.0 + (np.asarray(img, np.float32) / 255.0 - 0.5) * 2 * amp


def stud_field(h, w, phase=MARGIN):
    """shade + height of the stud relief over an h x w block (cells of CELL_PX, grid starting at `phase`)."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    u = ((x - phase) % CELL_PX + 0.5) / CELL_PX
    v = ((y - phase) % CELL_PX + 0.5) / CELL_PX
    e = np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v)) * CELL_PX
    bev = smooth(0.0, 4.0, e)
    q = np.maximum(np.abs(np.dstack((u - 0.5, v - 0.5))) - 0.12, 0)
    sd = np.sqrt((q ** 2).sum(2)) - 0.1
    stud = smooth(0.06, -0.06, sd)
    light = (0.5 - u) + (0.5 - v)
    shade = 0.9 + 0.1 * bev + (1 - bev) * light * 0.12 + stud * 0.05 \
        + smooth(0.08, 0.0, np.abs(sd)) * np.sign(light) * 0.05
    return shade, 0.4 * bev + 0.45 * stud


def paint(x, y, rgb, shade=None, height=None, emit=None):
    h, w = rgb.shape[:2]
    col[y:y + h, x:x + w] = np.clip(rgb * (shade[..., None] if shade is not None else 1), 0, 255)
    if height is not None:
        hgt[y:y + h, x:x + w] = height
    if emit is not None:
        emi[y:y + h, x:x + w] = emit


def vector(w, h, draw_fn):
    """draw with PIL at SS x, return an anti-aliased float mask (h, w) in 0..1."""
    img = Image.new('L', (w * SS, h * SS), 0)
    draw_fn(ImageDraw.Draw(img), SS)
    return np.asarray(img.resize((w, h), Image.LANCZOS), np.float32) / 255.0


def mix(a, b, t):
    return a * (1 - t[..., None]) + np.array(b, np.float32) * t[..., None]


# ---------------- palette swatches ----------------
for key, rgb, e, var in VOX:
    cx, cy = VOX_SWATCH[key]
    shade, h = stud_field(SW, SW)
    base = np.ones((SW, SW, 3), np.float32) * np.array(rgb, np.float32)
    base *= soft_noise(SW, SW, 64, var * 0.5)[..., None]
    paint(cx * SW, cy * SW, base, shade, h, np.full((SW, SW), e, np.float32))

# ---------------- wing membrane (row 3): smooth gradient + glowing runes ----------------
wa0, wb0, NA, NB, wc = wing_grid()
WW, WH = NA * CELL_PX, NB * CELL_PX
yy, xx = np.mgrid[0:WH, 0:WW].astype(np.float32)
A = wa0 + (xx + 0.5) / CELL_PX * wc
Bv = wb0 + (NB - (yy + 0.5) / CELL_PX) * wc
trail = sorted(wing_trailing_2d(), key=lambda p: p[0])
lead = sorted([wing2d(p) for p in W_LEAD], key=lambda p: p[0])
d = Bv - np.interp(A, [p[0] for p in trail], [p[1] for p in trail])
u = np.interp(A, [p[0] for p in lead], [p[1] for p in lead]) - Bv
t = smooth(4.8, 0.0, d)
mem = mix(np.ones((WH, WW, 3), np.float32) * np.array((24, 92, 108), np.float32), (46, 196, 200), t)
mem = mix(mem, (110, 240, 238), smooth(0.9, 0.1, d))
mem = mix(mem, (34, 36, 50), smooth(0.4, 1.5, -u + 1.5) * smooth(-0.5, 0.5, u + 0.5))
mem *= soft_noise(WH, WW, 48, 0.05)[..., None]
memit = 0.3 * t + 0.8 * smooth(0.9, 0.1, d)

px = lambda a: (a - wa0) / wc * CELL_PX
py = lambda b: (NB - (b - wb0) / wc) * CELL_PX
anch = wing_glyph_anchors()


def wing_runes(dr, s):
    def P_(a, b):
        return (px(a) * s, py(b) * s)
    lw = int(0.3 / wc * CELL_PX * s)
    # big keyhole rune: diamond frame, inner ring, stem
    a, b = anch[2]; r = 1.3
    dr.polygon([P_(a, b + r), P_(a + r, b), P_(a, b - r), P_(a - r, b)], outline=255, width=lw)
    cx_, cy_ = P_(a, b); rr = 0.45 / wc * CELL_PX * s
    dr.ellipse([cx_ - rr, cy_ - rr, cx_ + rr, cy_ + rr], outline=255, width=lw)
    dr.line([P_(a, b + r), P_(a, b + r + 0.7)], fill=255, width=lw)
    # medium cross rune
    a, b = anch[1]; r = 0.9
    dr.line([P_(a - r, b), P_(a + r, b)], fill=255, width=lw)
    dr.line([P_(a, b - r), P_(a, b + r)], fill=255, width=lw)
    dr.polygon([P_(a, b + 0.45), P_(a + 0.45, b), P_(a, b - 0.45), P_(a - 0.45, b)], outline=255, width=lw)
    # small chevrons
    a, b = anch[0]
    dr.line([P_(a - 0.5, b + 0.4), P_(a, b - 0.1), P_(a + 0.5, b + 0.4)], fill=255, width=lw, joint='curve')
    dr.line([P_(a - 0.5, b - 0.3), P_(a, b - 0.8), P_(a + 0.5, b - 0.3)], fill=255, width=lw, joint='curve')
    a, b = anch[3]
    dr.line([P_(a - 0.35, b - 0.35), P_(a + 0.35, b + 0.35)], fill=255, width=lw)


g = vector(WW, WH, wing_runes)
halo = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(9)), np.float32) / 255.0
mem = mix(mem, (70, 200, 205), np.clip(halo * 1.4, 0, 1) * 0.6)
mem = mix(mem, (150, 255, 250), g)
shade, h = stud_field(WH, WW, phase=0)
paint(0, WING_ROW_Y, mem, 0.5 + 0.5 * shade, 0.5 * h + 0.3 * g, np.clip(memit + g + halo * 0.4, 0, 1))


# ---------------- rune plates ----------------
def plate(name, draw_glow, inset=None):
    art = RUNE_ART[name]
    w, h = len(art[0]) * CELL_PX, len(art) * CELL_PX
    ox_, oy_ = RUNE_ORIGIN[name]
    rgbc = np.ones((h, w, 3), np.float32) * np.array((236, 164, 44), np.float32)
    rgbc *= soft_noise(h, w, 40, 0.05)[..., None]
    height = np.full((h, w), 0.6, np.float32)
    if inset is not None:
        m = vector(w, h, inset)
        rgbc = mix(rgbc, (24, 58, 70), m)
        edge = np.clip(m - np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(5)), np.float32) / 255, 0, 1)
        rgbc = mix(rgbc, (120, 80, 20), edge * 0.8)
        height -= 0.35 * m
    gl = vector(w, h, draw_glow)
    hal = np.asarray(Image.fromarray((gl * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32) / 255.0
    rgbc = mix(rgbc, (50, 190, 200), np.clip(hal * 1.3, 0, 1) * 0.55 * (1 if inset else 0.4))
    rgbc = mix(rgbc, (130, 255, 248), gl)
    paint(ox_, oy_, rgbc, None, height + 0.25 * gl, np.clip(gl + hal * 0.4, 0, 1))


def disc_inset(dr, s):
    W = 8 * CELL_PX * s
    dr.ellipse([W * 0.14, W * 0.14, W * 0.86, W * 0.86], fill=255)


def disc_glow(dr, s):
    W = 8 * CELL_PX * s; lw = int(W * 0.045)
    dr.ellipse([W * 0.27, W * 0.27, W * 0.73, W * 0.73], outline=255, width=lw)
    c = W / 2; r = W * 0.12
    dr.polygon([(c, c - r), (c + r, c), (c, c + r), (c - r, c)], fill=255)


def chest_inset(dr, s):
    w, h = 7 * CELL_PX * s, 8 * CELL_PX * s
    dr.polygon([(w * 0.14, h * 0.1), (w * 0.86, h * 0.1), (w * 0.86, h * 0.6), (w * 0.5, h * 0.9), (w * 0.14, h * 0.6)], fill=255)


def chest_glow(dr, s):
    w, h = 7 * CELL_PX * s, 8 * CELL_PX * s; lw = int(w * 0.05)
    c, m = w / 2, h * 0.45
    dr.polygon([(c, m - h * 0.25), (c + w * 0.26, m), (c, m + h * 0.25), (c - w * 0.26, m)], outline=255, width=lw)
    dr.polygon([(c, m - h * 0.1), (c + w * 0.1, m), (c, m + h * 0.1), (c - w * 0.1, m)], fill=255)
    dr.line([(c, h * 0.12), (c, m - h * 0.25)], fill=255, width=lw)
    dr.line([(c, m + h * 0.25), (c, h * 0.8)], fill=255, width=lw)


def tail_inset(dr, s):
    w, h = 4 * CELL_PX * s, 3 * CELL_PX * s
    dr.rounded_rectangle([w * 0.06, h * 0.08, w * 0.94, h * 0.92], radius=h * 0.2, fill=255)


def tail_glow(dr, s):
    w, h = 4 * CELL_PX * s, 3 * CELL_PX * s; lw = int(h * 0.1)
    dr.rounded_rectangle([w * 0.22, h * 0.24, w * 0.78, h * 0.76], radius=h * 0.12, outline=255, width=lw)
    dr.ellipse([w * 0.44, h * 0.42, w * 0.56, h * 0.58], fill=255)


def knee_glow(dr, s):
    w = 4 * CELL_PX * s; lw = int(w * 0.08); c = w / 2; r = w * 0.28
    dr.polygon([(c, c - r), (c + r, c), (c, c + r), (c - r, c)], outline=255, width=lw)


plate('disc', disc_glow, disc_inset)
plate('chest', chest_glow, chest_inset)
plate('tail', tail_glow, tail_inset)
plate('knee', knee_glow)

# ---------------- eyeball: glowing sclera, cyan iris, dark slit pupil, glint ----------------
ex, ey, ew, eh = EYE_REGION
yy, xx = np.mgrid[0:eh, 0:ew].astype(np.float32)
dx = (xx + 0.5 - ew / 2) / (ew / 2); dy = (yy + 0.5 - eh / 2) / (eh / 2)
d = np.sqrt(dx ** 2 + dy ** 2)
eye = np.ones((eh, ew, 3), np.float32) * np.array((150, 238, 236), np.float32)
iris = smooth(0.66, 0.6, d)
eye = mix(eye, (60, 250, 244), iris)
eye = mix(eye, (20, 120, 130), smooth(0.08, 0.0, np.abs(d - 0.62)))
slit = 0.13 * np.sqrt(np.clip(1 - (dy / 0.5) ** 2, 0, 1))
pupil = smooth(0.02, -0.02, np.abs(dx) - slit) * smooth(0.52, 0.46, np.abs(dy))
eye = mix(eye, (8, 16, 22), pupil)
eye = mix(eye, (255, 255, 255), smooth(0.13, 0.08, np.sqrt((dx + 0.25) ** 2 + (dy + 0.3) ** 2)))
paint(ex, ey, eye, None, np.full((eh, ew), 0.5, np.float32), np.clip(0.55 + 0.45 * iris - pupil, 0, 1))

os.makedirs(OUT, exist_ok=True)
Image.fromarray(col.astype(np.uint8)).save(os.path.join(OUT, 'AncientDragon_Color_2048.png'))
Image.fromarray(col.astype(np.uint8)).resize((1024, 1024), Image.LANCZOS).save(os.path.join(OUT, 'AncientDragon_Color.png'))
# normal map (OpenGL / +Y) from height
hs = np.asarray(Image.fromarray((hgt * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255.0
gx = np.zeros_like(hs); gy = np.zeros_like(hs)
gx[:, 1:-1] = (hs[:, 2:] - hs[:, :-2]) * 0.5
gy[1:-1, :] = (hs[2:, :] - hs[:-2, :]) * 0.5
k = 2.0
n = np.dstack((-gx * k, gy * k, np.ones_like(hs)))
n /= np.linalg.norm(n, axis=2, keepdims=True)
nimg = ((n * 0.5 + 0.5) * 255).astype(np.uint8)
Image.fromarray(nimg).save(os.path.join(OUT, 'AncientDragon_Normal_2048.png'))
Image.fromarray(nimg).resize((1024, 1024), Image.LANCZOS).save(os.path.join(OUT, 'AncientDragon_Normal.png'))
Image.fromarray((np.clip(emi, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, 'AncientDragon_Emission_2048.png'))
print('textures written', OUT)
