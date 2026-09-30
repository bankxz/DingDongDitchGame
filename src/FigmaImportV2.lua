-- Figma -> Roblox GUI converter for the V2 UI (Figma file "Ding Dong Ditch for Eggs — UI System", V2 screens).
-- Input: the JSON tree dumped from Figma (frames / rects / ellipses / text / image fills / instances), coordinates
-- relative to the parent in Figma px. Output: GuiObjects with the same geometry, colours, gradients, strokes, corner
-- radii, fonts and images. Anything that acts as a button (component instances and frames named like buttons) is built
-- as an ImageButton so the client can hook it.
local M = {}

M.Images = {} -- image name -> rbxassetid
M.Native = {} -- image name -> native pixel size (TILE fills)

M.ButtonComponents = {
	Button = true, CloseButton = true, HUDButton = true, PlusButton = true,
}
-- frames that behave as buttons in the design
M.ButtonNames = {
	"Button$", "^Button/", "^Tab/", "^Jump/", "^Sort/", "^Right/", "^Toggle", "^BuySlot", "RobuxPrice$",
	"^ClearButton", "^Setting/", "^Buy/", "^Odd/", "^PetCard/", "^SellCard/", "^Step%d", "^Slot%d", "^EggSlot",
}

local FONT = Font.new("rbxasset://fonts/families/FredokaOne.json", Enum.FontWeight.Regular, Enum.FontStyle.Normal)

local function hex(h)
	return Color3.fromHex(h)
end

local function gradientRotation(tf)
	local a, b, d, e = tf[1][1], tf[1][2], tf[2][1], tf[2][2]
	local det = a * e - b * d
	if math.abs(det) < 1e-6 then
		return 90
	end
	local dx, dy = e / det, -d / det
	return math.deg(math.atan2(dy, dx))
end

