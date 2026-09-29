# Lava Scorpion (Roblox-ready, rigged + animated)

Blocky lava scorpion built in Blender 5.0 from the reference sheet. Features: charcoal rock cubes with Roblox **stud texture**, glowing lava cracks, glowing eyes, 2 pincers, 8 legs, 6 tail segments and a stinger.

| | |
|---|---|
| Triangles | **2,784** (budget < 5,000) |
| Bones | 41 (Root, Body, Tail1–6, Stinger, Arm1/Arm2/Hand/Finger ×2, Leg1–4 ×3 segments ×2 sides) |
| Skinning | Rigid: 1 bone per vertex (no weight bleeding in Roblox) |
| Texture | One 1024×1024 atlas; the studs are **texture only**, not modelled |
| Animations | `Idle` (121 frames @ 30 fps, 4 s loop), `Walk` (33 frames @ 30 fps, in-place loop) |
| Rest pose | Neutral stance, legs splayed and claws forward (the scorpion equivalent of a T-pose) |

## Files
- `LavaScorpion.blend`: the Blender source (armature `LavaScorpion`, mesh `GEO-LavaScorpion`, actions `Idle` and `Walk` plus NLA tracks)
- `export/LavaScorpion.fbx`: rig, skinned mesh and embedded texture in rest pose. **Import this one first.**
- `export/LavaScorpion_Idle.fbx` / `export/LavaScorpion_Walk.fbx`: the same rig, one animation each
- `export/LavaScorpion.glb`: alternative glTF with both animations
- `textures/LavaScorpion_Color.png`: colour map, with the lava glow baked in (embedded in the FBX)
- `textures/LavaScorpion_Normal.png`: optional stud normal map for a `SurfaceAppearance`
- `textures/LavaScorpion_Emission.png`: glow mask (used in Blender; Roblox import ignores it)
- `validation/`: reference-vs-model comparison sheets and animation contact sheets
- `source/`: scripts that rebuild everything (`make_textures.py`, `build_scorpion.py`, `animate.py`, `export_roblox.py`, `render_views.py`)

## Importing into Roblox Studio
1. **Avatar tab → Import 3D** (or File → Import 3D) → `export/LavaScorpion.fbx`.
   - Rig General: on. The importer creates a Model with the MeshPart, the Bones and an AnimationController.
   - The texture is embedded. To add the stud normal map, put a `SurfaceAppearance` on the MeshPart with ColorMap = `LavaScorpion_Color.png` and NormalMap = `LavaScorpion_Normal.png`.
   - Scale: the file is authored in metres (about 4.7 m long, 2.9 m tall). Change the importer's scale if you want it bigger or smaller.
2. Select the imported model → **Animation Editor** → ⋯ → **Import → From FBX Animation** → `LavaScorpion_Idle.fbx`. Set it to loop, then Publish to Roblox.
3. Do the same with `LavaScorpion_Walk.fbx`.
4. For the lava glow, turn on `Lighting.Bloom`. The seams and claws are bright in the colour map, so they read as glowing.

Example playback (server `Script` inside the model):
```lua
local animator = script.Parent:FindFirstChildWhichIsA("AnimationController"):FindFirstChildWhichIsA("Animator")
local idle = Instance.new("Animation"); idle.AnimationId = "rbxassetid://IDLE_ID"
local walk = Instance.new("Animation"); walk.AnimationId = "rbxassetid://WALK_ID"
local idleTrack, walkTrack = animator:LoadAnimation(idle), animator:LoadAnimation(walk)
idleTrack.Looped, walkTrack.Looped = true, true
idleTrack:Play()
```

## Rebuilding
```bash
pip install bpy==5.0.1 "numpy<2" pillow
cd source
python3 make_textures.py && python3 build_scorpion.py && python3 animate.py && python3 export_roblox.py
python3 render_views.py ../validation          # reference-matching validation renders
```

## Credits
Stud normal and AO maps: [dudeax/Roblox-HD-Studs](https://github.com/dudeax/Roblox-HD-Studs), MIT licence (`source/studs/LICENSE-Roblox-HD-Studs.txt`).
