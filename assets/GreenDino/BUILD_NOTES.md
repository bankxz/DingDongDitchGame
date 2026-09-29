# Green Dino (Roblox)

A green crocodile-dinosaur rebuilt from the reference sheet as smooth, rounded low-poly shapes with a painted stud texture (v2: less blocky). It's rigged, has Idle and Walk animations, and is ready to import into Roblox Studio.

## Files
| File | Use |
|---|---|
| `GreenDino.blend` | Blender source: mesh, `GreenDinoRig` armature, `Idle` and `Walk` actions (both kept as NLA tracks) |
| `GreenDino.fbx` | Rigged model in its rest pose. Import with **Roblox 3D Importer** |
| `GreenDino_Idle.fbx` | Idle loop, 90 frames at 30 fps (3 s). Import with **Animation Editor → Import → From FBX Animation** |
| `GreenDino_Walk.fbx` | In-place walk loop, 30 frames at 30 fps (1 s), diagonal trot. Same import route |
| `GreenDino_Color.png` | 1024² painted stud atlas, 64 px per stud cell (also embedded in the FBX). Use as `TextureID` or SurfaceAppearance `ColorMap` |
| `GreenDino_Emissive.png` | Mask for the glowing eyes (optional, for SurfaceAppearance emissive) |
| `validation/` | Reference-vs-model comparison sheet, 8 views, animation contact sheets |
| `source/` | Scripts that rebuild everything: `make_atlas.py` → `build_dino.py` → `export_roblox.py` (`render_views.py` renders the validation images) |

## Stats
- **3,278 triangles** (budget: 5,000), 1 mesh, 1 material, 1 texture.
- 22 bones: Root, Hips, Spine, Chest, Neck, Head, Jaw, Tail1-3, UpperArm/LowerArm/Hand and Thigh/Shin/Foot for each side (L = +X).
- At most 2 bone influences per vertex; every vertex is weighted.
- The body, head and tail are one continuous smooth loft (welded vertices, smooth shading), with weights blending along the spine. The lower jaw and each limb segment are rounded tapered tubes bound rigidly to one bone.

## Stud texture
The texture is **painted, not pixel-style**, and the studs are **in the texture, not modelled**.
- Each region (camo green, leg green, cream, tan, red mouth, tongue, throat, stone spikes, teeth) has **one continuous base colour**, so no coloured squares show.
- On top of that: fine even grain everywhere, plus soft organic camo blotches and moss tufts. These are kept inside each stud cell and fade out before its edge, so neighbouring cells always join without seams.
- Every cell has a Roblox "inlet" stud: a recessed square with a shadowed top wall and a lit bottom wall, shaded over whatever colour is underneath. UVs orient each cell so its "up" points up the surface, so all studs are lit from the same side.
- Atlas: 1024² (Roblox's limit), 4×4 patches of 4×4 cells, 64 px per cell, drawn at 2× and Lanczos-downsampled. Teeth and claws are plain. Eyes are a soft round glow.

## Teeth
Each tooth's root is placed from the actual jaw surface height under all four of its base corners, then sunk 0.55 cells into the gum, so no gap shows. A check that ray-tests all 30 tooth roots against the jaw meshes passes (0 roots outside). Upper teeth use the same bone blend as the gum they sit in, so they stay seated while animating.

## Roblox import
1. **3D Importer**: `GreenDino.fbx`. Rig type is auto-detected as a custom rig and the texture is embedded.
   - The model is about 13 m long in Blender. If the importer's scale doesn't suit you, set its unit/scale option.
2. Open the Animation Editor on the imported rig. Import `GreenDino_Idle.fbx`, then `GreenDino_Walk.fbx`. Set both to **Looping** and publish.
3. Play them with an `AnimationController` + `Animator`.

## Known deviations from the reference
The reference is AI-painted perspective concept art: roughly thousands of individual cubes, with views that don't agree with each other. The model is a faithful low-poly reading of it, not a pixel-exact match:
- v2 swaps the reference's stacked-cube silhouette for smooth rounded forms, as requested. The block look now comes from the texture rather than the geometry. The earlier voxel version is still in git history.
- The front view in the sheet shows a lowered head under a tall hump. The side and hero views (followed here) show the head raised with the jaw wide open.
- Glow only shows in Roblox if you use the emissive mask or a Neon eye part. The colour texture alone just makes the eyes bright orange.
