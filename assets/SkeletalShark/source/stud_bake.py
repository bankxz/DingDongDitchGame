"""Texture baker for the low-poly shark: rasterises every triangle into the UV atlas with a soft
painted gradient, bevel-style edge highlights and sparse engraved "stud" squares (full squares
and partial corner marks), matching the user's example pets. Pure numpy."""
import numpy as np

BONE = np.array((245, 228, 204), float)
IVORY = np.array((212, 186, 161), float)
DARK_BLUE = np.array((30, 52, 103), float)
BLUE_ACCENT = np.array((80, 129, 193), float)
CYAN = np.array((80, 251, 254), float)
SOCKET = np.array((20, 38, 92), float)
MATS = ["bone", "blue", "cyan", "socket", "tooth", "eye"]
STUDDED = (0, 1)


def _shade(mat, h, nz, t_tip):
    """h: 0..1 height inside the part, nz: normal z, t_tip: 0..1 along a tooth."""
    n = h.shape[0]
    col = np.zeros((n, 3))
    light = 0.74 + 0.32 * h + 0.06 * nz
    if mat == 0:
        col[:] = (IVORY * 0.35 + BONE * 0.65)[None] * (1 - h[:, None] * 0.0) + (BONE - (IVORY * 0.35 + BONE * 0.65))[None] * h[:, None]
        col *= light[:, None]
    elif mat == 1:
        col[:] = DARK_BLUE[None] + (BLUE_ACCENT - DARK_BLUE)[None] * (0.08 + 0.32 * h)[:, None]
        col *= light[:, None]
    elif mat == 2:
        col[:] = CYAN[None] * (0.92 + 0.08 * h)[:, None]
    elif mat == 3:
        col[:] = SOCKET[None] * (0.9 + 0.2 * h)[:, None]
    elif mat == 4:
        col[:] = IVORY[None] + (np.array((255, 250, 240.0)) - IVORY)[None] * t_tip[:, None]
    else:  # eye: cyan with a hot centre (centre handled by t_tip = distance-to-edge proxy)
        col[:] = CYAN[None] + (np.array((235, 255, 255.0)) - CYAN)[None] * np.clip(t_tip * 1.6 - 0.4, 0, 1)[:, None]
    return col


