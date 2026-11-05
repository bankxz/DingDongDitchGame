"""Generate tileable stylised textures for the lobby kit (numpy + Pillow, no Blender needed).

cobblestone_albedo.png / cobblestone_normal.png
  * one tile = 6 x 6 studs  (COBBLE_TILE_STUDS) at 1024 px
  * 6 rows of 1.0-stud setts, 4 setts of 1.5 studs per row, running bond (odd rows offset 0.75)
  * colours sampled from the arch turnaround / lobby shots: blue-grey to lavender-grey setts,
    warm sandy grout, soft top-left bevel light baked in lightly (stylised, Roblox-friendly)
  * perfectly periodic in both directions (all noise is built from integer-frequency sines)
Run:  python make_textures.py
"""
import os, math
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "textures")
COBBLE_TILE_STUDS = 6.0
RES = 1024


def periodic_noise(x, y, period, octaves, seed, amp=1.0):
    """Sum of random integer-frequency sinusoids -> tileable smooth noise in [-1, 1]-ish."""
    rng = np.random.default_rng(seed)
    out = np.zeros_like(x)
    tot = 0.0
    for o in range(octaves):
        for _ in range(4):
            fx, fy = rng.integers(-(2 + 3 * o), 3 + 3 * o, size=2)
            if fx == 0 and fy == 0:
                fx = 1
            ph = rng.uniform(0, 2 * math.pi)
            a = amp / (1 + o)
            out += a * np.sin(2 * math.pi * (fx * x + fy * y) / period + ph)
            tot += a
    return out / tot


def srgb_to_lin(c):
    c = np.asarray(c) / 255.0
    return c


def cobblestone():
    T = COBBLE_TILE_STUDS
    px = (np.arange(RES) + 0.5) / RES * T
    X, Y = np.meshgrid(px, px)                    # X right, Y down in image space
    W, H = 1.5, 1.0
    row = np.floor(Y / H).astype(int)
    xo = np.mod(X + (row % 2) * 0.75, T)
    col = np.floor(xo / W).astype(int)
    u = xo - col * W - W / 2                       # local coords centred in the sett
    v = Y - row * H - H / 2
    sid = row * 4 + col
    rng = np.random.default_rng(7)
    n_st = 6 * 4
    shrink = rng.uniform(0.0, 0.025, n_st)
    tilt = rng.uniform(-0.06, 0.06, (n_st, 2))
    palette = np.array([[118, 120, 148], [104, 106, 136], [128, 128, 156], [112, 110, 140], [98, 100, 128],
                        [124, 122, 146]], float)
    base = palette[rng.integers(0, len(palette), n_st)] * rng.uniform(0.92, 1.08, (n_st, 1))
    # rounded-rectangle signed distance with wobbly edges
    gap = 0.038
    hx = W / 2 - gap - shrink[sid]
    hy = H / 2 - gap - shrink[sid]
    r = 0.16
    wob = 0.035 * periodic_noise(X, Y, T, 3, 3)
    qx = np.abs(u) - (hx - r)
    qy = np.abs(v) - (hy - r)
    sdf = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r + wob
    inside = sdf < 0
    # height: bevelled dome per sett + fine surface noise
    bevel = np.clip(-sdf / 0.14, 0, 1)
    bevel = bevel * bevel * (3 - 2 * bevel)
    dome = 1 - 0.25 * ((u / W) ** 2 + (v / H) ** 2)
    fine = 0.06 * periodic_noise(X, Y, T, 4, 11)
    height = np.where(inside, bevel * dome + fine * bevel + tilt[sid, 0] * u + tilt[sid, 1] * v, -0.05)
    # normal map (OpenGL convention, +Y up in texture space)
    s = RES / T
    hz = height * 0.18
    dx = (np.roll(hz, -1, 1) - np.roll(hz, 1, 1)) * s / 2
    dy = (np.roll(hz, -1, 0) - np.roll(hz, 1, 0)) * s / 2
    nx, ny, nz = -dx, dy, np.ones_like(dx)
    nl = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack([nx / nl, ny / nl, nz / nl], -1)
    # albedo: per-sett colour + mottling + light baked bevel lighting (top-left key)
    mott = 1 + 0.07 * periodic_noise(X, Y, T, 4, 21)
    col_st = base[sid] * mott[..., None]
    light = np.clip(normal @ np.array([-0.45, 0.55, 0.7]) / 0.98, 0, 1.2)
    col_st = col_st * (0.78 + 0.32 * light[..., None])
    edge_dark = 1 - 0.18 * (1 - bevel)
    col_st *= edge_dark[..., None]
    grout = np.array([168, 152, 128], float) * (1 + 0.08 * periodic_noise(X, Y, T, 3, 31))[..., None]
    aa = np.clip(-sdf / 0.012 + 0.5, 0, 1)[..., None]          # anti-aliased edge
    albedo = col_st * aa + grout * (1 - aa)
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray(np.clip(albedo, 0, 255).astype(np.uint8)).save(os.path.join(OUT, "cobblestone_albedo.png"))
    nimg = ((normal * 0.5 + 0.5) * 255).astype(np.uint8)
    Image.fromarray(nimg).save(os.path.join(OUT, "cobblestone_normal.png"))
    # 2x2 tiling preview to prove seamlessness
    a = Image.open(os.path.join(OUT, "cobblestone_albedo.png"))
    prev = Image.new("RGB", (RES * 2, RES * 2))
    for i in range(2):
        for j in range(2):
            prev.paste(a, (i * RES, j * RES))
    prev.resize((RES, RES)).save(os.path.join(os.path.dirname(HERE), "renders", "texture_cobblestone_tiling_2x2.png"))
    print("TEXTURES", OUT)


CASTLE_BRICK_TILE_STUDS = 12.0


