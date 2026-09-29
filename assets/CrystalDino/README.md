# CrystalDino: crystal-backed dinosaur (Roblox-ready)

A low-poly, rigged and animated model of the blue crystal dinosaur from the reference sheet.
The body, neck, tail, head, jaw and legs are smooth lofted forms. Studded navy and tan armour blocks are laid over them, tilted to follow the surface.
The eyes sit in almond-shaped sockets carved into the head (boolean cut into the head mesh), with a faceted glowing gem eyeball and a white-hot slit pupil. See `previews/eye/eye_closeup.png`.
The brow ridges are flat-topped, square-edged plates boolean-unioned into the skull, and the nose bridge has a slight concave curve. The upper lip is a rounded U-shaped rim that follows the mouth. The mouth is open, with a gum-red palate and throat, a rounded tongue on the jaw floor, and packed rows of teeth seated in the gums (see `previews/head/`).

| | |
|---|---|
| Triangles | **4,786**, under the 5k budget |
| Size | 1 block = 1 stud: about 34 studs long, 15 wide, 15.6 tall (including crystals) |
| Rig | 22 deform bones: Root, Hips, Chest, Neck, Head, Jaw, Tail1-4, and for each side UpperArm, Forearm, Hand, Thigh, Shin, Foot |
| Skinning | Up to 2 bones per vertex. Blends at the neck, hips, tail and knee rings so joints bend smoothly; armour blocks and crystals stay rigid. |
| Bind pose | Neutral stance: legs straight under the body, tail and head level. This is the quadruped equivalent of a T-pose. |
| Animations | `Idle`: 90 frames at 30 fps (3 s loop). `Walk`: 40 frames at 30 fps (1.33 s loop), in place, diagonal gait. |
| Texture | One 1024x1024 atlas: color, normal, roughness and emission maps |

## Files

- `CrystalDino.blend` is the Blender source. It contains the armature with IK foot controllers and the `Idle` and `Walk` actions.
- `export/CrystalDino.fbx` is the rigged mesh in bind pose. Import it with the 3D Importer.
- `export/CrystalDino_Idle.fbx` and `export/CrystalDino_Walk.fbx` are the animations, with IK already baked in. Import them with the Animation Editor.
- `export/CrystalDino.glb` holds the model and both clips, for preview or other engines.
- `textures/` holds the atlas maps. `textures/source/` holds the downloaded stud AO map.
- `scripts/` holds a fully reproducible pipeline:
  `make_textures.py`, then `build_dino.py`, then `render_views.py`, then `export_roblox.py`.
  The scripts run with `pip install bpy==4.2.0` (Python 3.11) or with `blender -b -P`.
- `previews/` contains the reference-vs-model comparison renders and the animation contact sheets.

## Stud texture

The studs are texture, not geometry. They use the Roblox "Inlet" look: a smooth, seamless surface with an even grid of recessed square inlets, one per stud (preview: `previews/stud_texture_closeup.png`). The inlet shading comes from the MIT-licensed [Roblox-HD-Studs](https://github.com/dudeax/Roblox-HD-Studs) set by dudeax (licence in `textures/STUDS_LICENSE_dudeax_Roblox-HD-Studs.txt`), and the recess is also baked into the normal map. UVs are laid out in real stud units (one texture cell = one stud, no shearing), so the inlets are the same size and square on every surface, curved or flat.

## Importing into Roblox Studio

1. **Model:** open Avatar > Import 3D and select `export/CrystalDino.fbx`.
   - Rig type: *Custom*.
   - Set the file dimensions / scale unit to **Studs** so that 1 block = 1 stud. Otherwise, scale the model to taste.
   - The model comes in as two MeshParts sharing one skeleton:
     - `CrystalDino_Body`: stud atlas.
     - `CrystalDino_Glow`: crystals, eyes and glow cracks.
   - For the glowing look, give `CrystalDino_Glow` a `SurfaceAppearance`. Alternatively, set its Material to **Neon** or **Glass**, and/or add a blue `PointLight` to the head and chest.
   - For the best block relief, add a `SurfaceAppearance` to `CrystalDino_Body` with `CrystalDino_Color.png` as ColorMap, `CrystalDino_Normal.png` as NormalMap and `CrystalDino_Roughness.png` as RoughnessMap.
2. **Animations:** select the imported rig and open the Animation Editor. Choose ... > Import > **From FBX Animation**, then pick `CrystalDino_Idle.fbx`. Publish the animation, then repeat with `CrystalDino_Walk.fbx`. Both clips loop seamlessly (the last frame equals the first), so set `Looped = true`.

## Rebuilding

```bash
cd assets/CrystalDino
python3 scripts/make_textures.py textures textures/source/Inlets_2x2_AO_Diffuse_dudeax.png
python3 scripts/build_dino.py         # fails loudly if the triangle budget (<5000) is exceeded
python3 scripts/render_views.py previews/final <dir-with-reference-crops>
python3 scripts/export_roblox.py
```
