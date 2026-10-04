-- Studio command bar: select the imported MeshPart, upload Color/Normal/Emissive.png as Images first,
-- paste the asset ids below, then run this. (SurfaceAppearance maps can only be set in Studio.)
local sel = game.Selection:Get()[1]
local sa = Instance.new("SurfaceAppearance")
sa.ColorMap = "rbxassetid://COLOR_ID"
sa.NormalMap = "rbxassetid://NORMAL_ID"
sa.EmissiveMaskTexture = "rbxassetid://EMISSIVE_ID"   -- leaf rims, eyes and gem glow
sa.EmissiveStrength = 1.5
sa.EmissiveTint = Color3.new(1, 1, 1)
sa.Parent = sel
