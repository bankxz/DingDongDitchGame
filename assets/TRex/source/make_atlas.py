"""Generate the stud texture atlas for the red T-rex.

Stud normal/AO maps come from dudeax/Roblox-HD-Studs (MIT). Each atlas tile
is 8x8 studs at 32 px per stud; the mesh UVs map every box face onto a tile
at exactly 1 stud per model unit, so studs never stretch.

Usage: python3 make_atlas.py <stud_normal_png> <stud_ao_png> <out_dir>
"""
import sys
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ATLAS = 1024
TILE = 256
CELL = 32          # px per stud
GRID = TILE // CELL

# name: (base colour, per-cell jitter, stud strength, cracks, seams)
TILES = {
    'BONE':       ((230, 180, 130), 10, 1.0, False, False),
    'BONE_LIGHT': ((240, 200, 150), 8, 1.0, False, False),
    'CHARCOAL':   ((80, 56, 64), 8, 1.0, True, False),
    'MAROON':     ((118, 36, 38), 8, 1.0, True, False),
    'MIX':        (None, 0, 1.0, True, False),
    'DARK':       ((64, 34, 38), 6, 1.0, True, False),
    'MOUTH':      ((132, 22, 34), 8, 0.6, False, False),
    'TONGUE':     ((168, 36, 48), 6, 0.4, False, False),
    'TEETH':      ((240, 212, 170), 0, 0.0, False, False),
    'EYE':        ((255, 60, 40), 0, 0.0, False, False),
    'LAVA':       ((235, 40, 24), 0, 0.0, False, False),
    'BONE_DARK':  ((200, 146, 102), 8, 1.0, False, False),
    'PUPIL':      ((14, 6, 8), 0, 0.0, False, False),
}
ORDER = list(TILES)
MIX_COLOURS = [(128, 40, 42), (92, 50, 58), (70, 34, 40), (140, 48, 46), (100, 34, 36), (76, 52, 60)]


