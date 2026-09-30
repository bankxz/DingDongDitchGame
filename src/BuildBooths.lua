-- Builds the two lobby merchant booths (Trail Shop + Sell Pets) in Workspace.Map.spawn.MerchantBooths.
-- Stud-style stalls (Plastic + the place's "Studs" MaterialVariant, Neon trims), a striped awning, a sign, and a
-- merchant NPC behind the counter (cloned from the spawn folder's Astronaut / Fisherman rigs). A ProximityPrompt on
-- each counter carries OpenUI = the window GameUIClient opens. The NPC idle loop runs from MerchantIdle (server).
local B = {}

local STUDS = "Studs"

local function part(parent, name, size, cf, color, material, variant)
	local p = Instance.new("Part")
	p.Name = name
	p.Anchored = true
	p.Size = size
	p.CFrame = cf
	p.Color = color
	p.Material = material or Enum.Material.Plastic
	if variant ~= false and (material == nil or material == Enum.Material.Plastic) then
		p.MaterialVariant = STUDS
	end
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.CastShadow = true
	p.Parent = parent
	return p
end

local function wedge(parent, name, size, cf, color)
	local w = Instance.new("WedgePart")
	w.Name = name
	w.Anchored = true
	w.Size = size
	w.CFrame = cf
	w.Color = color
	w.Material = Enum.Material.Plastic
	w.MaterialVariant = STUDS
	w.Parent = parent
	return w
end

local FONT = Font.new("rbxasset://fonts/families/FredokaOne.json", Enum.FontWeight.Regular, Enum.FontStyle.Normal)

local function sign(board, title, sub, color, iconImage, iconName)
	local sg = Instance.new("SurfaceGui")
	sg.Name = "Sign"
	sg.Face = Enum.NormalId.Front
	sg.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	sg.PixelsPerStud = 40
	sg.LightInfluence = 0
	sg.Brightness = 1.2
	sg.Parent = board
	local icon = Instance.new("ImageLabel")
	icon.Name = "Icon"
	icon.BackgroundTransparency = 1
	icon.Size = UDim2.fromScale(0.26, 1.1)
	icon.Position = UDim2.fromScale(0.02, -0.05)
	icon.ScaleType = Enum.ScaleType.Fit
	icon.Image = iconImage or ""
	icon:SetAttribute("Img", iconName)
	icon.Parent = sg
	local t = Instance.new("TextLabel")
	t.Name = "Title"
	t.BackgroundTransparency = 1
	t.Size = UDim2.fromScale(0.72, 0.62)
	t.Position = UDim2.fromScale(0.27, 0.04)
	t.FontFace = FONT
	t.TextScaled = true
	t.Text = title
	t.TextColor3 = Color3.new(1, 1, 1)
	t.Parent = sg
	local s = Instance.new("UIStroke")
	s.Thickness = 5
	s.Color = Color3.fromRGB(14, 14, 16)
	s.Parent = t
	local g = Instance.new("UIGradient")
	g.Color = ColorSequence.new(Color3.new(1, 1, 1), color:Lerp(Color3.new(1, 1, 1), 0.55))
	g.Rotation = 90
	g.Parent = t
	local st = Instance.new("TextLabel")
	st.Name = "Sub"
	st.BackgroundTransparency = 1
	st.Size = UDim2.fromScale(0.72, 0.3)
	st.Position = UDim2.fromScale(0.27, 0.64)
	st.FontFace = FONT
	st.TextScaled = true
	st.Text = sub
	st.TextColor3 = color:Lerp(Color3.new(1, 1, 1), 0.7)
	st.Parent = sg
	local s2 = s:Clone()
	s2.Thickness = 3
	s2.Parent = st
end

local function nameTag(npc, title, color)
	local head = npc:FindFirstChild("Head")
	if not head then
		return
	end
	local bb = Instance.new("BillboardGui")
	bb.Name = "MerchantTag"
	bb.Size = UDim2.fromScale(7, 1.6) -- studs: shrinks with distance like the world
	bb.StudsOffsetWorldSpace = Vector3.new(0, 2.4, 0)
	bb.MaxDistance = 90
	bb.LightInfluence = 0
	bb.Parent = head
	local t = Instance.new("TextLabel")
	t.BackgroundTransparency = 1
	t.Size = UDim2.fromScale(1, 1)
	t.FontFace = FONT
	t.TextScaled = true
	t.Text = title
	t.TextColor3 = color:Lerp(Color3.new(1, 1, 1), 0.45)
	t.Parent = bb
	local s = Instance.new("UIStroke")
	s.Thickness = 3
	s.Color = Color3.fromRGB(14, 14, 16)
	s.Parent = t
end

-- one booth, built around origin (front = -Z local, i.e. LookVector), then pivoted to `at`
local function booth(root, def)
	local m = Instance.new("Model")
	m.Name = def.Name
	local O = CFrame.new()
	local W, D = 16, 11 -- width (X), depth (Z)
	local c1, c2, dark, trim = def.Color1, def.Color2, def.Dark, def.Trim
	-- platform + step
	part(m, "Platform", Vector3.new(W + 2, 1, D + 2), O * CFrame.new(0, 0.5, 0), dark)
	part(m, "Step", Vector3.new(W - 2, 0.5, 2), O * CFrame.new(0, 0.25, -(D / 2 + 2)), dark:Lerp(Color3.new(1, 1, 1), 0.15))
	-- back wall with stripes
	for i = 0, 7 do
		local col = (i % 2 == 0) and c1 or c2
		part(m, "BackWall", Vector3.new(W / 8, 9, 1), O * CFrame.new(-W / 2 + W / 16 + i * W / 8, 5.5, D / 2 - 0.5), col)
	end
	-- side walls (half height)
	part(m, "SideL", Vector3.new(1, 4, D - 1), O * CFrame.new(-W / 2 + 0.5, 3, 0), c2)
	part(m, "SideR", Vector3.new(1, 4, D - 1), O * CFrame.new(W / 2 - 0.5, 3, 0), c2)
	-- counter
	part(m, "Counter", Vector3.new(W - 1, 3.5, 2.6), O * CFrame.new(0, 2.75, -D / 2 + 2), c1)
	part(m, "CounterTop", Vector3.new(W, 0.6, 3.4), O * CFrame.new(0, 4.8, -D / 2 + 2), Color3.fromRGB(245, 245, 245))
	part(m, "CounterTrim", Vector3.new(W - 0.6, 0.35, 0.3), O * CFrame.new(0, 4.35, -D / 2 + 0.55), trim, Enum.Material.Neon, false)
	part(m, "CounterPanel", Vector3.new(W - 5, 2.2, 0.3), O * CFrame.new(0, 2.7, -D / 2 + 0.55), c2)
	-- posts
	for _, x in { -W / 2 + 0.6, W / 2 - 0.6 } do
		part(m, "Post", Vector3.new(1.2, 10, 1.2), O * CFrame.new(x, 6, -D / 2 + 0.9), Color3.fromRGB(245, 245, 245))
		part(m, "PostCap", Vector3.new(1.6, 0.6, 1.6), O * CFrame.new(x, 11.2, -D / 2 + 0.9), trim, Enum.Material.Neon, false)
	end
	-- striped awning (sloped down to the front) + scalloped edge
	local slats = 8
	local tilt = math.rad(18)
	for i = 0, slats - 1 do
		local x = -W / 2 + W / slats / 2 + i * W / slats
		local col = (i % 2 == 0) and c1 or Color3.fromRGB(250, 250, 250)
		part(m, "Awning", Vector3.new(W / slats, 0.6, D + 1.5), O * CFrame.new(x, 11.7, -0.4) * CFrame.Angles(-tilt, 0, 0), col)
		local front = O * CFrame.new(x, 11.7 - math.sin(tilt) * (D + 1.5) / 2, -0.4 - math.cos(tilt) * (D + 1.5) / 2)
		local sc = part(m, "Scallop", Vector3.new(W / slats - 0.1, 1.2, 0.5), front * CFrame.new(0, -0.5, 0), col)
		local c = Instance.new("Part")
		c.Shape = Enum.PartType.Cylinder
		c.Name = "ScallopRound"
		c.Anchored = true
		c.Size = Vector3.new(0.5, W / slats - 0.1, W / slats - 0.1)
		c.CFrame = front * CFrame.new(0, -1.1, 0) * CFrame.Angles(0, math.rad(90), 0)
		c.Color = col
		c.Material = Enum.Material.Plastic
		c.MaterialVariant = STUDS
		c.Parent = m
		local _ = sc
	end
	-- sign board above the awning
	local board = part(m, "SignBoard", Vector3.new(12, 3.4, 0.6), O * CFrame.new(0, 14.4, -D / 2 + 1.2) * CFrame.Angles(0, math.rad(180), 0), dark)
	part(m, "SignFrame", Vector3.new(12.8, 4.2, 0.4), O * CFrame.new(0, 14.4, -D / 2 + 1.6), trim, Enum.Material.Neon, false)
	board.CFrame = O * CFrame.new(0, 14.4, -D / 2 + 1.2) -- Front face = -Z (towards the players)
	sign(board, def.Title, def.Sub, def.Color1, def.IconImage, def.Icon)
	part(m, "SignLegL", Vector3.new(0.6, 2.4, 0.6), O * CFrame.new(-4.5, 12.2, -D / 2 + 1.6), dark)
	part(m, "SignLegR", Vector3.new(0.6, 2.4, 0.6), O * CFrame.new(4.5, 12.2, -D / 2 + 1.6), dark)
	-- props on the counter
	for i, p in def.Props or {} do
		local pp = part(m, "Prop" .. i, p.Size, O * CFrame.new(p.X, 5.1 + p.Size.Y / 2, -D / 2 + 2) * CFrame.Angles(0, p.Rot or 0, 0), p.Color, p.Material, p.Material == nil)
		pp.Shape = p.Shape or Enum.PartType.Block
	end
	-- glow light
	local light = Instance.new("PointLight")
	light.Color = trim
	light.Range = 18
	light.Brightness = 1.2
	light.Parent = m:FindFirstChild("CounterTop")
	-- prompt on the counter
	local att = Instance.new("Attachment")
	att.Name = "PromptAttachment"
	att.Position = Vector3.new(0, 1.5, -1)
	att.Parent = m:FindFirstChild("CounterTop")
	local pr = Instance.new("ProximityPrompt")
	pr.Name = "OpenPrompt"
	pr.ActionText = def.Action
	pr.ObjectText = def.Title
	pr.KeyboardKeyCode = Enum.KeyCode.E
	pr.HoldDuration = 0
	pr.MaxActivationDistance = 12
	pr.RequiresLineOfSight = false
	pr.Style = Enum.ProximityPromptStyle.Default
	pr:SetAttribute("OpenUI", def.OpenUI)
	pr.Parent = att
	-- merchant behind the counter
	local src = workspace.Map.spawn:FindFirstChild(def.NPC)
	if src then
		local npc = src:Clone()
		npc.Name = "Merchant"
		for _, d in npc:GetDescendants() do
			if d:IsA("BasePart") then
				d.Anchored = false
				d.CanCollide = false
				d.CanQuery = false
			elseif d:IsA("LuaSourceContainer") then
				d:Destroy()
			end
		end
		local hrp = npc:FindFirstChild("HumanoidRootPart")
		local hum = npc:FindFirstChildOfClass("Humanoid")
		if hum then
			hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
			hum.NameDisplayDistance = 0
			if not hum:FindFirstChildOfClass("Animator") then
				Instance.new("Animator").Parent = hum
			end
		end
		if hrp then
			hrp.Anchored = true
			local _, size = npc:GetBoundingBox()
			local hip = hum and hum.HipHeight or 2
			-- stand behind the counter, facing the front (-Z)
			npc:PivotTo(O * CFrame.new(0, 1 + hip + hrp.Size.Y / 2, -D / 2 + 4.6) * CFrame.Angles(0, math.rad(180), 0) * CFrame.Angles(0, math.rad(180), 0))
			local look = O * CFrame.new(0, 0, -D)
			local pos = hrp.Position
			hrp.CFrame = CFrame.lookAt(pos, Vector3.new(look.X, pos.Y, look.Z))
			npc:PivotTo(hrp.CFrame)
			local _ = size
		end
		npc:SetAttribute("MerchantIdle", true)
		nameTag(npc, def.NPCTitle, def.Color1)
		npc.Parent = m
	end
	m.PrimaryPart = m:FindFirstChild("Platform")
	m.Parent = root
	-- turn the whole booth to face `facing` from `at`
	local floorY = def.At.Y
	local base = CFrame.lookAt(def.At, def.At + def.Facing) -- LookVector = facing; our front is -Z = LookVector
	m:PivotTo(base * CFrame.new(0, 0, 0))
	-- the platform bottom sits on the floor
	local cf = m.Platform.CFrame
	m:PivotTo(m:GetPivot() + Vector3.new(0, floorY - (cf.Position.Y - m.Platform.Size.Y / 2), 0))
	return m
end

function B.build(images)
	images = images or {}
	local parent = workspace.Map.spawn
	local old = parent:FindFirstChild("MerchantBooths")
	if old then
		old:Destroy()
	end
	local root = Instance.new("Folder")
	root.Name = "MerchantBooths"
	root.Parent = parent
	local floorY = 506.8033447265625 + 0.5 -- top of the lobby ground
	local facing = Vector3.new(1, 0, 0) -- towards the safe zone / spawn
	booth(root, {
		Name = "TrailBooth", Title = "TRAILS", Sub = "Speed trails!", Action = "Open Trail Shop", OpenUI = "TrailShopWindow",
		NPC = "Astronaut", NPCTitle = "Trail Merchant", Icon = "TrailGold", IconImage = images.TrailGold,
		Color1 = Color3.fromRGB(170, 70, 255), Color2 = Color3.fromRGB(255, 95, 200), Dark = Color3.fromRGB(58, 30, 92), Trim = Color3.fromRGB(80, 220, 255),
		At = Vector3.new(-32, floorY, -289), Facing = facing,
		Props = {
			{ X = -5, Size = Vector3.new(1.4, 1.4, 1.4), Color = Color3.fromRGB(255, 200, 40), Material = Enum.Material.Neon, Shape = Enum.PartType.Ball },
			{ X = 5, Size = Vector3.new(1.4, 1.4, 1.4), Color = Color3.fromRGB(60, 220, 255), Material = Enum.Material.Neon, Shape = Enum.PartType.Ball },
		},
	})
	booth(root, {
		Name = "SellBooth", Title = "SELL PETS", Sub = "Cash for pets!", Action = "Sell Pets", OpenUI = "SellWindow",
		NPC = "Fisherman", NPCTitle = "Pet Buyer", Icon = "CashPile", IconImage = images.CashPile,
		Color1 = Color3.fromRGB(60, 205, 60), Color2 = Color3.fromRGB(255, 200, 40), Dark = Color3.fromRGB(28, 70, 30), Trim = Color3.fromRGB(255, 225, 77),
		At = Vector3.new(-32, floorY, -338), Facing = facing,
		Props = {
			{ X = -5, Size = Vector3.new(2, 0.8, 1.2), Color = Color3.fromRGB(90, 220, 90) },
			{ X = -5, Size = Vector3.new(2, 0.8, 1.2), Color = Color3.fromRGB(120, 240, 110), Rot = 0.4 },
			{ X = 5, Size = Vector3.new(1.6, 1.6, 1.6), Color = Color3.fromRGB(255, 205, 40), Material = Enum.Material.Neon, Shape = Enum.PartType.Cylinder },
		},
	})
	return "booths built"
end

return B