local function colorSeq(stops)
	local kps, tps = {}, {}
	for i, s in stops do
		local p = math.clamp(s[1], 0, 1)
		if i > 1 and p <= kps[#kps].Time then
			p = math.min(1, kps[#kps].Time + 0.001)
		end
		table.insert(kps, ColorSequenceKeypoint.new(p, hex(s[2])))
		table.insert(tps, NumberSequenceKeypoint.new(p, 1 - (s[3] or 1)))
	end
	if kps[1].Time > 0 then
		table.insert(kps, 1, ColorSequenceKeypoint.new(0, kps[1].Value))
		table.insert(tps, 1, NumberSequenceKeypoint.new(0, tps[1].Value))
	end
	if kps[#kps].Time < 1 then
		table.insert(kps, ColorSequenceKeypoint.new(1, kps[#kps].Value))
		table.insert(tps, NumberSequenceKeypoint.new(1, tps[#tps].Value))
	end
	while #kps > 20 do
		table.remove(kps, #kps - 1)
		table.remove(tps, #tps - 1)
	end
	return ColorSequence.new(kps), NumberSequence.new(tps)
end

local function place(obj, n)
	local w, h = n.w, n.h
	if n.rot and n.rot ~= 0 then
		local t = math.rad(n.rot)
		local cx = n.x + math.cos(t) * w / 2 + math.sin(t) * h / 2
		local cy = n.y - math.sin(t) * w / 2 + math.cos(t) * h / 2
		obj.AnchorPoint = Vector2.new(0.5, 0.5)
		obj.Position = UDim2.fromOffset(cx, cy)
		obj.Rotation = -n.rot
	else
		obj.Position = UDim2.fromOffset(n.x, n.y)
	end
	obj.Size = UDim2.fromOffset(w, h)
end

local function addCorner(obj, n)
	if n.el then
		local c = Instance.new("UICorner")
		c.CornerRadius = UDim.new(0.5, 0)
		c.Parent = obj
		return
	end
	local cr = n.cr
	if not cr then
		return
	end
	local r = type(cr) == "table" and math.max(cr[1], cr[2], cr[3], cr[4]) or cr
	if r > 0 then
		local c = Instance.new("UICorner")
		c.CornerRadius = UDim.new(0, math.min(r, math.min(n.w, n.h) / 2))
		c.Parent = obj
	end
end

local function addStroke(obj, n, isText)
	if not n.s or #n.s == 0 then
		return
	end
	local p = n.s[1]
	local st = Instance.new("UIStroke")
	st.LineJoinMode = Enum.LineJoinMode.Round
	local sw = n.sw
	if type(sw) == "table" then
		sw = math.max(sw[1] or 0, sw[2] or 0, sw[3] or 0, sw[4] or 0)
	end
	st.Thickness = isText and math.max(1, (sw or 1) * 0.9) or (sw or 1)
	if p.k == "S" then
		st.Color = hex(p.c)
		st.Transparency = 1 - (p.o or 1)
	elseif p.st then
		st.Color = Color3.new(1, 1, 1)
		local g = Instance.new("UIGradient")
		g.Color = (colorSeq(p.st))
		g.Rotation = p.tf and gradientRotation(p.tf) or 0
		g.Parent = st
	end
	if not isText then
		st.ApplyStrokeMode = Enum.ApplyStrokeMode.Border
		pcall(function()
			st.BorderStrokePosition = n.sa == "OUTSIDE" and Enum.BorderStrokePosition.Outer
				or (n.sa == "CENTER" and Enum.BorderStrokePosition.Center or Enum.BorderStrokePosition.Inner)
		end)
	end
	st.Parent = obj
	if type(n.sw) == "table" and p.k == "S" then
		local t, r, b, l = n.sw[1], n.sw[2], n.sw[3], n.sw[4]
		if t == 0 or r == 0 or b == 0 or l == 0 then
			st:Destroy()
			for _, e in { { t, "T" }, { r, "R" }, { b, "B" }, { l, "L" } } do
				if e[1] > 0 then
					local bar = Instance.new("Frame")
					bar.Name = "Edge" .. e[2]
					bar.BorderSizePixel = 0
					bar.BackgroundColor3 = hex(p.c)
					bar.ZIndex = 1000
					if e[2] == "T" then
						bar.Size = UDim2.new(1, 0, 0, e[1])
					elseif e[2] == "B" then
						bar.AnchorPoint = Vector2.new(0, 1)
						bar.Position = UDim2.fromScale(0, 1)
						bar.Size = UDim2.new(1, 0, 0, e[1])
					elseif e[2] == "L" then
						bar.Size = UDim2.new(0, e[1], 1, 0)
					else
						bar.AnchorPoint = Vector2.new(1, 0)
						bar.Position = UDim2.fromScale(1, 0)
						bar.Size = UDim2.new(0, e[1], 1, 0)
					end
					bar.Parent = obj
				end
			end
		end
	end
end

local function imageFor(name)
	return M.Images[name] or ""
end

local function applyFills(obj, n, zbase)
	local fills = type(n.f) == "table" and n.f or {}
	obj.BackgroundTransparency = 1
	local first = true
	for i, p in fills do
		if p.k == "S" or p.k == "L" or p.k == "R" or p.k == "A" or p.k == "D" then
			local target = obj
			if not first then
				target = Instance.new("Frame")
				target.Name = "Fill" .. i
				target.BorderSizePixel = 0
				target.Size = UDim2.fromScale(1, 1)
				target.ZIndex = zbase
				target.Parent = obj
				local c = obj:FindFirstChildOfClass("UICorner")
				if c then
					c:Clone().Parent = target
				end
			end
			first = false
			if p.k == "S" then
				target.BackgroundColor3 = hex(p.c)
				target.BackgroundTransparency = 1 - (p.o or 1)
			else
				target.BackgroundColor3 = Color3.new(1, 1, 1)
				target.BackgroundTransparency = 1 - (p.o or 1)
				local g = Instance.new("UIGradient")
				local cs, ts = colorSeq(p.st)
				if p.k == "R" then
					-- radial: approximate with a light-centre vertical gradient
					local c0, c1 = hex(p.st[1][2]), hex(p.st[#p.st][2])
					cs = ColorSequence.new({
						ColorSequenceKeypoint.new(0, c1),
						ColorSequenceKeypoint.new(0.5, c0),
						ColorSequenceKeypoint.new(1, c1),
					})
					local a0, a1 = 1 - (p.st[1][3] or 1), 1 - (p.st[#p.st][3] or 1)
					ts = NumberSequence.new({
						NumberSequenceKeypoint.new(0, a1),
						NumberSequenceKeypoint.new(0.5, a0),
						NumberSequenceKeypoint.new(1, a1),
					})
					g.Rotation = 90
				else
					g.Rotation = p.tf and gradientRotation(p.tf) or 0
				end
				g.Color = cs
				g.Transparency = ts
				g.Parent = target
			end
		elseif p.k == "I" then
			local id = imageFor(p.img)
			local im = Instance.new("ImageLabel")
			im.Name = "Image"
			im.BackgroundTransparency = 1
			im.Size = UDim2.fromScale(1, 1)
			im.ZIndex = zbase
			im.Image = id
			im:SetAttribute("Img", p.img)
			im.ImageTransparency = 1 - (p.o or 1)
			if p.m == "TILE" then
				im.ScaleType = Enum.ScaleType.Tile
				local s = (M.Native[p.img] or 256) * (p.sf or 1)
				im.TileSize = UDim2.fromOffset(s, s)
			elseif p.m == "FILL" then
				im.ScaleType = Enum.ScaleType.Crop
			elseif p.m == "STRETCH" then
				im.ScaleType = Enum.ScaleType.Stretch
			else
				im.ScaleType = Enum.ScaleType.Fit
			end
			local c = obj:FindFirstChildOfClass("UICorner")
			if c then
				c:Clone().Parent = im
			end
			if first and obj:IsA("ImageLabel") then
				obj.Image = id
				obj:SetAttribute("Img", p.img)
				obj.ScaleType = im.ScaleType
				obj.TileSize = im.TileSize
				obj.ImageTransparency = im.ImageTransparency
				im:Destroy()
			else
				im.Parent = obj
			end
			first = false
		end
	end
end

local function makeText(n, z)
	local t = Instance.new("TextLabel")
	t.Name = n.n
	t.BackgroundTransparency = 1
	t.RichText = n.seg ~= nil
	t.TextWrapped = (n.tx or ""):find("\n") ~= nil or n.h > n.fs * 1.9
	t.FontFace = FONT
	t.TextSize = n.fs or 14
	t.ZIndex = z
	t.TextXAlignment = n.ah == "C" and Enum.TextXAlignment.Center or (n.ah == "R" and Enum.TextXAlignment.Right or Enum.TextXAlignment.Left)
	t.TextYAlignment = n.av == "C" and Enum.TextYAlignment.Center or (n.av == "B" and Enum.TextYAlignment.Bottom or Enum.TextYAlignment.Top)
	local fill = type(n.f) == "table" and n.f[1]
	if fill and fill.k == "S" then
		t.TextColor3 = hex(fill.c)
		t.TextTransparency = 1 - (fill.o or 1)
	elseif fill and fill.st then
		t.TextColor3 = Color3.new(1, 1, 1)
		local g = Instance.new("UIGradient")
		g.Color = (colorSeq(fill.st))
		g.Rotation = fill.tf and gradientRotation(fill.tf) or 90
		g.Parent = t
	else
		t.TextColor3 = Color3.new(1, 1, 1)
	end
	local text = n.tx or ""
	if n.seg then
		local parts = {}
		for _, s in n.seg do
			local piece = text:sub(s[1] + 1, s[2]):gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
			local f = type(s[3]) == "table" and s[3][1]
			if f and f.k == "S" then
				table.insert(parts, ('<font color="%s">%s</font>'):format(f.c, piece))
			else
				table.insert(parts, piece)
			end
		end
		text = table.concat(parts)
	end
	t.Text = text
	place(t, n)
	-- a little slack so live numbers never clip
	if t.TextXAlignment == Enum.TextXAlignment.Center then
		t.Position -= UDim2.fromOffset(n.w * 0.15, 0)
		t.Size += UDim2.fromOffset(n.w * 0.3, 0)
	elseif t.TextXAlignment == Enum.TextXAlignment.Left then
		t.Size += UDim2.fromOffset(n.w * 0.3, 0)
	end
	addStroke(t, n, true)
	if n.op then
		t.TextTransparency = 1 - n.op
	end
	return t
end

local function hasRotatedChild(n)
	for _, c in n.c or {} do
		if c.rot and c.rot ~= 0 then
			return true
		end
	end
	return false
end

local function isButtonName(name)
	for _, pat in M.ButtonNames do
		if name:find(pat) then
			return true
		end
	end
	return false
end

function M.build(n, z)
	z = z or 1
	if n.t == "Text" then
		return makeText(n, z)
	end
	local iconName = n.mc and n.mc:match("^Icons/(.+)$")
	local base = n.mc and (n.mc:match("^([^|]+)|") or n.mc)
	local isButton = (base and M.ButtonComponents[base]) or (not iconName and isButtonName(n.n))
	local obj
	if iconName then
		obj = Instance.new("ImageLabel")
		obj.Image = imageFor(iconName)
		obj:SetAttribute("Img", iconName)
		obj.ScaleType = Enum.ScaleType.Fit
		obj.BackgroundTransparency = 1
	elseif isButton then
		obj = Instance.new("ImageButton")
		obj.AutoButtonColor = false
		obj.ImageTransparency = 1
	elseif n.clip and hasRotatedChild(n) then
		obj = Instance.new("CanvasGroup")
	else
		obj = Instance.new("Frame")
	end
	obj.Name = n.n
	obj.BorderSizePixel = 0
	obj.ZIndex = z
	place(obj, n)
	addCorner(obj, n)
	if not iconName then
		applyFills(obj, n, 0)
	end
	if obj:IsA("CanvasGroup") and obj:FindFirstChildOfClass("UIGradient") then
		local fill = Instance.new("Frame")
		fill.Name = "Fill"
		fill.Size = UDim2.fromScale(1, 1)
		fill.BorderSizePixel = 0
		fill.BackgroundColor3 = obj.BackgroundColor3
		fill.BackgroundTransparency = obj.BackgroundTransparency
		fill.ZIndex = 0
		local c = obj:FindFirstChildOfClass("UICorner")
		if c then
			c:Clone().Parent = fill
		end
		obj:FindFirstChildOfClass("UIGradient").Parent = fill
		fill.Parent = obj
		obj.BackgroundTransparency = 1
	end
	addStroke(obj, n, false)
	if n.op then
		if obj:IsA("CanvasGroup") then
			obj.GroupTransparency = 1 - n.op
		elseif obj:IsA("ImageLabel") then
			obj.ImageTransparency = 1 - n.op * (1 - obj.ImageTransparency)
		else
			obj.BackgroundTransparency = 1 - n.op * (1 - obj.BackgroundTransparency)
			for _, ch in obj:GetChildren() do
				if ch:IsA("ImageLabel") then
					ch.ImageTransparency = 1 - n.op * (1 - ch.ImageTransparency)
				end
			end
		end
	end
	if n.clip and not obj:IsA("CanvasGroup") then
		obj.ClipsDescendants = true
	end
	for i, c in n.c or {} do
		local child = M.build(c, i)
		if child then
			if child:IsA("GuiObject") then
				child.LayoutOrder = i
				child.ZIndex = i
			end
			child.Parent = obj
		end
	end
	return obj
end

return M
