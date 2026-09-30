-- Builds StarterGui.GameUI from the V2 Figma dump (ServerStorage.FigmaDump.V2.Part*). Run in Studio edit mode:
--   require(ServerStorage.FigmaDump.BuildGameUIV2).build(imageIds)
-- Every group is authored at 1920x1080 (the Figma frames). Each group is one Frame anchored to a screen edge / the
-- centre with a UIScale named "Scale"; GameUIClient recomputes positions + scales for the real screen size.
-- Attributes on each group: AX / AY (anchor 0 / 0.5 / 1), OX / OY (design-px offset of the anchor point from that
-- screen anchor), Kind ("hud" / "window" / "modal" / "overlay").
local HttpService = game:GetService("HttpService")
local ServerStorage = game:GetService("ServerStorage")
local StarterGui = game:GetService("StarterGui")

local B = {}
local DW, DH = 1920, 1080

local function decode()
	local folder = ServerStorage.FigmaDump.V2
	local parts = {}
	for _, m in folder:GetChildren() do
		if m:IsA("ModuleScript") and m.Name:match("^Part") then
			table.insert(parts, m)
		end
	end
	table.sort(parts, function(a, b)
		return a.Name < b.Name
	end)
	local s = {}
	for _, m in parts do
		table.insert(s, (m.Source:match("^return %[==%[(.*)%]==%]$")))
	end
	return HttpService:JSONDecode(table.concat(s))
end

