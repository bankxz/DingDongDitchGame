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
- **3,418 triangles** (budget: 5,000), down from 4,558 after optimisation, 1 mesh, 1 material, 1 texture.
- 22 bones: Root, Hips, Spine, Chest, Neck, Head, Jaw, Tail1-3, UpperArm/LowerArm/Hand and Thigh/Shin/Foot for each side (L = +X).
- At most 2 bone influences per vertex; every vertex is weighted.
- The body, head and tail are one continuous smooth loft (welded vertices, smooth shading), with weights blending along the spine. The lower jaw and each limb segment are rounded tapered tubes bound rigidly to one bone.

## Stud texture
The texture is **painted, not pixel-style**, and the studs are **in the texture, not modelled**.
- Each region (camo green, leg green, cream, tan, red mouth, tongue, throat, stone spikes, teeth) has **one continuous base colour**, so no coloured squares show.
- On top of that: fine even grain everywhere, plus soft organic camo blotches and moss tufts. These are kept inside each stud cell and fade out before its edge, so neighbouring cells always join without seams.
- Every cell has a Roblox "inlet" stud: a recessed square with a shadowed top wall and a lit bottom wall, shaded over whatever colour is underneath. UVs orient each cell so its "up" points up the surface, so all studs are lit from the same side.
- Atlas: 1024² (Roblox's limit), 4×4 patches of 4×4 cells, 64 px per cell, drawn at 2× and Lanczos-downsampled. Teeth and claws are plain.

## Eyes
- **Eyeball shape:** almond, a long oval running along the head that tapers to points at the front and back.
- **Set into the head:** each eyeball sits in an oval hollow pressed into the head mesh, and its front is level with the head surface.
- **Rim:** a thin lid rim follows the almond outline and thickens on top into a brow ridge.
- **Texture:** projected straight along the eye's axis, with a glowing orange iris, a vertical black reptile slit pupil and a small highlight. The emissive mask makes the iris glow but not the pupil.
- Eyes, rim and socket all move with the Head bone.

## Claws
Each foot has 3 chunky curved talons, centred on the foot. Each one is a symmetric 6-sided cross-section swept along a curve and tapering slowly: the base is buried in the toe, the claw arches over and hooks down to a sharp tip touching the ground. They're plain cream and bound to the foot bone.

## Optimisation
- **Triangles:** 4,558 → 3,418 (−25%) with no visible change:
  - Claws: 6-sided, no hidden base cap.
  - Eyeballs: only the visible front half, flat back hidden in the socket.
  - Eye rims: 12×4 instead of 16×6.
  - Teeth: single-point pyramids with no tip cap or hidden base.
  - Body: fewer rings on the straight trunk and tail; every ring around the head and eye sockets is kept.
  - Legs: 8-sided, no cap on the top ends buried in the body.
- **Vertices:** 3,550 → 2,866.
- **Animation files:** carry just the rig, mesh and keys. The texture is only embedded in `GreenDino.fbx`, and redundant keys are simplified away. Each animation file went from about 1.6 MB to 0.28 MB. The exported poses match the source to within 2 cm on the 13 m model.
- **Checks:** all 30 tooth roots are still inside the jaw mesh. Every vertex is weighted, with at most 2 influences.

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
