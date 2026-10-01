--[[
	Kitsune texture diagnostic. Select the imported kitsune Model, paste this into
	View > Command Bar, press Enter, then copy everything it prints in the Output
	window and send it back.
]]
local model = game:GetService("Selection"):Get()[1]
if not model then
	warn("Select the kitsune Model in the Explorer first")
	return
end
print("== KITSUNE DIAGNOSTIC ==", model:GetFullName(), model.ClassName)
local parts, bones = 0, 0
for _, d in model:GetDescendants() do
	if d:IsA("Bone") then
		bones += 1
	elseif d:IsA("BasePart") then
		parts += 1
		local info = { d.ClassName, d.Name, "Material=" .. tostring(d.Material), "Color=" .. tostring(d.Color) }
		if d:IsA("MeshPart") then
			table.insert(info, "MeshId=" .. d.MeshId)
			table.insert(info, "TextureID=" .. (d.TextureID ~= "" and d.TextureID or "<none>"))
			table.insert(info, "Size=" .. tostring(d.Size))
		end
		print(table.concat(info, " | "))
		for _, c in d:GetChildren() do
			if c:IsA("SurfaceAppearance") then
				local sa = { "   SurfaceAppearance:", "ColorMap=" .. tostring(c.ColorMap), "NormalMap=" .. tostring(c.NormalMap),
					"RoughnessMap=" .. tostring(c.RoughnessMap) }
				pcall(function() table.insert(sa, "Emissive=" .. tostring((c :: any).EmissiveMaskContent)) end)
				print(table.concat(sa, " | "))
			elseif not c:IsA("Bone") then
				print("   child:", c.ClassName, c.Name)
			end
		end
	end
end
print(("parts=%d bones=%d"):format(parts, bones))
print("== END ==")
