# Verdant Qilin Guardian - Roblox stud-style model

Stylised stud-texture recreation of the "Verdant Qilin Guardian (Grass Boss)" concept sheet.
Built procedurally in Blender (bpy 4.2) with the stud-style kit in `tools/`.

| | |
|---|---|
| Triangles | 3,782 - under the 5k budget |
| Mesh | single skinned mesh `Qilin_Body`; glow comes from the **emissive texture** (`textures/Emissive.png`) |
| Rig | 23 bones, <= 2 weights per vertex. Rest pose = standing neutral pose (legs straight, tail extended, mouth closed) |
| Animations | `Idle` (90 f, loops), `Walk` (40 f, in place, feet planted via baked IK) - 30 fps |
| Texture | 1024x1024 atlas `textures/Color.png` + `Normal.png` + `Emissive.png`. Studs are **texture only** (dudeax/Roblox-HD-Studs, MIT), not geometry |
| Units | 1 unit = 1 stud, Z up, faces -Y |

## Files
- `export/VerdantQilin.fbx` - mesh + rig + both clips (use with the 3D Importer)
- `export/VerdantQilin_Idle.fbx`, `export/VerdantQilin_Walk.fbx` - one clip each (Animation Editor import)
- `export/VerdantQilin.glb` - same model as glTF
- `out/VerdantQilin.blend` - source scene
- `compare/` - reference vs render side-by-sides
- `build.py`, `anim_clips.py`, `atlas_config.json` - rebuild everything with `python3 build.py`
  (`pip install bpy==4.2.0 pillow numpy`; regenerate the atlas with `tools/make_stud_atlas.py <Roblox-HD-Studs> atlas_config.json textures`)

## Roblox Studio import
1. Avatar tab -> **Import 3D** -> `VerdantQilin.fbx`. Set **File Dimensions / Scale Unit = Studs**. Rig type: custom/rigged.
2. Upload `Color.png`, `Normal.png`, `Emissive.png` and run `roblox/ApplySurfaceAppearance.lua` (ColorMap / NormalMap / EmissiveMaskTexture, EmissiveStrength ~1.5). Add a BloomEffect to Lighting for the soft glow.
3. Animations: Animation Editor -> Import -> From FBX Animation with `VerdantQilin_Idle.fbx` / `VerdantQilin_Walk.fbx`, set `Looped = true`, publish, play on an `AnimationController` + `Animator`.

## Checks run
`check_normals` PASS (0 inside-out islands), `check_clips` Idle/Walk: root drift 0, loop seam 0, feet on ground,
`verify_export`: 3,782 tris, 23 bones, max 2 weights, textures embedded.

## Known differences from the reference
This is a <5k-tri stylisation of a high-detail render, not a pixel copy. See the chat summary for the list.
Stud texture credit: https://github.com/dudeax/Roblox-HD-Studs (MIT).
