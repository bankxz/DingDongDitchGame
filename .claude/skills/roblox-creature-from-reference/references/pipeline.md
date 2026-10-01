# Pipeline code patterns

Working implementation of all of this: `assets/Kitsune/source/` in the DingDongDitchGame
repo (`kitsune_geo.py` forms + accessories, `kitsune_sculpt.py` sculpt/UV/eyes/seating,
`kitsune_paint.py` painter, `kitsune_fur.py` shared fur field, `kitsune_rig.py` rig +
animation + FBX, `build_kitsune.py` orchestration). Copy and adapt rather than rewrite.

## Contents
1. Mesh data + loft builder
2. Sculpt pipeline (remesh -> displace -> mirror -> decimate -> transfer)
3. UVs and texel density
4. Painter (rasterise + supersample)
5. Eyes sealed into sockets
6. Seating accessories
7. Rig, poses, grounding
8. FBX export + verification

## 1. Mesh data + loft builder

`MeshData`: verts, per-vertex skin weights `{bone: w}`, faces, per-face part id,
island id, per-corner UVs and per-corner loft params `(t, th)`.
`Loft(centers, rw, rt, rb, ref, n)` = generalised cylinder with elliptical rings
(separate top/bottom radii); `.point(s, th, offset)` returns surface point, normal,
tangent — use it to place anything on a part (eyes, tufts, harness). Build organic
parts as **closed** lofts (cap_start/cap_end poles) so the remesh can fuse them.

Useful extra builders: `build_tube` (ropes, returns rings for seating),
`build_sphere` (pads, beads, gem), `build_flame_lock` (closed flattened pointed lock
along a direction with a curl — fur tufts, ear spikes), `build_slab` (closed slab
from a 2D outline via ear clipping — flat flame shapes).

## 2. Sculpt pipeline

```python
ob0 = link(mesh_from(md_body))                       # closed source forms
rm = ob0.modifiers.new('Remesh', 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = 0.0085 * S
sm = ob0.modifiers.new('Smooth', 'SMOOTH'); sm.factor = 0.6; sm.iterations = 5
me1 = evaluated_copy(ob0)
co, nr = arrays(me1)
idx, bary = src.nearest(co)                           # BVH to source tris
part, t, th = src.params(idx, bary)                   # per-vertex part + loft params
th = mirror_th(part_names, co[:, 0], th)              # right side uses left params
disp = fur_height(part, t, th) + eye_sockets(co) + skin_bumps(co)   # along normals
me1.vertices.foreach_set('co', (co + nr * disp[:, None] * S).ravel())
ob1 = link(me1)
mir = ob1.modifiers.new('Mirror', 'MIRROR'); mir.use_bisect_axis = (True, False, False)
mir.use_clip = mir.use_mirror_merge = True
ob1.modifiers.new('Smooth', 'SMOOTH')                 # factor 0.5, 2 iterations
dec = ob1.modifiers.new('Decimate', 'DECIMATE'); dec.ratio = target / cur
dec.use_symmetry = True; dec.symmetry_axis = 'X'
me2 = evaluated_copy(ob1)
# transfer: face part by centroid; per-corner (t, th) by nearest point on the SAME
# part (per-part BVH) -- for fused multi-piece parts use per-island BVH so a face
# never interpolates params of two different pieces; unwrap th within each face.
```
Fur displacement uses a shared lock field (rows of pointed shingles in metric
part coordinates) with a raised floor `(0.3 + 0.7*h) * amplitude` so crevices stay
shallow and silhouettes smooth. Set amplitude 0 where the user wants smooth (face,
top of neck).

Skin bump for blending a fused tuft root:
`disp += 0.042 * exp(-(|p - root| / 0.078)^2)` on head/neck vertices only.

## 3. UVs and texel density

Seams at part borders and where |th_a - th_b| > pi, then
`bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.002)`. Scale each island so
`uv_area == world_area_unit * importance^2` (compute world area in the SAME units for
body and accessory islands — a units mismatch made body islands 4x too big once),
then `pack_islands(rotate=True, scale=True, margin=0.0025, shape_method='CONCAVE')`.
Measure: texels/unit = sqrt(uv_area / world_area) * TEX_SIZE per part.

## 4. Painter

Rasterise every triangle into UV space (barycentrics, conservative 0.7 px) at
`size*2`, interpolate t, th, position, normal, part, face; evaluate colour rules in
chunks of ~1.5M samples; coverage-weighted 2x2 box filter down; dilate 12 px;
normal map from height (OpenGL, green = +v); face region votes -> material slot.
Outputs: colour (sRGB), emissive mask, roughness, normal, metalness.

Patterns that worked:
- stroke_mask(polyline, w0, w1) for lightning / flame strokes, `soft_in` masks.
- Flame boundaries (legs, tail, tufts): `bound = base - height * tri_wave(...)**k`
  with per-tongue random height; `smoothstep(bound - e, bound + e, t)`.
- Signed distance to a measured outline (ear border, eye frame) in metric units.
- Root of a fused piece: same colour + lighting multiplier + height as the skin.

## 5. Eyes

```python
def eye_outline(a):      # (along, across) at angle a; shared by lens + painter
    ca, sa = cos(a), sin(a)
    h = (0.020*sa**1.45 if sa > 0 else -0.027*(-sa)**1.2) * (1 - 0.3*max(0, ca)**3)
    return HALF_LEN*ca, h - 0.010*max(0, -ca)**1.5   # inner corner drops
RINGS = ((1.07, -0.010), (1.0, 0.0), (0.70, 0.0035), (0.38, 0.0050))  # scale, lift
```
Each ring vertex = nearest point on the final surface + normal x lift; centre vertex
lifted slightly; UVs radial. Paint iris from eye-frame coords of world position,
not from the per-corner angle.

## 6. Seating accessories

```python
for h in ma.hug:
    if h['kind'] == 'tube':   # move ring centres to surface + n*(r + gap + lift), smooth 3x
    else:                     # rigid block: one delta = target(anchor, clear) - anchor
```

## 7. Rig, poses, grounding

Bones: Root > Hips > Spine > Chest > Neck1 > Neck2 > Head > Ears; legs off
Chest/Hips (Upper > Lower > Paw / Foot > Paw); TailBase > TailN_1.._3; tassels.
Sagittal bones get roll so local X == world X (clean pitch). Pose = dict of
quaternions built from world-axis rotations; `apply(frame)` keys rotation +
location on every bone. Bake every frame, linear interpolation.
Ground: render-evaluate mesh per frame, min z over the PAW vertex mask, shift Root;
for run do it per frame (smoothed) plus a small suspension hop.

## 8. FBX export + verification

```python
bpy.context.scene.unit_settings.scale_length = 0.01
bpy.ops.export_scene.fbx(filepath=p, use_selection=True, object_types={'ARMATURE', 'MESH'},
    apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y',
    add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
    use_armature_deform_only=True, bake_anim=anim, bake_anim_force_startend_keying=True,
    path_mode='STRIP' if anim else 'COPY', embed_textures=not anim)
```
Verify by re-importing each file into an empty scene: bone count, tri count,
material names, action frame range, max influences per vertex.
