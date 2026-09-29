# Ice Dragon (three-headed, Roblox-ready)

A low-poly, rigged and animated version of the three-headed ice dragon concept sheet.
It uses the Roblox stud look (the studs are texture, not geometry).

| File | What it is |
|---|---|
| `IceDragon.fbx` | Mesh, rig and both clips (`Idle`, `Walk`). Use this with the Roblox **3D Importer**. |
| `IceDragon_Idle.fbx` / `IceDragon_Walk.fbx` | One clip each, for **Animation Editor → ⋯ → Import → From FBX Animation**. |
| `IceDragon.glb` | Same model and clips as glTF. |
| `IceDragon.blend` | Blender 4.2 source scene. |
| `textures/IceDragon_Color.png` | 1024² colour atlas with Roblox studs baked in (works as a plain `TextureID`). |
| `textures/IceDragon_Normal.png` | Matching stud normal map (optional, for `SurfaceAppearance`). |
| `source/*.py` | Build scripts that regenerate everything (see below). |
| `validation/` | Renders compared with the reference, and animation contact sheets. |

## Stats
- **4,364 triangles** (the limit is 5,000). `IceDragon_Body` has 2,876 and `IceDragon_Ice` has 1,488.
- **41 bones**, with at most 3 weights per vertex:
  - Root, Torso, Pelvis
  - 3 necks × 3 bones, plus Head and Jaw for each head
  - UpperArm, Forearm and Hand for each front leg
  - Thigh, Shin and Foot for each back leg
  - Wing1, Wing2 and Wing3 for each wing
  - Tail1 to Tail5
- About 15.6 × 19.4 × 12.1 studs (W × L × H), with 1 Blender unit = 1 stud.
- Rest pose: legs straight and apart, wings spread clear of the body, jaws open, tail straight. No limb touches another limb, so each bone deforms its own part cleanly.
- Clips at 30 fps, both loop:
  - `Idle` (90 frames): breathing, the necks sway out of step, one jaw snap per head, wing flex, tail sway. The feet stay locked in place.
  - `Walk` (40 frames, walks in place): the legs step in the order back-left, front-left, back-right, front-right. The feet plant flat, and the body, necks, wings and tail move in time. It was solved with IK and then baked to plain keys, so no constraints get exported.

## Importing into Roblox Studio
1. **Avatar → Import 3D** (or File → Import 3D), then pick `IceDragon.fbx`.
2. In the importer, set **File Dimensions / Scale Unit = Studs**. The dragon should then be about 12 studs tall. Rig type: *Rigged / Custom*.
3. The importer brings the texture in automatically. The model becomes one Model with two skinned MeshParts sharing the bones.
4. To get the ice glow, select the `IceDragon_Ice` MeshPart and try `Material = Neon` or `Glass`, or add a light-blue `PointLight`.
5. Animations: open the **Animation Editor** on the model. Use **Import → From FBX Animation** with `IceDragon_Idle.fbx` and then `IceDragon_Walk.fbx`, and publish each one. Play them with an `AnimationController` + `Animator`, and set `Looped = true`.

## Rebuilding
```bash
pip install bpy==4.2.0 pillow numpy
git clone https://github.com/dudeax/Roblox-HD-Studs /tmp/studs      # MIT-licensed stud texture source
python3 source/make_atlas.py /tmp/studs textures    # builds the stud texture atlas
python3 source/build_dragon.py .                    # builds the model, rig and animations -> IceDragon.blend
python3 source/export_dragon.py .                   # exports the FBX and GLB files
python3 source/verify_export.py .                   # re-imports the exports and checks tris, bones and clips
python3 source/render_views.py . validation         # renders the validation views
```

## Credits
The stud relief comes from [dudeax/Roblox-HD-Studs](https://github.com/dudeax/Roblox-HD-Studs) (MIT, © 2024 dudeax).

## Known differences from the concept sheet
The concept art is a high-detail voxel render made of thousands of separate blocks and several hundred crystals. At under 5k triangles, this model keeps these things from it:
- the silhouette and proportions
- three heads with open fanged mouths and glowing eyes
- the crystal crests and spine
- the gold diamond chest gem
- the gold wing joints with gems
- the gold shoulder, ankle and toe bands
- the white claws
- the crystal fan on the tail
- the palette, sampled from the sheet

These are simplified:
- The neck and body are faceted lofts, not individual blocks.
- There are fewer crystals, and each one is bigger.
- The wing membrane uses the stud tile instead of the scale pattern.
- The glow is emissive in Blender, but Roblox needs Neon or lights to show it.