local function screen(layout, prefix)
	for _, s in layout.screens do
		if s.n:sub(1, #prefix) == prefix then
			return s
		end
	end
	error("no screen " .. prefix)
end

local function findNode(n, name, pattern)
	for _, c in n.c or {} do
		if (pattern and c.n:find(name)) or c.n == name then
			return c
		end
	end
	for _, c in n.c or {} do
		local r = findNode(c, name, pattern)
		if r then
			return r
		end
	end
	return nil
end

local function copy(t)
	return HttpService:JSONDecode(HttpService:JSONEncode(t))
end

local function findGui(root, name)
	return root:FindFirstChild(name, true)
end

---------------------------------------------------------------- group helpers
local function makeGroup(gui, name, x, y, w, h, kind, ax, ay, z)
	local g = Instance.new("Frame")
	g.Name = name
	g.BackgroundTransparency = 1
	g.Size = UDim2.fromOffset(w, h)
	ax = ax or ((x + w / 2) < DW / 3 and 0 or ((x + w / 2) > DW * 2 / 3 and 1 or 0.5))
	ay = ay or ((y + h / 2) < DH / 2 and 0 or 1)
	g.AnchorPoint = Vector2.new(ax, ay)
	local ox = (x + ax * w) - ax * DW
	local oy = (y + ay * h) - ay * DH
	g.Position = UDim2.new(ax, ox, ay, oy)
	g:SetAttribute("AX", ax)
	g:SetAttribute("AY", ay)
	g:SetAttribute("OX", ox)
	g:SetAttribute("OY", oy)
	g:SetAttribute("Kind", kind)
	g.ZIndex = z or 1
	local s = Instance.new("UIScale")
	s.Name = "Scale"
	s.Parent = g
	g.Parent = gui
	return g
end

-- build node n inside parent at (n.x - ox, n.y - oy)
local function put(Import, parent, n, ox, oy, z)
	local c = copy(n)
	c.x -= ox or 0
	c.y -= oy or 0
	local obj = Import.build(c, z or 1)
	obj.Parent = parent
	return obj
end

-- replace a static container with a ScrollingFrame of the same geometry, keeping its look
local function toScroll(frame, dir)
	local s = Instance.new("ScrollingFrame")
	s.Name = frame.Name
	s.Position = frame.Position
	s.Size = frame.Size
	s.AnchorPoint = frame.AnchorPoint
	s.BackgroundColor3 = frame.BackgroundColor3
	s.BackgroundTransparency = frame.BackgroundTransparency
	s.BorderSizePixel = 0
	s.ZIndex = frame.ZIndex
	s.LayoutOrder = frame.LayoutOrder
	s.ScrollBarThickness = 8
	s.ScrollBarImageColor3 = Color3.fromRGB(140, 138, 150)
	s.ScrollingDirection = dir == "X" and Enum.ScrollingDirection.X or Enum.ScrollingDirection.Y
	s.AutomaticCanvasSize = dir == "X" and Enum.AutomaticSize.X or Enum.AutomaticSize.Y
	s.CanvasSize = UDim2.new()
	s.ElasticBehavior = Enum.ElasticBehavior.WhenScrollable
	s.ScrollingEnabled = true
	for _, c in frame:GetChildren() do
		if c:IsA("UICorner") or c:IsA("UIStroke") or c:IsA("UIGradient") then
			c.Parent = s
		end
	end
	s.Parent = frame.Parent
	frame:Destroy()
	return s
end

local function listLayout(parent, dir, pad, halign)
	local l = Instance.new("UIListLayout")
	l.FillDirection = dir == "X" and Enum.FillDirection.Horizontal or Enum.FillDirection.Vertical
	l.Padding = UDim.new(0, pad or 8)
	l.SortOrder = Enum.SortOrder.LayoutOrder
	if halign then
		l.HorizontalAlignment = halign
	end
	l.Parent = parent
	return l
end

local function padding(parent, t, l, b, r)
	local p = Instance.new("UIPadding")
	p.PaddingTop = UDim.new(0, t or 0)
	p.PaddingLeft = UDim.new(0, l or 0)
	p.PaddingBottom = UDim.new(0, b or 0)
	p.PaddingRight = UDim.new(0, r or 0)
	p.Parent = parent
	return p
end

local function template(folder, obj, name)
	obj.Name = name
	obj.Position = UDim2.new()
	obj.Visible = false
	obj.Parent = folder
	return obj
end

---------------------------------------------------------------- build
function B.build(images, native)
	local Import = require(ServerStorage.FigmaDump.FigmaImportV2:Clone())
	Import.Images = images or {}
	Import.Native = native or { img_11e5dc56dac6 = 128 }
	local L = decode()

	local old = StarterGui:FindFirstChild("GameUI")
	if old then
		local backups = ServerStorage:FindFirstChild("ScriptBackups")
		local prev = backups:FindFirstChild("GameUI_V1")
		if prev then
			prev:Destroy()
		end
		old.Name = "GameUI_V1"
		old.Enabled = false
		old.Parent = backups
	end
	local gui = Instance.new("ScreenGui")
	gui.Name = "GameUI"
	gui.ResetOnSpawn = false
	gui.IgnoreGuiInset = true
	gui.ScreenInsets = Enum.ScreenInsets.DeviceSafeInsets
	gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
	gui.DisplayOrder = 5
	gui.Enabled = true

	local T = Instance.new("Folder")
	T.Name = "Templates"
	T.Parent = gui

	---------------------------------------------------------------- HUD (V2 01)
	local S01 = screen(L, "V2 01")
	local hud = S01.c[1]
	local hudGroups = {}
	for _, n in hud.c do
		local ay
		if n.n == "LeftButtons" then
			ay = 1
		end
		local g = makeGroup(gui, n.n, n.x, n.y, n.w, n.h, "hud", nil, ay, 2)
		local obj = put(Import, g, n, n.x, n.y)
		obj.Name = "Body"
		hudGroups[n.n] = g
	end

	-- Active Pets panel: rows become a scrolling list built from templates
	do
		local g = hudGroups.ActivePets
		local list = g.Body.List
		local row = list:FindFirstChild("PetRow")
		template(T, row:Clone(), "PetRow")
		local S18 = screen(L, "V2 18")
		local panel18 = findNode(S18, "ActivePets", true)
		local empty = findNode(panel18, "EmptySlotRow")
		template(T, put(Import, T, empty, empty.x, empty.y), "EmptyPetRow")
		local sc = toScroll(list, "Y")
		listLayout(sc, "Y", 8)
		padding(sc, 12, 12, 12, 0)
	end
	-- Hatching panel: ready row / growing row / empty row templates
	do
		local g = hudGroups.EggTimers
		local list = g.Body.List
		local rows = {}
		for _, c in list:GetChildren() do
			if c.Name == "EggRow" then
				table.insert(rows, c)
			end
		end
		table.sort(rows, function(a, b)
			return a.Position.Y.Offset < b.Position.Y.Offset
		end)
		template(T, rows[1]:Clone(), "EggRowReady")
		template(T, rows[2]:Clone(), "EggRowGrowing")
		local S18 = screen(L, "V2 18")
		local panel18 = findNode(S18, "EggTimers", true)
		local empty = findNode(panel18, "EmptyEggRow")
		template(T, put(Import, T, empty, empty.x, empty.y), "EmptyEggRow")
		local sc = toScroll(list, "Y")
		listLayout(sc, "Y", 8)
		padding(sc, 12, 12, 12, 0)
	end
	-- Hotbar: one template slot, centred row
	do
		local g = hudGroups.Hotbar
		local body = g.Body
		local slot = body:FindFirstChild("Slot1")
		local t = template(T, slot:Clone(), "HotbarSlot")
		local icon = t:FindFirstChild("Icon/Bat")
		if icon then
			icon.Name = "Icon"
		end
		for _, c in body:GetChildren() do
			if c:IsA("GuiObject") then
				c:Destroy()
			end
		end
		body.Size = UDim2.fromOffset(1200, 124)
		body.Position = UDim2.fromOffset((264 - 1200) / 2, 0)
		listLayout(body, "X", 16, Enum.HorizontalAlignment.Center)
	end

	---------------------------------------------------------------- windows
	local function window(name, prefix, nodeName, sideName, kind, z)
		local S = screen(L, prefix)
		local n = findNode(S, nodeName)
		local x0, y0, x1, y1 = n.x, n.y, n.x + n.w, n.y + n.h
		local side = sideName and findNode(S, sideName, true)
		-- headers stick out of the window (-16,-12): include them
		x0 -= 16
		y0 -= 12
		x1 += 16
		if side then
			x0 = math.min(x0, side.x)
			y0 = math.min(y0, side.y)
			x1 = math.max(x1, side.x + side.w)
			y1 = math.max(y1, side.y + side.h)
		end
		local g = makeGroup(gui, name, x0, y0, x1 - x0, y1 - y0, kind or "window", 0.5, 0.5, z or 10)
		-- centre the window itself on screen (the side column hangs off it)
		local winCx = n.x + n.w / 2 - x0
		g:SetAttribute("OX", (x1 - x0) / 2 - winCx)
		g:SetAttribute("OY", 0)
		g.Position = UDim2.new(0.5, (x1 - x0) / 2 - winCx, 0.5, 0)
		local w = put(Import, g, n, x0, y0)
		w.Name = "Window"
		if side then
			local s = put(Import, g, side, x0, y0)
			s.Name = "Side"
		end
		g.Visible = false
		return g, w
	end

	local growWin = window("GrowingEggsWindow", "V2 02", "GrowingEggsWindow")
	do
		local row = growWin.Window.Body.Content.Row
		local slots = {}
		for _, c in row:GetChildren() do
			if c.Name == "EggSlot" then
				table.insert(slots, c)
			end
		end
		template(T, slots[1]:Clone(), "EggSlot")
		template(T, row:FindFirstChild("EggSlot/Empty"):Clone(), "EggSlotEmpty")
		local sc = toScroll(row, "X")
		listLayout(sc, "X", 18)
		sc.ScrollBarThickness = 6
	end

	local petsWin = window("PetInventoryWindow", "V2 03", "PetInventoryWindow")
	do
		local body = petsWin.Window.Body
		local side = body.Sidebar
		template(T, side:FindFirstChild("Tab/All"):Clone(), "InvTabSelected")
		template(T, side:FindFirstChild("Tab/Common"):Clone(), "InvTab")
		for _, c in side:GetChildren() do
			if c:IsA("GuiObject") and c.Name:match("^Tab/") then
				c:Destroy()
			end
		end
		local ss = toScroll(side, "Y")
		listLayout(ss, "Y", 10)
		padding(ss, 12, 12, 12, 0)
		local grid = body.Content.Grid
		template(T, grid:FindFirstChild("PetCard/Dog"):Clone(), "InvCard")
		local gs = toScroll(grid, "Y")
		local gl = Instance.new("UIGridLayout")
		gl.CellSize = UDim2.fromOffset(232, 222)
		gl.CellPadding = UDim2.fromOffset(16, 16)
		gl.SortOrder = Enum.SortOrder.LayoutOrder
		gl.Parent = gs
		padding(gs, 0, 0, 8, 0)
	end

	local indexWin = window("IndexWindow", "V2 04", "IndexWindow")
	do
		local body = indexWin.Window.Body
		local side = body.Sidebar
		template(T, side:FindFirstChild("Tab/Forest"):Clone(), "IndexTabSelected")
		template(T, side:FindFirstChild("Tab/Desert"):Clone(), "IndexTab")
		for _, c in side:GetChildren() do
			if c:IsA("GuiObject") and c.Name:match("^Tab/") then
				c:Destroy()
			end
		end
		local ss = toScroll(side, "Y")
		listLayout(ss, "Y", 10)
		padding(ss, 12, 12, 12, 0)
		local grid = body.Content.Grid
		template(T, grid:FindFirstChild("PetCard/Dog"):Clone(), "IndexCard")
		template(T, grid:FindFirstChild("PetCard/???"):Clone(), "IndexCardUnknown")
		local gs = toScroll(grid, "Y")
		local gl = Instance.new("UIGridLayout")
		gl.CellSize = UDim2.fromOffset(232, 240)
		gl.CellPadding = UDim2.fromOffset(16, 16)
		gl.SortOrder = Enum.SortOrder.LayoutOrder
		gl.Parent = gs
		padding(gs, 0, 0, 8, 0)
	end

	local claimModal = window("ClaimModal", "V2 05", "ClaimModal", nil, "modal", 14)

	-- Shop: one scrolling list assembled from the four shop screens
	local shopWin = window("ShopWindow", "V2 06", "ShopWindow", "QuickJump", "window", 10)
	do
		local body = shopWin.Window.Body
		local old = body.Content
		local sc = Instance.new("ScrollingFrame")
		sc.Name = "Scroll"
		sc.Position = old.Position
		sc.Size = old.Size
		sc.BackgroundTransparency = 1
		sc.BorderSizePixel = 0
		sc.ScrollBarThickness = 10
		sc.ScrollBarImageColor3 = Color3.fromRGB(140, 138, 150)
		sc.AutomaticCanvasSize = Enum.AutomaticSize.Y
		sc.CanvasSize = UDim2.new()
		sc.ScrollingDirection = Enum.ScrollingDirection.Y
		sc.ZIndex = old.ZIndex
		sc.Parent = body
		old:Destroy()
		local bar = shopWin.Window:FindFirstChild("ScrollBar")
		if bar then
			bar:Destroy()
		end
		listLayout(sc, "Y", 14, Enum.HorizontalAlignment.Center)
		padding(sc, 8, 0, 24, 0)
		local order = 0
		local function add(prefix, name, section)
			local S = screen(L, prefix)
			local n = findNode(S, name)
			local obj = put(Import, sc, n, n.x, n.y)
			order += 1
			obj.LayoutOrder = order
			if section then
				obj:SetAttribute("Section", section)
			end
			return obj
		end
		add("V2 06", "Section/FEATURED", "Featured")
		local feat = add("V2 06", "FeaturedBanner")
		local packs = { ["Buy/50Eggs"] = "Eggs50", ["Buy/10Eggs"] = "Eggs10", ["Buy/3Eggs"] = "Eggs3", ["Buy/1Egg"] = "Eggs1" }
		for name, key in packs do
			local b = findGui(feat, name)
			if b then
				b:SetAttribute("Product", key)
				local price = findGui(b, "PriceButton")
				if price then
					price:SetAttribute("Product", key)
				end
				local gift = findGui(b, "GiftButton")
				if gift then
					gift:SetAttribute("Product", key)
					gift:SetAttribute("Gift", true)
				end
			end
		end
		add("V2 09", "Section/PASSES", "Passes")
		local passRow = add("V2 09", "Row")
		for _, c in passRow:GetChildren() do
			local key = c.Name == "PassCard/x2 Growth" and "Growth" or (c.Name == "PassCard/x2 Money" and "Money")
			if key then
				c.Name = "Pass_" .. key
				c:SetAttribute("Pass", key)
			end
		end
		add("V2 07", "Section/SPEED", "Speed")
		-- speed / money card grids come from templates (Config.ShopSpeedRows / ShopMoneyRows fill them)
		local S07 = screen(L, "V2 07")
		local speedCard = findNode(S07, "SpeedCard")
		template(T, put(Import, T, speedCard, speedCard.x, speedCard.y), "SpeedCard")
		local S06 = screen(L, "V2 06")
		local moneyCard = findNode(S06, "MoneyCard")
		template(T, put(Import, T, moneyCard, moneyCard.x, moneyCard.y), "MoneyCard")
		local function grid(name, cell)
			local f = Instance.new("Frame")
			f.Name = name
			f.BackgroundTransparency = 1
			f.Size = UDim2.fromOffset(1008, 0)
			f.AutomaticSize = Enum.AutomaticSize.Y
			order += 1
			f.LayoutOrder = order
			local gl = Instance.new("UIGridLayout")
			gl.CellSize = cell
			gl.CellPadding = UDim2.fromOffset(16, 14)
			gl.SortOrder = Enum.SortOrder.LayoutOrder
			gl.HorizontalAlignment = Enum.HorizontalAlignment.Center
			gl.Parent = f
			f.Parent = sc
			return f
		end
		grid("SpeedGrid", UDim2.fromOffset(325, 260))
		local up = add("V2 07", "UpgradeBanner")
		up:SetAttribute("Product", "Treadmill")
		add("V2 06", "Section/MONEY", "Money")
		grid("MoneyGrid", UDim2.fromOffset(325, 250))
		-- quick jump buttons
		for _, c in shopWin.Side:GetChildren() do
			local key = c.Name:match("^Jump/(.+)$")
			if key then
				c:SetAttribute("Section", key)
			end
		end
	end

	local settingsWin = window("SettingsWindow", "V2 11", "SettingsWindow")
	local sellWin = window("SellWindow", "V2 12", "SellWindow", "SellTabs")
	do
		local grid = findGui(sellWin, "PetGrid (ScrollingFrame)")
		template(T, grid:FindFirstChild("SellCard/Dino"):Clone(), "SellCard")
		grid.Name = "PetGrid"
		local gs = toScroll(grid, "Y")
		local gl = Instance.new("UIGridLayout")
		gl.CellSize = UDim2.fromOffset(180, 236)
		gl.CellPadding = UDim2.fromOffset(14, 14)
		gl.SortOrder = Enum.SortOrder.LayoutOrder
		gl.Parent = gs
		padding(gs, 12, 2, 12, 0)
		local clear = findGui(sellWin, "ClearButton (swaps to Select All when nothing selected)")
		if clear then
			clear.Name = "ClearButton"
		end
	end
	local confirmModal = window("ConfirmModal", "V2 13", "ConfirmModal", nil, "modal", 14)
	local trailWin = window("TrailShopWindow", "V2 14", "TrailShopWindow")
	do
		local list = findGui(trailWin, "TrailList (ScrollingFrame, horizontal)")
		list.Name = "TrailList"
		local bar = findGui(trailWin, "HorizontalScrollBar")
		if bar then
			bar:Destroy()
		end
		local sc = Instance.new("ScrollingFrame")
		sc.Name = "TrailList"
		sc.Position = list.Position
		sc.Size = list.Size + UDim2.fromOffset(0, 26)
		sc.BackgroundTransparency = 1
		sc.BorderSizePixel = 0
		sc.ScrollBarThickness = 10
		sc.ScrollBarImageColor3 = Color3.fromRGB(140, 138, 150)
		sc.ScrollingDirection = Enum.ScrollingDirection.X
		sc.AutomaticCanvasSize = Enum.AutomaticSize.X
		sc.CanvasSize = UDim2.new()
		sc.ZIndex = list.ZIndex
		sc.Parent = list.Parent
		for _, c in list:GetChildren() do
			c.Parent = sc
		end
		list:Destroy()
		listLayout(sc, "X", 16)
		for _, c in sc:GetChildren() do
			local id = c.Name:match("^TrailCard/(.+)$")
			if id then
				c:SetAttribute("Trail", id)
				c.LayoutOrder = math.floor(c.Position.X.Offset)
			end
		end
		-- state pieces for locked / not-enough-cash
		local S18 = screen(L, "V2 18")
		local locked = findNode(S18, "TrailCard/Locked")
		local ov = Instance.new("Frame")
		ov.Name = "LockedOverlay"
		ov.BackgroundTransparency = 1
		ov.Size = UDim2.fromOffset(226, 552)
		for _, name in { "LockedOverlay", "Icon/Lock", "LOCKED", "Reach Zone 5 to unlock" } do
			for _, c in locked.c do
				if c.n == name then
					local o = put(Import, ov, c, 0, 0, 50)
					o.ZIndex = 50
				end
			end
		end
		template(T, ov, "LockedOverlay")
		local tip = findNode(S18, "Tooltip", true)
		local t = put(Import, T, tip, tip.x, tip.y)
		template(T, t, "Tooltip")
	end
	local giftWin = window("FreeGiftWindow", "V2 15", "FreeGiftWindow")

	---------------------------------------------------------------- hatch reveal (V2 16), full-screen overlay
	do
		local S16 = screen(L, "V2 16")
		local dim = Instance.new("Frame")
		dim.Name = "HatchDim"
		dim.BackgroundColor3 = Color3.new(0, 0, 0)
		dim.BackgroundTransparency = 0.35
		dim.Size = UDim2.fromScale(1, 1)
		dim.ZIndex = 19
		dim.Visible = false
		dim.Parent = gui
		local g = makeGroup(gui, "HatchReveal", 0, 0, DW, DH, "overlay", 0.5, 0.5, 20)
		g.Position = UDim2.fromScale(0.5, 0.5)
		g:SetAttribute("OX", 0)
		g:SetAttribute("OY", 0)
		for i, n in S16.c do
			local o = put(Import, g, n, 0, 0, i)
			o.LayoutOrder = i
			o.ZIndex = i
			if n.n:find("^RarityGlow") then
				o.Name = "RarityGlow"
			elseif n.n:find("^Rays") then
				o.Name = "Rays"
			elseif n.n == "Icon/PetDragon" then
				o.Name = "PetArt"
			elseif n.n == "DRAGON" then
				o.Name = "PetName"
			elseif n.n == "NEW!" then
				o.Name = "NewText"
			end
		end
		g.Visible = false
	end

	---------------------------------------------------------------- toasts (V2 17)
	do
		local S17 = screen(L, "V2 17")
		local stack = findNode(S17, "ToastStack", true)
		local g = makeGroup(gui, "Toasts", stack.x, stack.y, stack.w, stack.h, "overlay", 0.5, 0, 30)
		local list = Instance.new("Frame")
		list.Name = "List"
		list.BackgroundTransparency = 1
		list.Size = UDim2.fromScale(1, 1)
		list.Parent = g
		listLayout(list, "Y", 12, Enum.HorizontalAlignment.Center)
		for _, c in stack.c do
			local o = put(Import, T, c, c.x, c.y)
			template(T, o, c.n:gsub("/", "_"))
		end
		local fg = findNode(S17, "FloatingGain", true)
		template(T, put(Import, T, fg, fg.x, fg.y), "FloatingGain")
	end

	---------------------------------------------------------------- dim behind windows
	local dim = Instance.new("Frame")
	dim.Name = "Dim"
	dim.BackgroundColor3 = Color3.new(0, 0, 0)
	dim.BackgroundTransparency = 1
	dim.Size = UDim2.fromScale(1, 1)
	dim.ZIndex = 8
	dim.Visible = false
	dim.Parent = gui

	gui.Parent = StarterGui
	-- count
	local n = 0
	for _ in gui:GetDescendants() do
		n += 1
	end
	return ("built GameUI: %d instances"):format(n)
end

-- set every image from its Figma name (Img attribute) once the assets are uploaded
function B.applyImages(images, root)
	root = root or StarterGui:FindFirstChild("GameUI")
	local missing, set = {}, 0
	for _, d in root:GetDescendants() do
		local name = d:GetAttribute("Img")
		if name and (d:IsA("ImageLabel") or d:IsA("ImageButton")) then
			local id = images[name]
			if id then
				d.Image = id
				set += 1
			else
				missing[name] = true
			end
		end
	end
	local m = {}
	for k in missing do
		table.insert(m, k)
	end
	return set, m
end

return B
