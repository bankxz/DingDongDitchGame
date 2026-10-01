# Roblox import, performance and pet notes

## Import
- **Avatar → Import 3D** with `Name.fbx`; set **File Dimensions / Scale Unit = Studs**
  (the exporter writes 1 unit = 1 stud with `FBX_SCALE_NONE`). Rig type: rigged/custom.
- Two skinned MeshParts (body + glow) share one bone set; the importer brings in the embedded
  texture as `TextureID`. Optional: a `SurfaceAppearance` with ColorMap + NormalMap from the atlas.
- Glow part: `Material = Neon` (glow; may wash out texture detail like pupils) or `Glass` /
  `Transparency ≈ 0.15` (translucent ice). Roblox has no soft bloom like concept renders - say so.
- Clips: Animation Editor → ⋯ → Import → From FBX Animation with each `Name_<Clip>.fbx`, publish,
  play via `AnimationController` + `Animator`, `Looped = true`.

## Budgets that worked
- ≤ 5,000 tris per pet (body ~3.4k + glow ~1.5k), 1024² atlas, ~41 bones, ≤ 3 weights/vertex.

## Performance (pets in pens)
- Skinned-animation cost scales with bones × vertices × number of animating instances, not with
  what the motion looks like - a flying idle costs the same as a standing idle **if** the flight
  is inside the animation (Torso lifts, Root fixed).
- What *does* cost more: moving the model every frame from scripts/physics (BodyMovers, tweens,
  server-side CFrame updates replicate), particles/trails/lights on wings.
- Pets: anchor the model, `CanCollide`/`CanQuery` off on MeshParts, play animations on the
  client, stop animating when far/off-screen (StreamingEnabled helps), test the worst case
  (full server, every pen full) in the MicroProfiler on a low-end phone.