def castle_brick():
    """White/lavender marble ashlar for the floating castle (castle sheet: 'Wall Section',
    'Wall / Crenellation' close-ups): 4 courses of 3.0-stud blocks, 3 blocks of 4.0 studs per course,
    running bond, thin LIGHT mortar seams (the sheet's joints are subtle), per-block tint and faint veins.
    One tile = 12 x 12 studs at 1024 px, periodic in both directions."""
    T = CASTLE_BRICK_TILE_STUDS
    px = (np.arange(RES) + 0.5) / RES * T
    X, Y = np.meshgrid(px, px)
    W, H = 4.0, 3.0
    row = np.floor(Y / H).astype(int)
    xo = np.mod(X + (row % 2) * (W / 2), T)
    col = np.floor(xo / W).astype(int)
    u = xo - col * W - W / 2
    v = Y - row * H - H / 2
    sid = row * 3 + col
    rng = np.random.default_rng(12)
    n_st = 4 * 3
    tint = rng.uniform(0.95, 1.03, (n_st, 1)) * np.array([[1.0, 1.0, 1.0]])
    tint[:, 0] *= rng.uniform(0.985, 1.0, n_st)
    base = np.array([226, 222, 236], float)
    seam = 0.05                                          # half-width of a joint (studs)
    dx = W / 2 - np.abs(u)
    dy = H / 2 - np.abs(v)
    d = np.minimum(dx, dy)                               # distance to the block edge
    inside = np.clip((d - seam) / 0.03, 0, 1)            # anti-aliased joint mask
    # height: flat face, tiny edge chamfer, recessed joint
    height = np.clip((d - seam) / 0.18, 0, 1) * 0.6 + inside * 0.4
    s = RES / T
    hz = height * 0.08
    gx = (np.roll(hz, -1, 1) - np.roll(hz, 1, 1)) * s / 2
    gy = (np.roll(hz, -1, 0) - np.roll(hz, 1, 0)) * s / 2
    nx, ny, nz = -gx, gy, np.ones_like(gx)
    nl = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack([nx / nl, ny / nl, nz / nl], -1)
    # faint marble veins: thin bands of a periodic noise field
    vn = periodic_noise(X, Y, T, 3, 41)
    has_vein = (rng.random(n_st) < 0.45).astype(float)     # only some blocks carry a faint vein
    vein = np.clip(1 - np.abs(vn) / 0.018, 0, 1) * 0.22 * has_vein[sid]
    cloud = 1 + 0.035 * periodic_noise(X, Y, T, 2, 43)
    stone = base * tint[sid] * cloud[..., None]
    stone = stone * (1 - vein[..., None]) + np.array([170, 160, 192]) * vein[..., None]
    light = np.clip(normal @ np.array([-0.4, 0.5, 0.77]), 0, 1.1)
    stone = stone * (0.9 + 0.12 * light[..., None])
    mortar = np.array([196, 190, 212], float)
    albedo = stone * inside[..., None] + mortar * (1 - inside[..., None])
    Image.fromarray(np.clip(albedo, 0, 255).astype(np.uint8)).save(os.path.join(OUT, "castle_brick_albedo.png"))
    Image.fromarray(((normal * 0.5 + 0.5) * 255).astype(np.uint8)).save(os.path.join(OUT, "castle_brick_normal.png"))
    a = Image.open(os.path.join(OUT, "castle_brick_albedo.png"))
    prev = Image.new("RGB", (RES * 2, RES * 2))
    for i in range(2):
        for j in range(2):
            prev.paste(a, (i * RES, j * RES))
    prev.resize((RES, RES)).save(os.path.join(os.path.dirname(HERE), "renders", "texture_castle_brick_tiling_2x2.png"))
    print("TEXTURE castle_brick")


WOOD_TILE_STUDS = 6.0


def wood_grain():
    """Grey-scale, tileable wood-grain map (grain runs along U / image X).  All wood materials share it
    and tint it; one tile = 6 x 6 studs.  Integer frequencies + periodic warp keep it seamless."""
    T = WOOD_TILE_STUDS
    px = (np.arange(RES) + 0.5) / RES * T
    X, Y = np.meshgrid(px, px)
    warp = 0.9 * periodic_noise(X, Y, T, 2, 51)                       # gentle waviness along the grain
    g = np.zeros_like(X)
    for fy, a, ph in ((9, 0.45, 0.3), (17, 0.3, 1.7), (31, 0.18, 2.9)):
        g += a * np.sin(2 * math.pi * fy * Y / T + warp * (1 + fy / 20) + ph)
    g = g / 0.93
    rng = np.random.default_rng(53)                                    # fine streaks: integer freqs only
    fibre = np.zeros_like(X)
    for fx, fy in ((1, 41), (2, 57), (1, 73), (3, 89)):
        fibre += np.sin(2 * math.pi * (fx * X + fy * Y) / T + rng.uniform(0, 2 * math.pi))
    fibre *= 0.05 / 4 * 2
    v = np.clip(0.5 + 0.22 * g + fibre, 0, 1)                         # soft, painterly contrast
    v = v ** 0.9
    Image.fromarray((v * 255).astype(np.uint8), mode="L").save(os.path.join(OUT, "wood_grain.png"))
    a = Image.open(os.path.join(OUT, "wood_grain.png"))
    prev = Image.new("L", (RES * 2, RES * 2))
    for i in range(2):
        for j in range(2):
            prev.paste(a, (i * RES, j * RES))
    prev.resize((RES, RES)).save(os.path.join(os.path.dirname(HERE), "renders", "texture_wood_grain_tiling_2x2.png"))
    print("TEXTURE wood_grain")


if __name__ == "__main__":
    cobblestone()
    castle_brick()
    wood_grain()
