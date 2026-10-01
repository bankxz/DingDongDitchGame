# Kitsune (Roblox creature)

Nine-tailed kitsune: indigo fur with glowing cyan markings, cyan legs and tail tips,
glowing red eyes, red rope harness with halo loop, chest gem and bead tassels.

| | |
|---|---|
| Triangles | 9,932 (limit 10k) |
| Bones | 60 (all deform; 4 per tail, eye bones), max 3 influences / vertex |
| Textures | 2048² colour, normal (OpenGL), roughness, emissive mask, metalness |
| Size | shoulder height 4 studs, ~9 studs wide with tails |
| Animations | Idle 4 s (120 f), Run 0.67 s (20 f), Sleep 5 s (150 f), 30 fps, seamless loops |

Idle: breathing, look-around, ear flicks; the tail fan slowly lifts and spreads while a
wave travels down every tail (phase-offset across the fan). Run: rotary gallop, tails
stream back like banners with rolling waves. Sleep (sleep reference sheet): lying flat and
straight, head resting on the front paws, ears up, eyes closed (Eye bones sink the
lenses), hind legs folded beside the belly, all tails in a layered fan behind - lower ones on the ground, upper ones
arching up, tips curling up - stirring slowly; slow breathing. The harness (incl. the halo
loop) is rigidly attached to the chest - no extra bones, to keep the rig light.

## Files

```
Kitsune.fbx                 rigged, skinned model in rest pose (textures embedded)
Kitsune.blend               source scene (Idle / Run / Sleep actions, packed textures)
Animations/Kitsune_*.fbx    one FBX per animation (same rig)
Textures/T_Kitsune_*.png    SurfaceAppearance maps
roblox/ApplySurfaceAppearance.luau   Studio command-bar setup for the texture maps
source/                     procedural build scripts (Blender 4.2 Python)
validation/                 review renders against the reference sheets
```

## Material slots

`M_Kitsune_Fur_Purple`, `M_Kitsune_Glow_Cyan_EMISSIVE`, `M_Kitsune_TailTips_EMISSIVE`,
`M_Kitsune_Rope_Red`, `M_Kitsune_Ornament_Red`, `M_Kitsune_Eyes_Red_EMISSIVE`.
All slots share one texture atlas; the emissive mask marks what glows.

## Rig

```
Root
└ Hips ─ Spine ─ Chest ─ Neck1 ─ Neck2 ─ Head ─ Ear_L / Ear_R, Eye_L / Eye_R
   │               ├ FrontLegUpper_L/R ─ FrontLegLower ─ FrontPaw
   │               └ Tassel_L/R
   ├ HindLegUpper_L/R ─ HindLegLower ─ HindFoot ─ HindPaw
   └ TailBase ─ Tail1..8_1 ─ _2 ─ _3 ─ _4
```

## Import into Roblox Studio

1. **Model:** Avatar/Home tab → *Import 3D* → `Kitsune.fbx`. Keep "Rig" / skinned
   mesh import on. The file uses Blender unit scale 0.01 (1 Blender unit = 1 stud),
   so the creature imports ~4 studs tall at the shoulder; if your importer settings
   differ, set *Scale Unit* to Stud.
2. **Textures:** upload the five PNGs (Asset Manager → Images), copy their ids into
   `roblox/ApplySurfaceAppearance.luau`, select the imported Model and run the script
   in the command bar.
3. **Glow:** add a `BloomEffect` to Lighting (e.g. Intensity 0.6, Size 24,
   Threshold 0.9) so the emissive cyan fur and red eyes bloom.
4. **Animations:** open the Animation Editor on the imported Model → *Import from
   FBX Animation* → each `Animations/Kitsune_*.fbx` → publish to get the ids.
5. **Play them** with `src/shared/Kitsune.luau`:

```lua
local Kitsune = require(game.ReplicatedStorage.Shared.Kitsune)
local k = Kitsune.new(workspace.Kitsune, {
	Idle = "rbxassetid://...", Run = "rbxassetid://...", Sleep = "rbxassetid://...",
})
k:Play("Idle")
k:Play("Run", 0.15)   -- crossfade
```

## Rebuild

```
python build_kitsune.py -- --out ..            # pip 'bpy' 4.2 module
blender -b -P build_kitsune.py -- --out ..     # or inside Blender 4.2+
```
`--stage model` stops before rigging and writes `_model_stage.blend` for quick reviews.