def bake(uv, pos, nrm, mat, isl, zrange, size=1024, seed=5, stud_cubes=1.0, spacing_cubes=1.7):
    T = len(uv)
    img = np.zeros((size, size, 3))
    emis = np.zeros((size, size))
    islmap = np.full((size, size), -1, np.int32)
    matmap = np.full((size, size), -1, np.int32)
    P = np.stack([uv[..., 0] * size, (1 - uv[..., 1]) * size], -1)  # pixel coords
    a_uv = 0.5 * np.abs(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]))
    a_w = 0.5 * np.linalg.norm(np.cross(pos[:, 1] - pos[:, 0], pos[:, 2] - pos[:, 0]), axis=1)
    k = float(np.sqrt(a_uv[mat != 4].sum() / max(a_w[mat != 4].sum(), 1e-9)))  # px per cube
    for t in range(T):
        p = P[t]
        x0, y0 = np.floor(p.min(0)).astype(int) - 1
        x1, y1 = np.ceil(p.max(0)).astype(int) + 1
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        q = np.stack([xs.ravel(), ys.ravel()], -1)
        v0, v1 = p[1] - p[0], p[2] - p[0]
        d = v0[0] * v1[1] - v0[1] * v1[0]
        if abs(d) < 1e-12:
            continue
        r = q - p[0]
        b1 = (r[:, 0] * v1[1] - r[:, 1] * v1[0]) / d
        b2 = (v0[0] * r[:, 1] - v0[1] * r[:, 0]) / d
        b0 = 1 - b1 - b2
        inside = (b0 >= -0.02) & (b1 >= -0.02) & (b2 >= -0.02)
        if not inside.any():
            continue
        bc = np.stack([b0, b1, b2], -1)[inside]
        w = bc @ pos[t]
        z0, z1 = zrange[t]
        h = np.clip((w[:, 2] - z0) / max(z1 - z0, 1e-6), 0, 1)
        tip = h if mat[t] != 5 else np.clip(1 - 2 * np.abs(h - 0.5), 0, 1)
        col = _shade(int(mat[t]), h, np.full(len(h), nrm[t][2]), tip)
        px = q[inside].astype(int)
        img[px[:, 1], px[:, 0]] = col
        islmap[px[:, 1], px[:, 0]] = isl[t]
        matmap[px[:, 1], px[:, 0]] = mat[t]
        if mat[t] in (2, 5):
            emis[px[:, 1], px[:, 0]] = 1.0

    filled = islmap >= 0
    # bevel-style highlight along island borders (real geometric edges on a low-poly mesh)
    band = max(2, int(round(0.10 * k)))
    edge = np.zeros_like(filled)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        for r in range(1, band + 1):
            sh = np.roll(np.roll(islmap, dy * r, 0), dx * r, 1)
            edge |= filled & (sh != islmap)
    stud_ok = np.isin(matmap, STUDDED)
    img[edge & stud_ok] += (255 - img[edge & stud_ok]) * 0.16

    # sparse engraved studs
    rng = np.random.default_rng(seed)
    sp = spacing_cubes * k
    n = int(size / sp) + 2
    lw = max(2, int(round(0.12 * k)))
    for gy in range(n):
        for gx in range(n):
            if rng.random() > 0.7:
                continue
            half = 0.5 * stud_cubes * k * (0.8 + 0.4 * rng.random())
            cx = (gx + 0.5 + (rng.random() - 0.5) * 0.35) * sp
            cy = (gy + 0.5 + (rng.random() - 0.5) * 0.35) * sp
            xa, xb = int(cx - half), int(cx + half)
            ya, yb = int(cy - half), int(cy + half)
            if xa - 2 * lw < 0 or ya - 2 * lw < 0 or xb + 2 * lw >= size or yb + 2 * lw >= size:
                continue
            reg = islmap[ya - 2 * lw:yb + 2 * lw + 1, xa - 2 * lw:xb + 2 * lw + 1]
            if reg.min() < 0 or (reg != reg[0, 0]).any() or not stud_ok[cy.__int__(), cx.__int__()]:
                continue
            partial = rng.random() < 0.3
            sub = img[ya:yb + 1, xa:xb + 1]
            H, W = sub.shape[:2]
            yy, xx = np.mgrid[0:H, 0:W]
            top, left = yy < lw, xx < lw
            bot, right = yy >= H - lw, xx >= W - lw
            if partial:  # corner mark only (like the example meshes)
                dark = (top & (xx < W * 0.6)) | (left & (yy < H * 0.6))
                lite = np.zeros_like(dark)
            else:
                dark = top | left
                lite = (bot | right) & ~dark
                sub *= 1.0 + 0.03 * ((~dark) & (~lite))[..., None]
            sub[dark] *= 0.70
            sub[lite] += (255 - sub[lite]) * 0.34
    # dilate into the gutters so mip/linear filtering never samples black
    for _ in range(6):
        empty = islmap < 0
        if not empty.any():
            break
        acc = np.zeros_like(img)
        cnt = np.zeros(islmap.shape)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh_i = np.roll(np.roll(islmap, dy, 0), dx, 1)
            sh_c = np.roll(np.roll(img, dy, 0), dx, 1)
            sh_e = np.roll(np.roll(emis, dy, 0), dx, 1)
            ok = empty & (sh_i >= 0)
            acc[ok] += sh_c[ok]
            cnt[ok] += 1
            emis[ok] = np.maximum(emis[ok], sh_e[ok])
        grow = cnt > 0
        img[grow] = acc[grow] / cnt[grow][:, None]
        islmap[grow] = 0
    return np.clip(img, 0, 255), emis, k
