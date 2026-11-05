ARENA LOBBY KIT - Roblox import

1) Studio > Avatar/Home > Import 3D: select every file in fbx/ (bulk import).
   Each imports as a Model:  Model > Group (Structure, Canopy, Crates...) > Item (one crate,
   lantern, potion...) > MeshParts.  Every glowing piece is its own MeshPart.
2) Put LobbyAssetStyler.luau (and LobbyLayout.luau) in ReplicatedStorage.Shared as ModuleScripts
   (already wired via Rojo in src/shared if you use the repo).
3) Command bar:  require(game.ReplicatedStorage.Shared.LobbyAssetStyler).styleAll(workspace)
   - sets each part's Roblox Material + Color by its name prefix (edit the MATERIALS table freely)
   - rescales each model to its Blender size (1 Blender unit = 1 stud)
   - tags every neon part "LobbyNeon" (CollectionService) + attribute Neon = true
4) Optional textures: upload textures/cobblestone_albedo.png + _normal.png and paste the asset ids
   into TEXTURES.cobblestone in LobbyAssetStyler (otherwise cobble floors use plain Slate).

LobbyMap_Blender.blend = the whole assembled map in Blender (textures packed in).
LobbyLayout.luau = placement data of the assembled map (studs, Roblox axes).
Not tested inside Roblox Studio (built in a cloud environment without Studio).
