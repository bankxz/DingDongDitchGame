# Green Dino (Roblox)

A blocky green crocodile-dinosaur rebuilt from the reference sheet. It's rigged, has Idle and Walk animations, and is ready to import into Roblox Studio.

## Files
| File | Use |
|---|---|
| `GreenDino.blend` | Blender source: mesh, `GreenDinoRig` armature, `Idle` and `Walk` actions (both kept as NLA tracks) |
| `GreenDino.fbx` | Rigged model in its rest pose. Import with **Roblox 3D Importer** |
| `GreenDino_Idle.fbx` | Idle loop, 90 frames at 30 fps (3 s). Import with **Animation Editor → Import → From FBX Animation** |
| `GreenDino_Walk.fbx` | In-place walk loop, 30 frames at 30 fps (1 s), diagonal trot. Same import route |
| `GreenDino_Color.png` | 1024² stud-block colour atlas (also embedded in the FBX). Use as `TextureID` or SurfaceAppearance `ColorMap` |
| `GreenDino_Emissive.png` | Mask for the glowing eyes (optional, for SurfaceAppearance emissive) |
| `validation/` | Reference-vs-model comparison sheet, 8 views, animation contact sheets |
| `source/` | Scripts that rebuild everything: `make_atlas.py` → `build_dino.py` → `export_roblox.py` (`render_views.py` renders the validation images) |

## Stats
- **4,342 triangles** (budget: 5,000), 1 mesh, 1 material, 1 texture.
- 22 bones: Root, Hips, Spine, Chest, Neck, Head, Jaw, Tail1-3, UpperArm/LowerArm/Hand and Thigh/Shin/Foot for each side (L = +X).
- At most 2 bone influences per vertex; every vertex is weighted.
- The limbs are rigid blocky segments, which is the Roblox style. The spine, neck and tail blend smoothly.

## Stud texture
The studs are **painted into the texture, not modelled**. Every block in the atlas has a bevel and a centred raised square stud, matching Roblox's current square stud style. Camo, cream, tan, red mouth and mossy stone patches are packed into 4×4-block tiles. Voxel faces are merged and mapped onto these tiles, so every visible block shows exactly one stud.

## Roblox import
1. **3D Importer**: `GreenDino.fbx`. Rig type is auto-detected as a custom rig and the texture is embedded.
   - The model is about 13 m long in Blender. If the importer's scale doesn't suit you, set its unit/scale option.
2. Open the Animation Editor on the imported rig. Import `GreenDino_Idle.fbx`, then `GreenDino_Walk.fbx`. Set both to **Looping** and publish.
3. Play them with an `AnimationController` + `Animator`.

## Known deviations from the reference
The reference is AI-painted perspective concept art: roughly thousands of individual cubes, with views that don't agree with each other. The model is a faithful low-poly reading of it, not a pixel-exact match:
- Blocks sit on a regular voxel grid with scattered protruding blocks. The reference's cubes are free-floating and jitter more.
- The front view in the sheet shows a lowered head under a tall hump. The side and hero views (followed here) show the head raised with the jaw wide open.
- Glow only shows in Roblox if you use the emissive mask or a Neon eye part. The colour texture alone just makes the eyes bright orange.
