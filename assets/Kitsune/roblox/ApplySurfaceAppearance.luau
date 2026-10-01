--[[
	Run ONCE in the Roblox Studio command bar (View > Command Bar) after importing
	Kitsune.fbx and uploading the textures.  SurfaceAppearance texture maps can only
	be set in Studio, not by game scripts at runtime.

	1. Select the imported kitsune Model in the Explorer.
	2. Paste the asset ids of the uploaded textures below.
	3. Paste this whole script into the command bar and press Enter.
]]
local IDS = {
	ColorMap = "rbxassetid://0", -- T_Kitsune_Color.png
	NormalMap = "rbxassetid://0", -- T_Kitsune_Normal.png
	RoughnessMap = "rbxassetid://0", -- T_Kitsune_Roughness.png
	MetalnessMap = "rbxassetid://0", -- T_Kitsune_Metalness.png
	EmissiveMask = "rbxassetid://0", -- T_Kitsune_EmissiveMask.png (cyan markings, tail tips, eyes)
}
local EMISSIVE_STRENGTH = 2 -- glow of the cyan fur / tail tips / red eyes
local EMISSIVE_TINT = Color3.new(1, 1, 1) -- emissive colour comes from the ColorMap

local model = game:GetService("Selection"):Get()[1]
assert(model, "select the kitsune Model first")
local count = 0
for _, part in model:GetDescendants() do
	if part:IsA("MeshPart") then
		-- plain colour texture as a fallback (shows even without SurfaceAppearance)
		pcall(function()
			part.TextureID = IDS.ColorMap
		end)
		local old = part:FindFirstChildOfClass("SurfaceAppearance")
		if old then
			old:Destroy()
		end
		local sa = Instance.new("SurfaceAppearance")
		sa.Name = "Kitsune_SurfaceAppearance"
		sa.ColorMap = IDS.ColorMap
		sa.NormalMap = IDS.NormalMap
		sa.RoughnessMap = IDS.RoughnessMap
		sa.MetalnessMap = IDS.MetalnessMap
		-- emissive mask (newer SurfaceAppearance API; skipped if this Studio build lacks it)
		local ok, err = pcall(function()
			(sa :: any).EmissiveMaskContent = Content.fromUri(IDS.EmissiveMask)
			;(sa :: any).EmissiveStrength = EMISSIVE_STRENGTH
			;(sa :: any).EmissiveTint = EMISSIVE_TINT
		end)
		if not ok then
			warn("Emissive mask not set (" .. tostring(err) .. "); use a Neon/Glow fallback if needed")
		end
		sa.Parent = part
		count += 1
	end
end
print(("Kitsune: SurfaceAppearance applied to %d MeshPart(s)"):format(count))
