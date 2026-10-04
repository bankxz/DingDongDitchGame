# Verdant Qilin Guardian (Grass Boss) - stud-style model

Procedural Blender build (`build.py`) following the stud-style pipeline: stud texture atlas
(Roblox-HD-Studs, MIT, credit dudeax), olive/brown/cream blocks + faceted leaf plates, glowing
gem/eyes/neon leaves driven by `textures/Emissive.png`.

    python3 tools/make_atlas.py <Roblox-HD-Studs> atlas_config.json textures
    python3 build.py && python3 render.py && python3 export.py

Outputs: `out/Qilin.fbx` (embedded textures), `out/Qilin.glb`, `out/Qilin.blend`.
Roblox: import with Scale Unit = Studs; `Qilin_Glow` MeshPart -> SurfaceAppearance with
`Emissive.png` as emissive mask (or Neon). `compare.py` / `silhouette.py` compare renders to `ref/ref.png`.
Status: close stylised match, not pixel-exact (see session notes).