def one_stud(path, mode):
    # the source maps hold a 2x2 grid of studs; keep just one stud cell
    im = Image.open(path).convert(mode)
    return im.crop((0, 0, im.width // 2, im.height // 2))


def stud_shading(normal_png, ao_png):
    n = np.asarray(one_stud(normal_png, 'RGB').resize((CELL, CELL), Image.LANCZOS), np.float32) / 127.5 - 1.0
    ao = np.asarray(one_stud(ao_png, 'L').resize((CELL, CELL), Image.LANCZOS), np.float32) / 255.0
    light = np.array([-0.45, 0.55, 0.70])        # from upper-left, like the references
    light /= np.linalg.norm(light)
    ndl = (n * light).sum(-1)
    flat = light[2]
    shade = np.clip(1.0 + 0.9 * (ndl - flat), 0.7, 1.3)
    ao = 0.75 + 0.25 * ao / max(ao.max(), 1e-3)
    return shade * ao


def mottle(colours, rng, cells=4):
    """Smooth low-frequency colour variation (no per-block checkerboard)."""
    grid = np.array([[rng.choice(colours) for _ in range(cells)] for _ in range(cells)], np.float32)
    small = Image.fromarray(np.clip(grid, 0, 255).astype(np.uint8))
    return np.asarray(small.resize((TILE, TILE), Image.BICUBIC), np.float32)


def crack_network(rng, count):
    """Branching, jagged lava cracks: a few trunks that fork into thinner branches.
    Returns (glow, body, core) greyscale masks."""
    masks = [Image.new('L', (TILE, TILE), 0) for _ in range(3)]
    draws = [ImageDraw.Draw(m) for m in masks]

    def grow(x, y, ang, width, steps, depth):
        pts = [(x, y)]
        for _ in range(steps):
            ang += rng.uniform(-0.75, 0.75)
            ln = rng.uniform(6, 15)
            x, y = x + ln * np.cos(ang), y + ln * np.sin(ang)
            pts.append((x, y))
            if depth < 2 and rng.random() < 0.28:          # fork off a thinner branch
                grow(x, y, ang + rng.choice((-1, 1)) * rng.uniform(0.6, 1.2), width * 0.6,
                     rng.randrange(2, 5), depth + 1)
        w = max(1, int(round(width)))
        draws[0].line(pts, fill=255, width=w * 5)          # wide soft glow
        draws[1].line(pts, fill=255, width=w + 1)          # hot red body
        draws[2].line(pts, fill=255, width=max(1, w - 1))  # yellow-orange core
        for p in pts[1:-1]:                                # round the jagged joints
            r = (w + 1) / 2
            draws[1].ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=255)

    for _ in range(count):
        grow(rng.uniform(0, TILE), rng.uniform(0, TILE), rng.uniform(0, 2 * np.pi),
             rng.uniform(2.4, 3.6), rng.randrange(6, 12), 0)
    glow = masks[0].filter(ImageFilter.GaussianBlur(6))
    body = masks[1].filter(ImageFilter.GaussianBlur(0.8))
    core = masks[2].filter(ImageFilter.GaussianBlur(0.6))
    return [np.asarray(m, np.float32)[..., None] / 255.0 for m in (glow, body, core)]


GLOW_RGB = np.array((190, 26, 12), np.float32)
BODY_RGB = np.array((245, 52, 18), np.float32)
CORE_RGB = np.array((255, 176, 70), np.float32)


def make_tile(name, shade, rng):
    """Returns (albedo, emissive) images for one tile."""
    base, jitter, stud_k, cracks, seams = TILES[name]
    if base is None:
        colour = mottle(MIX_COLOURS, rng)
    else:
        shades = [tuple(np.array(base) + rng.uniform(-jitter, jitter)) for _ in range(6)]
        colour = mottle(shades, rng)
    s = 1.0 + stud_k * (np.tile(shade, (GRID, GRID)) - 1.0)
    img = colour * s[..., None]
    if seams:
        for i in range(GRID + 1):
            p = min(i * CELL, TILE - 1)
            img[p, :] *= 0.72
            img[:, p] *= 0.72
    emit = np.zeros_like(img)
    if name in ('EYE', 'LAVA'):
        emit = img.copy()
    if cracks:
        glow, body, core = crack_network(rng, 5 if name in ('MIX', 'MAROON') else 3)
        g = glow * 0.55
        img = img * (1 - g) + GLOW_RGB * g                 # warm halo on the surrounding surface
        img = img * (1 - body) + BODY_RGB * body
        img = img * (1 - core) + CORE_RGB * core
        emit = np.maximum(emit, GLOW_RGB * glow * 0.35 + BODY_RGB * body * 0.9 + CORE_RGB * core)
    to_img = lambda a: Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))  # noqa: E731
    return to_img(img), to_img(emit)


def main(normal_png, ao_png, out_dir):
    rng = random.Random(7)
    shade = stud_shading(normal_png, ao_png)
    atlas = Image.new('RGB', (ATLAS, ATLAS), (0, 0, 0))
    emissive = Image.new('RGB', (ATLAS, ATLAS), (0, 0, 0))   # glowing eyes, lava and cracks
    per_row = ATLAS // TILE
    for i, name in enumerate(ORDER):
        alb, emi = make_tile(name, shade, rng)
        pos = ((i % per_row) * TILE, (i // per_row) * TILE)
        atlas.paste(alb, pos)
        emissive.paste(emi, pos)
    atlas.save(f'{out_dir}/TRex_Studs_Albedo.png')
    emissive.save(f'{out_dir}/TRex_Studs_Emissive.png')
    # tangent-space normal atlas so Roblox SurfaceAppearance can add real stud relief
    n = one_stud(normal_png, 'RGB').resize((CELL, CELL), Image.LANCZOS)
    tile = Image.new('RGB', (TILE, TILE))
    for gy in range(GRID):
        for gx in range(GRID):
            tile.paste(n, (gx * CELL, gy * CELL))
    natlas = Image.new('RGB', (ATLAS, ATLAS), (128, 128, 255))
    for i, name in enumerate(ORDER):
        if TILES[name][2] > 0:
            natlas.paste(tile, ((i % per_row) * TILE, (i // per_row) * TILE))
    natlas.save(f'{out_dir}/TRex_Studs_Normal.png')
    print('atlas tiles:', ORDER)


if __name__ == '__main__':
    main(*sys.argv[1:4])
