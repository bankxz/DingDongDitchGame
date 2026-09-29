# Voxel Sea Drake (Roblox-ready)

A low-poly voxel sea drake built in Blender 4.2 from `reference/drake_reference_sheet.webp`. It's skinned to a 26-bone rig and has two looping clips: **Idle** (90 frames) and **Walk** (40 frames, an in-place slither with paddling fins), both at 30 fps.

| | |
|---|---|
| Triangles | **2,242** total (budget < 5,000): body 1,510 + spikes 732 |
| Meshes | `Drake` (body) and `Drake_Spikes` (every crystal spike and fin), both skinned to the same rig |
| Bones | 26: `Root` → `Chest` → `Neck1` → `Neck2` → `Head` → `Jaw`; `Spine1-5`, `Tail1-4`, `TailFan`; `Limb1_1/2_R/L`, `Fin2-4_R/L` |
| Skin | ≤ 4 influences per vertex, normalised |
| Texture | one 1024² baked colour atlas + normal map, shared by both meshes |
| Size | ~30 studs long (1 Blender unit = 1 stud, unit scale 0.01) |
| Facing | −Y in Blender |

## Rest pose (animation-ready)

The bind pose is the serpent equivalent of a T-pose: a straight spine lying flat, the head level, limbs and fins spread out, and the jaw relaxed. The sheet's pose (neck raised in an S, head up, jaw wide, tail tip lifted) is built into the animations, and is also saved as the `RefPose` action in the `.blend`. See the last row of `previews/`: `sheet.png` is in the reference pose, and the rest pose is what you get with no animation playing.

## Neon spikes

The spikes and fins are a separate MeshPart, `Drake_Spikes`. After importing, select it and set **Material = Neon** and **Color** to the glow you want (the sheet's cyan is `#14C7FA`). Don't put a SurfaceAppearance on that part, because a SurfaceAppearance overrides the Material. `previews/neon_spikes_preview.png` shows roughly how it looks. If you'd rather keep the textured fins, leave `Drake_Spikes` as it imports.

## Stud texture

The studs are texture only; none are modelled. The reference uses **square** raised studs on block panels, not Roblox's classic round studs. `source/make_textures.py` generates matching tileable square-stud colour and height tiles in the sheet's palette (`#09236F #0542DF #14C7FA #0FBCAF #9CF3E4 #FEF7EE`). Those are baked into the atlas plus a normal map.

## Files

- `export/Drake_Rig.fbx`: both meshes + rig in the rest pose. **Import this one.**
- `export/Drake_Idle.fbx`, `export/Drake_Walk.fbx`: the same rig with one baked clip each, for the Animation Editor.
- `export/Drake.glb`: meshes + rig + RefPose/Idle/Walk clips.
- `textures/Drake_Color.png`, `textures/Drake_Normal.png`: the atlas.
- `Drake.blend`: source scene (textures packed, actions + NLA tracks).
- `source/`: scripts that rebuild everything from scratch.
- `previews/`: the six reference views in the sheet pose, `idle.gif`, `walk.gif`, `walk_top.gif`, the Neon preview, and the silhouette `overlay.png` and `fit_report.json`.

## Import into Roblox Studio

1. **Avatar** or **Home** tab → **Import 3D** → `export/Drake_Rig.fbx`. Check the scale in the importer preview (about 30 studs long) and change it if you want.
2. Add an **AnimationController** with an **Animator** inside it to the model.
3. On the `Drake` MeshPart, add a **SurfaceAppearance** with `ColorMap` = `Drake_Color.png` and `NormalMap` = `Drake_Normal.png`. On `Drake_Spikes`, set Neon as described above, or add the same SurfaceAppearance if you want the textured look.
4. **Animation Editor** → select the model → ⋯ → **Import → From FBX Animation** → `Drake_Idle.fbx`. Turn Looping on and publish. Repeat for `Drake_Walk.fbx`.
5. Play them with `Animator:LoadAnimation(...)`. The walk is in place, so you move the model yourself.

## Rebuild

```bash
pip install bpy==4.2.0 "numpy<2" pillow
python3 source/make_textures.py
python3 source/build_drake.py
python3 source/render_sheet.py reference/drake_reference_sheet.webp previews
python3 source/fit_check.py reference/drake_reference_sheet.webp previews previews
```

## Match to the reference (honest notes)

Checked every iteration by rendering the sheet's six views and overlaying the silhouettes.

- **Silhouette overlap (IoU):** front 0.65, back 0.62, left/right 0.60–0.62, top 0.60, 3/4 0.38.
- **v2 rebuild:** the body and head proportions were re-measured column by column from the sheet's side view (body ~4.6 studs tall through the chest, head level with the back, slight neck lift). v1 had a thin body and an over-raised neck. `previews/compare_vs_reference.png` shows the sheet (top) against the model (bottom).
- **Why the 3/4 view is low:** the sheet's 3/4 art shows the body coiled with the tail curled up high. That contradicts its own side and top views, where the body is almost straight, so I matched the side and top views.
- **Matched:** palette, fin counts per side (8 dorsal, 4 side, 6 tail), crystal fin shapes and colours, the head mane and cheek frills, the angry slit eyes under brow plates, cream teeth and belly, and the crescent front arms with claws.
- **Not a pixel-exact 1:1:** the reference is illustration art. The remaining differences are mainly finer head detail and exact fin placement.
