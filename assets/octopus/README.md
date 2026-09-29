# Voxel Octopus (Roblox-ready)

A low-poly voxel octopus built in Blender 4.2 from `reference/octopus_reference_sheet.webp`. It's skinned to a 42-bone rig and has two looping clips: **Idle** (90 frames) and **Walk** (36 frames), both at 30 fps.

| | |
|---|---|
| Triangles | **4,124** (budget < 5,000) |
| Bones | 42 (`Root` → `Body` → 8 arms × 5 bones: `Arm1..4_1..5_R/L`) |
| Skin | ≤ 4 influences per vertex, normalised |
| Material | 1 material, 1 UV set, 1024² baked atlas |
| Size | ~7 studs tall, ~10 studs wide (1 Blender unit = 1 stud, unit scale 0.01) |
| Facing | −Y in Blender (Roblox front after the default FBX axis conversion) |

## Files

- `export/Octopus_Rig.fbx`: mesh + rig in the bind pose. Import this one as the model.
- `export/Octopus_Idle.fbx`, `export/Octopus_Walk.fbx`: the same rig with one baked clip each, for the Animation Editor's FBX import.
- `export/Octopus.glb`: mesh + rig + both clips (alternative to FBX).
- `textures/Octopus_Color.png`: baked colour atlas (studs, suckers, eyes, beak).
- `textures/Octopus_Normal.png`: baked tangent-space normal map (OpenGL / +Y, which is Roblox's convention) for the stud relief.
- `Octopus.blend`: source scene with the textures packed, `Idle`/`Walk` actions and NLA tracks.
- `source/`: scripts that rebuild everything from scratch (see below).
- `previews/`: renders of the six reference views, `idle.gif`, `walk.gif`, and the silhouette `overlay.png` and `fit_report.json`.

## Stud texture

The studs are texture only; none are modelled. The reference shows **square** raised studs on block panels (not Roblox's classic round studs), so `source/make_textures.py` generates matching tileable square-stud colour and height tiles. Those tiles are box-projected onto the body and run along each arm, then baked into the single colour atlas plus a normal map. The cream suckers on the arm undersides are low-poly blocks (10 tris each), because in the reference they are 3D forms that stick out of the silhouette.

## Import into Roblox Studio

1. **Avatar tab → Import 3D** (or **Home → Import 3D**) → choose `export/Octopus_Rig.fbx`.
   Check that the importer's preview shows roughly 7 × 10 studs, and adjust **Scale** there if you want it bigger or smaller. Import.
2. The model imports as a skinned MeshPart with the bones under it. Add an **AnimationController** with an **Animator** inside it to the model. If you want it to use Humanoid movement, add a Humanoid and a HumanoidRootPart instead.
3. For the stud relief, add a **SurfaceAppearance** to the MeshPart: `ColorMap` = `Octopus_Color.png`, `NormalMap` = `Octopus_Normal.png`. The importer usually applies the colour map as `TextureID` already.
4. **Animation Editor** → select the model → ⋯ → **Import → From FBX Animation** → `Octopus_Idle.fbx`. Turn **Looping** on, then **Publish to Roblox** and copy the asset id. Repeat with `Octopus_Walk.fbx`.
5. Play them:

```lua
local animator = model.AnimationController.Animator
local function load(id)
	local a = Instance.new("Animation")
	a.AnimationId = "rbxassetid://" .. id
	local track = animator:LoadAnimation(a)
	track.Looped = true
	return track
end
local idle, walk = load(IDLE_ID), load(WALK_ID)
idle:Play()
-- when moving: idle:Stop(0.2); walk:Play(0.2)
```

The walk plays in place with no root motion, so you move the model yourself (Humanoid or tween).

## Rebuild

```bash
pip install bpy==4.2.0 "numpy<2" pillow
python3 source/make_textures.py      # stud / sucker / eye tiles
python3 source/build_octopus.py      # mesh, bake, rig, anims, exports, Octopus.blend
python3 source/render_sheet.py reference/octopus_reference_sheet.webp previews
python3 source/fit_check.py reference/octopus_reference_sheet.webp previews previews
```

## Match to the reference (honest notes)

Checked every iteration by rendering all six sheet views and overlaying the silhouettes (`previews/overlay.png`: red = reference only, blue = model only).

- Matched: the palette (sampled directly: `#191856 #33219B #8451EF #D4A9FB #FEECEB`), 8 chunky square-section arms with the cream square suckers, the square-stud surface, the angry slanted white-and-purple eyes under V-shaped brow plates, the dark faceted downward beak, the crown spike, the front and back crest blocks, the temple and side spikes, and the long swept-back fins.
- Not a pixel-exact 1:1. The sheet is illustration art whose views don't agree with each other: each view shows the arms curling in its own picture plane, which no single rigid model can do. The **front view is treated as canonical**. Its silhouette overlap (IoU) is about 0.58, and the other views are about 0.49–0.55. The arm poses in the back, side and top views differ the most.
