# Haori swordsman (R6) — build notes

- Final low-poly: `blender/lowpoly/Haori_LowPoly_NoHair.blend` — 7,827 gear tris + 1,110 rig, 8 meshes, colour + normal map per mesh.
- High-detail source: `blender/parts/Haori_Final_NoHair.blend` (164k tris).
- No hair (add a UGC hair in Studio). Face: ChatGPT decal set (prompt in chat).
- Studio: MeshPart + SurfaceAppearance (ColorMap `*_Color.png`, NormalMap `*_Normal.png`). Not tested in Studio yet.

![[lowpoly_all_angles.png]]

## Lessons
See skill `roblox-outfit-from-sheet` (skills/roblox-outfit-from-sheet/SKILL.md): part-by-part with sign-off, registered overlays, fold lobes not boxes, continuous trim, clipping check, painted cel textures, low-poly bake to 8-10k.
