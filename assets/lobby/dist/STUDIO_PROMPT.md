Assemble the arena lobby in Roblox Studio for my game, using the kit I built. Work in Studio through the Roblox Studio MCP and follow my installed skills (roblox-studio-mcp, roblox-map-building, roblox-luau, roblox-security). Inspect the place before changing anything, preserve existing gameplay, read back every step, and do not claim something works without checking it in Studio.

## What I have (repo `bankxz/DingDongDitchGame`, branch `claude/amazing-brown-ovxzun`, or `LobbyKit.zip`)
- `assets/lobby/fbx/*.fbx`: 48 models, 1 Blender unit = 1 stud. Each imports as Model → Group (Structure, Canopy, Crates…) → Item → MeshParts named `<Material>__<Item>`. Every glowing piece is its own MeshPart.
- `src/shared/LobbyAssetStyler.luau` (ModuleScript): `styleAll(container)` / `style(model)`.
  - Sets each part's Roblox Material and Color from the part-name prefix (`MATERIALS` table).
  - Rescales each model to its true stud size (`UNITS` table).
  - Tags glowing parts with CollectionService tag `LobbyNeon` and attribute `Neon = true`.
- `src/shared/LobbyLayout.luau` (ModuleScript, data only), with Roblox coordinates relative to a lobby origin where the deck top is Y = 0:
  - `placements`: `{unit, zone, target, yaw, scale, stretch}`.
    - `unit` = FBX/model name.
    - `target` = where the model's axis-aligned bounding-box BOTTOM-CENTRE must end up AFTER rotation.
    - `yaw` = degrees about +Y.
    - `scale` = uniform scale.
    - `stretch` = per-axis scale in the model's own unrotated frame (X, Y, Z).
  - `parts`: island geometry to create as plain Parts: `{name, zone, shape "Block"|"Cylinder", center, size, material, color}`. For Cylinder, size is {X diameter, Y height, Z diameter} with a VERTICAL axis. A Roblox cylinder's axis is X, so build it as Size (height, diameter, diameter), rotated 90° about Z.
  - `spawn` = SpawnLocation position.
  - `scaleRigs` = 5-stud reference-figure positions, used only for scale checks.
  - `triggers` = `DuelsTeleportZone` and `PracticeTeleportZone` boxes in front of the two mode portals.
- The project uses Rojo (`default.project.json`): `src/shared` → ReplicatedStorage.Shared, `src/server` → ServerScriptService.Server, `src/client` → StarterPlayerScripts.Client. Keep the Workspace Baseplate unless I say otherwise.

## Steps
1. **Inspect.** Look at the place: Workspace, ServerStorage, ReplicatedStorage, Lighting, existing scripts and spawns. Tell me what is there before changing anything.
2. **Import the kit.** Bulk-import all FBX files with the 3D Importer into `ServerStorage.LobbyKit`, keeping each file as a Model named after the file (e.g. `Lobby_ArenaGate`) and keeping the hierarchy.
   - Read back: list every model, its part count, and its bounding-box size compared with `UNITS[name].size`.
   - Check the models are upright (Y up), not rotated. Report any importer rename, flattening or rotation; don't work around it silently.
   - If MCP cannot import FBX, stop and give me exact manual import steps, then continue once I confirm.
3. **Style the kit once.** Run `require(game.ReplicatedStorage.Shared.LobbyAssetStyler).styleAll(game.ServerStorage.LobbyKit)`.
   - If styled models are still the wrong size or rotated, fix the kit copies first.
   - Set collision: glowing, banner and glass parts CanCollide = false. Use CollisionFidelity Box or Hull on small props, and leave the gate, arches and shops on Default so the openings stay walkable.
4. **Write `src/shared/LobbyAssembler.luau`** (ModuleScript), with `build(origin: Vector3?)`. Default origin is `Vector3.new(0, 60, 0)`, so the island floats above the Baseplate. It must:
   - delete and recreate `workspace.Lobby`, with one Folder per zone;
   - for each placement:
     - clone `ServerStorage.LobbyKit[unit]`, then apply `scale` via `Model:ScaleTo`;
     - apply `stretch`, scaling each part's Size and its offset from the model's bounding-box bottom-centre;
     - compute the world-axis-aligned box from every part's 8 corners, and take its bottom-centre B;
     - rotate about B by `yaw`, then move B to `origin + target` with `PivotTo(CFrame.new(target) * CFrame.Angles(0, rad(yaw), 0) * CFrame.new(-B) * pivot)`;
     - anchor every part;
   - create every PartSpec as an anchored Part (Marble / SmoothPlastic / Slate / Neon materials, colours from the table);
   - create an invisible SpawnLocation at `spawn`;
   - create the two trigger Parts: Transparency 1, CanCollide false, CanTouch true, Anchored, named exactly as in `triggers`;
   - put temporary scale-reference figures in `workspace.MapReferences`, easy to delete;
   - **read back:** for each placement, assert the actual box bottom-centre is within 0.05 studs of `origin + target`, and print a summary per zone.

   Run it from the command bar.
5. **Verify visually.** Take screenshots from:
   - the spawn plaza looking north down the road: arches, the EVENTS banner, 12 ability pedestals per side and the arena gate at the end;
   - the four arch openings: red path to DUELS and yellow path to PRACTICE on the west, cyan paths to the Market and Craft shops on the east;
   - an aerial view of the floating island with the castle islands in the sky.

   Then:
   - playtest-walk from the spawn to the gate, through each opening, and around the balustrade;
   - fix holes, floating parts, blocked paths, camera clipping and flickering faces;
   - tell me the part count and anything that looks wrong.
6. **Lighting.** Set a bright anime-fantasy look in `default.project.json` (Lighting properties plus Atmosphere / Bloom / ColorCorrection children), so Rojo does not overwrite it:
   - ShadowMap technology, ClockTime about 14, soft lavender ambient;
   - restrained bloom, so the neon glows without washing out.

   Check that the red Duels and yellow Practice portals keep their colours.
7. **Teleports.** Ask me for the Duels and Practice place IDs. Then add a server script (`src/server`) that listens to `DuelsTeleportZone` / `PracticeTeleportZone` Touched events, debounced per player, and uses `TeleportService:TeleportAsync` with `pcall`, a retry and a client-visible message on failure.
   - Follow roblox-security: server-authoritative, no client-trusted remotes.
   - Do not add placeholder IDs.
8. **Optional texture.** If I upload `textures/cobblestone_albedo.png` and `cobblestone_normal.png`, paste their asset IDs into `TEXTURES.cobblestone` in `LobbyAssetStyler` and re-run `styleAll`. Until then, cobble floors stay plain Slate.
9. **Wrap up.**
   - Commit the new and changed Luau files to the branch.
   - Do not commit the place file.
   - Report what was built, what was verified in Studio (with screenshots), and what still needs me: teleport IDs, the texture upload, and deleting the reference figures before publishing.
