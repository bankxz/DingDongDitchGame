"""Texture the 2880-tri sword from the reference sheet.
Front-facing polys  <- reference front view   (projected X/Z, aligned to the model's coordinates)
Back-facing polys   <- reference back view    (mirrored crop so the same X/Z mapping works)
Sidewalls / thin edges <- dark-metal swatch region of the atlas (no stretched projection)
Red glow is split into an emissive map; gems get a separate emissive material.
Run from models/sword:  python3 texture_sword.py
"""
import bpy, bmesh, cv2, numpy as np, math, os
from PIL import Image
from scipy import ndimage as ndi

REF = 'reference_sheet.png'
SRC_BLEND = 'sword_model.blend'
OUT = 'sword_model_textured'
TEXDIR = 'textures'
os.makedirs(TEXDIR, exist_ok=True)

rgb = np.array(Image.open(REF).convert('RGB'))
lum = rgb.astype(int).sum(2)
FX0, FX1, BX0, BX1 = 40, 239, 317, 516
R0, R1 = 8, 864
SCALE = 1.2 / 850
CX, ZERO = 139.5, 500
AT = 1024
S = 1.18
FW = int(round((FX1 - FX0) * S))        # width of front/back rects in atlas
FH = int(round((R1 - R0) * S))


def fill_bg(crop):
    """Replace white background (and the antialiased halo) by the nearest sword colour."""
    fg = (crop.astype(int).sum(2) < 3 * 232)
    fg = cv2.erode(fg.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    idx = ndi.distance_transform_edt(~fg, return_distances=False, return_indices=True)
    return crop[idx[0], idx[1]]


front = fill_bg(rgb[R0:R1, FX0:FX1])
back = fill_bg(rgb[R0:R1, BX0:BX1][:, ::-1].copy())
# dark-metal swatch sampled from the reference's darkest sword pixels
dark = rgb[(lum < 3 * 70) & (lum > 3 * 18)]
base = np.median(dark, axis=0).astype(np.uint8) if len(dark) else np.array([34, 30, 36], np.uint8)
atlas = np.zeros((AT, AT, 3), np.uint8); atlas[:] = base
rng = np.random.default_rng(7)
SW_X0 = 2 * FW + 20
sw = np.clip(base.astype(int) + rng.normal(0, 3, (AT - 40, AT - SW_X0 - 20, 1)), 0, 255).astype(np.uint8)
atlas[20:AT - 20, SW_X0:AT - 20] = sw
atlas[:FH, :FW] = cv2.resize(front, (FW, FH), interpolation=cv2.INTER_CUBIC)
atlas[:FH, FW:2 * FW] = cv2.resize(back, (FW, FH), interpolation=cv2.INTER_CUBIC)
Image.fromarray(atlas).save(f'{TEXDIR}/sword_basecolor.png')

# emissive map = strong red regions of the atlas (the reference's glowing cracks, seams and gems)
a = atlas.astype(int)
redm = ((a[..., 0] > 105) & (a[..., 1] < 90) & (a[..., 2] < 90) & (a[..., 0] > 1.7 * a[..., 1])).astype(np.float32)
redm = cv2.GaussianBlur(redm, (0, 0), 0.9)
emis = (atlas * redm[..., None]).astype(np.uint8)
Image.fromarray(emis).save(f'{TEXDIR}/sword_emissive.png')
# roughness: glossy where lit/bright metal, rougher in dark fill (packed as grey, Non-Color)
g = cv2.cvtColor(atlas, cv2.COLOR_RGB2GRAY).astype(np.float32)
rough = np.clip(0.62 - g / 255.0 * 0.9, 0.28, 0.65)
Image.fromarray((rough * 255).astype(np.uint8)).save(f'{TEXDIR}/sword_roughness.png')

# ---------------- Blender ----------------
bpy.ops.wm.open_mainfile(filepath=SRC_BLEND)


def img(path, cs):
    im = bpy.data.images.load(os.path.abspath(path), check_existing=True)
    im.colorspace_settings.name = cs
    im.pack()
    return im


mat = bpy.data.materials.new('MAT-sword'); mat.use_nodes = True
nt = mat.node_tree; bs = nt.nodes['Principled BSDF']
tb = nt.nodes.new('ShaderNodeTexImage'); tb.image = img(f'{TEXDIR}/sword_basecolor.png', 'sRGB')
te = nt.nodes.new('ShaderNodeTexImage'); te.image = img(f'{TEXDIR}/sword_emissive.png', 'sRGB')
tr = nt.nodes.new('ShaderNodeTexImage'); tr.image = img(f'{TEXDIR}/sword_roughness.png', 'Non-Color')
for t in (tb, te, tr): t.interpolation = 'Linear'
nt.links.new(tb.outputs['Color'], bs.inputs['Base Color'])
nt.links.new(tr.outputs['Color'], bs.inputs['Roughness'])
nt.links.new(te.outputs['Color'], bs.inputs['Emission Color'])
bs.inputs['Emission Strength'].default_value = 2.2
bs.inputs['Metallic'].default_value = 0.55

gem_mat = bpy.data.materials.new('MAT-sword_gem'); gem_mat.use_nodes = True
gb = gem_mat.node_tree.nodes['Principled BSDF']
gb.inputs['Base Color'].default_value = (0.55, 0.0, 0.03, 1)
gb.inputs['Emission Color'].default_value = (0.9, 0.0, 0.03, 1)
gb.inputs['Emission Strength'].default_value = 2.6
gb.inputs['Roughness'].default_value = 0.15

LATHE = ('grip', 'cap', 'spike')
SW_UV = ((SW_X0 + 120) / AT, 1 - 0.5)


def uv_front(x, z, back=False):
    col = x / SCALE + CX
    row = ZERO - z / SCALE
    px = (col - FX0) * S + (FW if back else 0)
    py = (row - R0) * S
    lo = FW if back else 0
    px = min(max(px, lo + 1.5), lo + FW - 1.5); py = min(max(py, 1.5), FH - 1.5)
    return (px / AT, 1 - py / AT)


for ob in list(bpy.data.objects):
    if ob.type != 'MESH': continue
    me = ob.data
    me.materials.clear()
    if 'gems' in ob.name:
        me.materials.append(gem_mat); continue
    me.materials.append(mat)
    uvl = me.uv_layers.get('UVMap') or me.uv_layers.new(name='UVMap')
    lathe = any(k in ob.name for k in LATHE)
    nfront = nback = nside = 0
    for p in me.polygons:
        ny = p.normal.y
        if lathe: mode = 'front' if ny <= 0 else 'back'
        else: mode = 'front' if ny <= -0.35 else ('back' if ny >= 0.35 else 'side')
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if mode == 'side':
                j = 0.04 * ((co.x * 977 + co.z * 613) % 1.0)
                uvl.data[li].uv = (SW_UV[0] + 0.05 * (j - 0.02), SW_UV[1] + 0.05 * j)
            else:
                uvl.data[li].uv = uv_front(co.x, co.z, back=(mode == 'back'))
        if mode == 'front': nfront += 1
        elif mode == 'back': nback += 1
        else: nside += 1
    me.uv_layers.active = uvl
    print('UV', ob.name, 'front', nfront, 'back', nback, 'side', nside)

bpy.ops.wm.save_as_mainfile(filepath=OUT + '.blend')
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=OUT + '.glb', export_format='GLB', use_selection=True, export_apply=True,
                          export_image_format='AUTO')
print('SAVED', OUT)
