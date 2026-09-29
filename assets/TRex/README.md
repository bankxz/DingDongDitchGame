# Red stud T-rex (Roblox)

Blocky voxel T-rex with the Roblox stud texture, rigged, with Idle and Walk animations.

| File | What it is |
|---|---|
| `TRex.fbx` | Skinned mesh + armature in bind pose. Import this one first. |
| `TRex_Idle.fbx` | Rig + Idle loop (60 frames @ 30 fps) |
| `TRex_Walk.fbx` | Rig + Walk loop, in place (40 frames @ 30 fps) |
| `TRex.glb` | glTF with both animations (optional) |
| `TRex.blend` | Blender 4.2 source file. Actions `Idle` and `Walk` are saved with fake users |
| `textures/` | 1024² stud atlas: albedo, normal, emissive |
| `source/` | Scripts that rebuild everything from scratch |

- 3,954 triangles, one mesh, one material, one 1024×1024 texture atlas
- 23 bones: Root, Hips, Spine, Chest, Neck, Head, Jaw, Tail1–6, Thigh/Shin/Foot .L/.R, UpperArm/Forearm .L/.R
- Rigid 1-bone skin weights. The bind pose is neutral, with the legs straight under the hips and the arms relaxed forward. The jaw is open in the bind pose to match the reference; the Jaw bone opens and closes it.
- Real size is about 15 m, which is roughly 53 studs long. The model is exported in metres, so Roblox's importer sizes it correctly. If it comes in too big or too small, change the scale in the importer.

## Import into Roblox Studio
1. **File → Import 3D →** `TRex.fbx`. Keep "Import as rig" on (it is on by default for skinned meshes). You get a Model with a MeshPart and its Bones.
2. The albedo texture is embedded in the FBX. For the raised stud relief, add a `SurfaceAppearance` to the MeshPart. Set ColorMap to `TRex_Studs_Albedo.png` and NormalMap to `TRex_Studs_Normal.png`.
3. Add an `AnimationController` with an `Animator` inside it to the model (the importer usually adds these already).
4. **Avatar → Animation Editor**, select the rig, then **… → Import → From FBX Animation**. Import `TRex_Idle.fbx`, turn Looping on and publish. Do the same for `TRex_Walk.fbx`.
5. Play the animations with `Animator:LoadAnimation(...)`. The walk is in place, so your movement code moves the model.

## Rebuild from source
```
pip install bpy==4.2.0 pillow numpy
git clone https://github.com/dudeax/Roblox-HD-Studs   # MIT stud maps
python3 source/make_atlas.py "Roblox-HD-Studs/2x2 Textures/Smooth/Studs 2x2 Normal.png" \
        "Roblox-HD-Studs/2x2 Textures/Diffuse Maps/Studs 2x2 AO Diffuse.png" textures
python3 source/build_trex.py "$PWD"          # builds TRex.blend (fails if >= 5000 tris)
python3 source/export_roblox.py TRex.blend "$PWD"
python3 source/render_views.py TRex.blend previews/views   # reference-sheet views
```

The stud normal/AO maps are from [dudeax/Roblox-HD-Studs](https://github.com/dudeax/Roblox-HD-Studs) (MIT license, see `textures/STUDS_LICENSE_MIT.txt`).
