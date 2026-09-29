# Stud Drake (Roblox-ready)

A blue sea-serpent drake built from `reference/drake_reference_sheet.png`. It has a stud texture, a rig, and looping idle and walk animations.

| | |
|---|---|
| Triangles | 3,866 (limit < 5,000) |
| Mesh | one skinned mesh, one material, one 1024² texture set |
| Rig | 22 bones: Root, spine and neck chain, Head, Jaw, 7 tail bones, 8 flipper bones. At most 2 bone influences per vertex. |
| Rest pose | neutral bind pose: body straight in top view, side-view profile, jaw open as in the reference |
| Animations | `Drake_Idle` (120 f @ 30 fps, loops) and `Drake_Walk` (48 f @ 30 fps, slither with alternating flipper strokes, loops, in place) |
| Size | about 8.5 m long, 2.9 m tall (about 30 studs long when imported in metres) |
| Fins per side | 8 dorsal (on the centreline), 4 side flippers, 6 tail fins, matching the reference fin table |

## Files

- `Drake.fbx`: mesh and rig in the rest pose. Import this as the model.
- `Drake_Idle.fbx`, `Drake_Walk.fbx`: the same rig with one baked animation each, for the Animation Editor.
- `Drake.blend`: the source scene (textures packed; both actions kept as NLA tracks and fake-user actions).
- `textures/Drake_Color.png`: base colour with the stud shading baked in. Use it on its own as a `TextureID`, or as the `SurfaceAppearance.ColorMap`.
- `textures/Drake_Normal.png`: stud normal map (OpenGL / +Y, which Roblox expects), for `SurfaceAppearance.NormalMap`.
- `textures/Drake_Roughness.png`: flat roughness map for `SurfaceAppearance.RoughnessMap` (optional).
- `textures/Drake_FlatColor.png`, `textures/Drake_EyeGlowMask.png`: helper maps (flat colours without studs, and the eye mask used for the glow in Blender).
- `validation/`: renders of the model next to the reference, plus animation contact sheets.
- `source/`: the procedural build scripts (Blender 4.2 / `bpy`).

## Importing into Roblox Studio

1. **Avatar → Import 3D** (the 3D Importer), then pick `Drake.fbx`. If the size looks wrong, set *File Dimensions / Scale Unit* to **Meter**. The model is about 30 studs long.
2. The importer creates a MeshPart with its Bones. If the texture isn't applied automatically, add a `SurfaceAppearance` to the MeshPart and set `ColorMap = Drake_Color.png` and `NormalMap = Drake_Normal.png`. (A plain `TextureID = Drake_Color.png` also works, and the studs still show because their shading is baked into the colour map.)
3. For the animations, open the model in the **Animation Editor**, choose **⋯ → Import → From FBX Animation**, and pick `Drake_Idle.fbx`. Publish it, then do the same for `Drake_Walk.fbx`. Bone names match the model exactly.
4. Both clips loop and play in place. Set `Looped = true` and move the model with your own controller script while the walk track plays.

## Stud texture

The studs are **texture only**, not modelled. They come from the MIT-licensed [dudeax/Roblox-HD-Studs](https://github.com/dudeax/Roblox-HD-Studs) square-stud maps (`source/studs/`, licence included). The build script tiles them in UV space at a fixed 0.22 m world spacing, so stud size stays the same across the whole creature. Mirrored left/right faces share UV space, so each stud gets about 21 px on the 1024 atlas. Colours are the six swatches sampled from the reference palette (#09236F, #0542DF, #14C7FA, #0FBCAF, #9CF3E4, #FEF7EE).

## Rebuilding

```bash
pip install bpy==4.2.0 numpy pillow opencv-python-headless
cd source
python3 build_drake.py                 # writes ../Drake.blend, ../*.fbx, ../textures/*
python3 render_views.py ../validation  # multiview validation renders
python3 render_anim_sheet.py ../validation
```

Shape parameters live in `source/drake_geo.py`: body profile `STATIONS`, head loft `HEAD_ST`, and the `DORSAL`, `SIDE` and `TAIL` fin tables. Animation curves and the hero `BASE_POSE` live in `source/build_drake.py`.

## Known differences from the reference

The reference is a brick-by-brick render of several thousand individual bricks. Under the 5k-triangle budget, the model approximates that brick look in three ways: raised brick plates on the flanks, per-face navy/royal brick colouring, and brick seams baked into the texture. Individual bricks are not modelled. What still differs:

- The fins are faceted crystal leaves, not stepped brick stacks, so their edges are straight rather than jagged.
- The front flippers form a crescent from three segments. The reference arc is smoother and rounder.
- The reference sheet's views don't agree with each other: the front view shows the body curling round beside the head, and the top view shows a much thinner body than the 3/4 view. The build follows the side and 3/4 views for the body and the front view for the head.
- The side, front and top reference views are posed. The FBX rest pose is kept neutral for animation, and the `Drake_Idle` pose reproduces the reference 3/4 hero pose.
