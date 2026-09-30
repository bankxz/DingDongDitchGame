-- Client for the V2 game UI (StarterGui.GameUI, imported from the Figma "UI System" V2 screens by
-- ServerStorage.FigmaDump.BuildGameUIV2). Presentation only: every number comes from the server (leaderstats,
-- ReplicatedStorage.GameUI.Remote "State" snapshots) and every button just asks the server.
-- Layout: each group in GameUI is authored at 1920x1080 and anchored to a screen edge / the centre (attributes AX AY
-- OX OY); rescale() gives every group a UIScale + position for the real screen, so phones, tablets, laptops and
-- ultrawides all get the same composition. Settings / images / sounds: ReplicatedStorage.GameUI.Config.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")
local RunService = game:GetService("RunService")
local StarterGui = game:GetService("StarterGui")
local SoundService = game:GetService("SoundService")
local CollectionService = game:GetService("CollectionService")
local ProximityPromptService = game:GetService("ProximityPromptService")
local Lighting = game:GetService("Lighting")
local MarketplaceService = game:GetService("MarketplaceService")

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")
local Shared = ReplicatedStorage:WaitForChild("GameUI")
local C = require(Shared:WaitForChild("Config"))
local Remote = Shared:WaitForChild("Remote")
local Previews = Shared:WaitForChild("Previews")
local DD = require(ReplicatedStorage:WaitForChild("DingDong"):WaitForChild("Config"))
local SeedShared = ReplicatedStorage:WaitForChild("ForestSeedSystem")
local SeedConfig = require(SeedShared:WaitForChild("Config"))
local SeedRemotes = SeedShared:WaitForChild("Remotes")

local gui = playerGui:WaitForChild("GameUI")
local T = gui:WaitForChild("Templates")
player:SetAttribute("V2Toasts", true) -- ForestSeedClient leaves its old toast to us

local DW, DH = 1920, 1080
local state = nil -- last server snapshot

---------------------------------------------------------------- helpers
local function img(name)
	local id = (C.ImagesV2 and C.ImagesV2[name]) or (C.Images and C.Images[name])
	return id and id ~= "" and id or ""
end

local function tween(obj, t, props, style, dir)
	local tw = TweenService:Create(obj, TweenInfo.new(t, style or Enum.EasingStyle.Quad, dir or Enum.EasingDirection.Out), props)
	tw:Play()
	return tw
end

local function short(n)
	return C.short(n)
end
local function money(n)
	return "$" .. short(n)
end
local function commas(n)
	local s = tostring(math.floor(n))
	local k
	repeat
		s, k = s:gsub("^(-?%d+)(%d%d%d)", "%1,%2")
	until k == 0
	return s
end
local function clock(seconds)
	seconds = math.max(0, math.ceil(seconds))
	local h, m, s = seconds // 3600, seconds % 3600 // 60, seconds % 60
	if h > 0 then
		return ("%dh %02dm"):format(h, m)
	elseif m > 0 then
		return ("%dm %02ds"):format(m, s)
	end
	return ("%ds"):format(s)
end

-- children in design order
local function kids(frame, class)
	local list = {}
	for _, c in frame:GetChildren() do
		if c:IsA(class or "GuiObject") then
			table.insert(list, c)
		end
	end
	table.sort(list, function(a, b)
		return a.LayoutOrder < b.LayoutOrder
	end)
	return list
end
local function texts(frame)
	return kids(frame, "TextLabel")
end
local function text(frame, i)
	return texts(frame)[i or 1]
end
local function find(root, path)
	local node = root
	for name in path:gmatch("[^%.]+") do
		node = node and node:FindFirstChild(name)
	end
	return node
end
local function iconIn(frame)
	for _, c in frame:GetDescendants() do
		if c:IsA("ImageLabel") and c.Name:match("^Icon") then
			return c
		end
	end
	return nil
end
local function setText(label, s)
	if label then
		label.Text = s
	end
end

---------------------------------------------------------------- sounds (Config.Sounds cues, layered)
local uiGroup = SoundService:FindFirstChild("UISounds") or Instance.new("SoundGroup")
uiGroup.Name = "UISounds"
uiGroup.Parent = SoundService
local sfxGroup = SoundService:FindFirstChild("GameSFX") or Instance.new("SoundGroup")
sfxGroup.Name = "GameSFX"
sfxGroup.Parent = SoundService
local templates = {}
for _, id in C.SoundIds or {} do
	local s = Instance.new("Sound")
	s.SoundId = id
	s.SoundGroup = uiGroup
	s.Parent = uiGroup
	templates[id] = s
end
task.spawn(function()
	local list = {}
	for _, s in templates do
		table.insert(list, s)
	end
	pcall(game:GetService("ContentProvider").PreloadAsync, game:GetService("ContentProvider"), list)
end)
local S = C.SoundIds or {}
local extraCues = {
	Hatch = { { Id = S.Cork, Volume = 0.6, Pitch = 0.9 }, { Id = S.Stars, Volume = 0.5, Pitch = 1, Delay = 0.1 }, { Id = S.Chime, Volume = 0.45, Pitch = 1.15, Delay = 0.25 } },
	Toast = { { Id = S.Bubble, Volume = 0.35, Pitch = 1.1, Var = 0.05 } },
	Sell = { { Id = S.ChaChing, Volume = 0.55, Pitch = 1.05 }, { Id = S.Tick, Volume = 0.25, Pitch = 1.4, Delay = 0.08 } },
	Equip = { { Id = S.PopClick, Volume = 0.55, Pitch = 1.2 }, { Id = S.Chime, Volume = 0.3, Pitch = 1.3, Delay = 0.05 } },
}
local rng = Random.new()
local lastPlayed = {}
local function playLayer(layer, pitchMul)
	if not layer.Id then
		return
	end
	local base = templates[layer.Id]
	if not base then
		base = Instance.new("Sound")
		base.SoundId = layer.Id
		base.SoundGroup = uiGroup
		base.Parent = uiGroup
		templates[layer.Id] = base
	end
	local s = base:Clone()
	local var = layer.Var or 0
	s.PlaybackSpeed = (layer.Pitch or 1) * (pitchMul or 1) * (1 + rng:NextNumber(-var, var))
	s.Volume = layer.Volume or 0.5
	s.Parent = uiGroup
	s:Play()
	if layer.Length then
		task.delay(layer.Length, function()
			if s.Parent then
				tween(s, 0.06, { Volume = 0 })
			end
		end)
	end
	task.delay(math.min(layer.Length and layer.Length + 0.1 or 4, 4), function()
		s:Destroy()
	end)
end
local function play(name, pitchMul)
	local def = C.Sounds[name] or extraCues[name]
	if not def then
		return
	end
	local now = os.clock()
	if lastPlayed[name] and now - lastPlayed[name] < 0.03 then
		return
	end
	lastPlayed[name] = now
	for _, layer in def do
		if layer.Delay then
			task.delay(layer.Delay, playLayer, layer, pitchMul)
		else
			playLayer(layer, pitchMul)
		end
	end
end

---------------------------------------------------------------- button feel
local function scaleOf(obj, name)
	name = name or "PressScale"
	local s = obj:FindFirstChild(name)
	if not s then
		s = Instance.new("UIScale")
		s.Name = name
		s.Parent = obj
	end
	return s
end

local function pop(obj, amount)
	if not obj then
		return
	end
	local s = scaleOf(obj, "PopScale")
	s.Scale = amount or 1.2
	tween(s, 0.35, { Scale = 1 }, Enum.EasingStyle.Back)
end

local function shake(obj)
	if not obj then
		return
	end
	local p = obj.Position
	task.spawn(function()
		for i = 1, 6 do
			obj.Position = p + UDim2.fromOffset((i % 2 == 0 and 1 or -1) * (8 - i), 0)
			task.wait(0.035)
		end
		obj.Position = p
	end)
end

local function hookButton(button, onClick, sound)
	if not (button and button:IsA("GuiButton")) then
		return
	end
	local s = scaleOf(button)
	local hovering = false
	button.MouseEnter:Connect(function()
		hovering = true
		if UserInputService.MouseEnabled then
			tween(s, 0.12, { Scale = 1.06 })
			play("Hover")
		end
	end)
	button.MouseLeave:Connect(function()
		hovering = false
		tween(s, 0.12, { Scale = 1 })
	end)
	button.MouseButton1Down:Connect(function()
		tween(s, 0.07, { Scale = 0.92 })
		if sound ~= false then
			play("Press")
		end
	end)
	button.MouseButton1Up:Connect(function()
		tween(s, 0.18, { Scale = hovering and 1.06 or 1 }, Enum.EasingStyle.Back)
	end)
	button.Activated:Connect(function()
		if sound ~= false then
			play(sound or "Click")
		end
		if onClick then
			onClick(button)
		end
	end)
end

---------------------------------------------------------------- 3D previews (animals / eggs / tools) in the icon slots
local function fitCamera(vp, model, yaw)
	local cam = vp:FindFirstChildOfClass("Camera") or Instance.new("Camera")
	cam.FieldOfView = 30
	cam.Parent = vp
	vp.CurrentCamera = cam
	local cf, size = model:GetBoundingBox()
	local radius = size.Magnitude / 2
	local dist = radius / math.tan(math.rad(cam.FieldOfView / 2)) * 1.0
	local dir = (CFrame.Angles(0, math.rad(yaw or 35), 0) * CFrame.Angles(math.rad(-12), 0, 0)).LookVector
	cam.CFrame = CFrame.lookAt(cf.Position - dir * dist, cf.Position)
end

local function setPreview(vp, source, yaw)
	for _, c in vp:GetChildren() do
		if not c:IsA("UICorner") then
			c:Destroy()
		end
	end
	if not source then
		return
	end
	local model
	if source:IsA("Model") then
		model = source:Clone()
	else
		model = Instance.new("Model")
		source:Clone().Parent = model
	end
	for _, d in model:GetDescendants() do
		if d:IsA("LuaSourceContainer") or d:IsA("Sound") or d:IsA("ParticleEmitter") or d:IsA("BillboardGui") then
			d:Destroy()
		end
	end
	model.Parent = vp
	fitCamera(vp, model, yaw)
	vp.Ambient = Color3.fromRGB(200, 200, 200)
	vp.LightColor = Color3.fromRGB(255, 255, 255)
	vp.LightDirection = Vector3.new(-1, -2, -1)
end

local function animalPreview(zone, animalId)
	local f = Previews:FindFirstChild("Animals")
	return f and f:FindFirstChild(zone .. "_" .. animalId)
end
local function eggPreview(zone, eggId)
	local f = Previews:FindFirstChild("Eggs")
	return f and f:FindFirstChild(zone .. "_" .. eggId)
end

-- a ViewportFrame exactly over an icon ImageLabel (the icon is hidden); returns the viewport
local function viewportOver(icon)
	if not icon then
		return nil
	end
	local vp = icon.Parent:FindFirstChild(icon.Name .. "_VP")
	if not vp then
		vp = Instance.new("ViewportFrame")
		vp.Name = icon.Name .. "_VP"
		vp.BackgroundTransparency = 1
		vp.AnchorPoint = icon.AnchorPoint
		vp.Position = icon.Position
		vp.Size = icon.Size
		vp.ZIndex = icon.ZIndex
		vp.LayoutOrder = icon.LayoutOrder
		vp.Parent = icon.Parent
	end
	icon.Visible = false
	return vp
end

local function waitFor(getter, tries)
	for _ = 1, tries or 40 do
		local v = getter()
		if v then
			return v
		end
		task.wait(0.25)
	end
	return nil
end

local function showAnimal(icon, zone, animalId, yaw)
	local vp = viewportOver(icon)
	if not vp then
		return
	end
	local key = zone .. "_" .. animalId
	if vp:GetAttribute("Showing") == key then
		return
	end
	vp:SetAttribute("Showing", key)
	task.spawn(function()
		local src = waitFor(function()
			return animalPreview(zone, animalId)
		end)
		if vp:GetAttribute("Showing") == key then
			setPreview(vp, src, yaw or 30)
		end
	end)
end
local function showEgg(icon, zone, eggId)
	local vp = viewportOver(icon)
	if not vp then
		return
	end
	local key = zone .. "_" .. eggId
	if vp:GetAttribute("Showing") == key then
		return
	end
	vp:SetAttribute("Showing", key)
	task.spawn(function()
		local src = waitFor(function()
			return eggPreview(zone, eggId)
		end)
		if vp:GetAttribute("Showing") == key then
			setPreview(vp, src, 15)
		end
	end)
end

local function rarityColor(r)
	local c = C.Rarity[r]
	return c and c.Color or Color3.new(1, 1, 1)
end

---------------------------------------------------------------- responsive scaling
local groups = {}
for _, g in gui:GetChildren() do
	if g:IsA("Frame") and g:GetAttribute("Kind") then
		groups[g.Name] = g
	end
end
local function G(name)
	return groups[name]
end

local hudScale = 1
local function touchOnly()
	return UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled
end
-- the on-screen thumbstick / jump button are showing (touch device, or a touchscreen laptop being used by touch)
local function touchControls()
	local tg = player.PlayerGui:FindFirstChild("TouchGui")
	local frame = tg and tg:FindFirstChild("TouchControlFrame")
	if tg and tg:IsA("ScreenGui") then
		return tg.Enabled and (frame == nil or frame.Visible)
	end
	return touchOnly()
end
local function rescale()
	local size = gui.AbsoluteSize
	if size.X < 10 then
		return
	end
	local base = math.min(size.X / DW, size.Y / DH)
	-- phones: a bit bigger than a straight scale so buttons stay thumb-sized
	local hud = base * (touchOnly() and 1.2 or 1)
	hud = math.clamp(hud, 0.3, 1.35)
	-- keep the top-left and top-right panels from crossing on narrow screens
	local maxByWidth = size.X / (400 + 48 + 400 + 150 + 84 + 48 + 40)
	hud = math.min(hud, math.max(maxByWidth, 0.3))
	hudScale = hud
	for _, g in groups do
		local kind = g:GetAttribute("Kind")
		local s = hud
		if kind == "window" or kind == "modal" then
			local w, h = g.Size.X.Offset, g.Size.Y.Offset
			s = math.min((size.X - 24) / w, (size.Y - 24) / h, base * (touchOnly() and 1.15 or 1.05))
			s = math.max(s, 0.2)
		elseif kind == "overlay" then
			s = g.Name == "HatchReveal" and math.min(size.X / DW, size.Y / DH) * (touchOnly() and 1.15 or 1) or hud
		end
		local sc = g:FindFirstChild("Scale")
		if sc then
			sc.Scale = s
		end
		local home = UDim2.new(g:GetAttribute("AX"), g:GetAttribute("OX") * s, g:GetAttribute("AY"), g:GetAttribute("OY") * s)
		-- touch: lift the bottom-corner HUD clear of the thumbstick (left) and jump button (right)
		if touchControls() and kind ~= "window" and kind ~= "modal" and kind ~= "overlay" and g:GetAttribute("AY") == 1 then
			local small = math.min(size.X, size.Y) <= 500
			local ax = g:GetAttribute("AX")
			local lift = 0
			if ax == 0 then
				lift = small and size.Y * 0.26 or 190
			elseif ax == 1 then
				lift = small and 95 or 150
			end
			home += UDim2.fromOffset(0, -lift)
		end
		g:SetAttribute("HomeX", home.X.Offset)
		g:SetAttribute("HomeY", home.Y.Offset)
		if not g:GetAttribute("Sliding") then
			g.Position = home
		end
	end
end
gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(rescale)
local lastTouch = touchControls()
local function recheckTouch()
	local t = touchControls()
	if t ~= lastTouch then
		lastTouch = t
		rescale()
	end
end
UserInputService.LastInputTypeChanged:Connect(recheckTouch)
player.PlayerGui.ChildAdded:Connect(function(c)
	if c.Name == "TouchGui" then
		task.wait(0.5)
		recheckTouch()
		local frame = c:FindFirstChild("TouchControlFrame")
		if frame then
			frame:GetPropertyChangedSignal("Visible"):Connect(recheckTouch)
		end
		c:GetPropertyChangedSignal("Enabled"):Connect(recheckTouch)
	end
end)
task.delay(2, recheckTouch)
task.defer(rescale)
local function homeOf(g)
	return UDim2.new(g:GetAttribute("AX"), g:GetAttribute("HomeX") or 0, g:GetAttribute("AY"), g:GetAttribute("HomeY") or 0)
end

---------------------------------------------------------------- CoreGui: our hotbar replaces the default backpack
task.spawn(function()
	for _ = 1, 20 do
		if pcall(StarterGui.SetCoreGuiEnabled, StarterGui, Enum.CoreGuiType.Backpack, false) then
			break
		end
		task.wait(0.5)
	end
end)

---------------------------------------------------------------- toasts (V2 17) + floating gains
local toastList = find(G("Toasts"), "List")
local toastCount = 0
local function toast(kind, message, iconName, zone, animalId)
	if not toastList then
		return
	end
	local tpl = T:FindFirstChild("Toast_" .. (kind or "Speed")) or T:FindFirstChild("Toast_Speed")
	local t = tpl:Clone()
	t.Visible = true
	toastCount += 1
	t.LayoutOrder = -toastCount -- newest on top
	local label = text(t)
	if label then
		label.Text = message
		label.TextXAlignment = Enum.TextXAlignment.Left
		label.Size = UDim2.fromOffset(math.max(200, #message * 19), label.Size.Y.Offset)
		t.Size = UDim2.fromOffset(label.Position.X.Offset + label.Size.X.Offset + 24, t.Size.Y.Offset)
	end
	local icon = iconIn(t)
	if icon and iconName then
		icon.Image = img(iconName)
	end
	if icon and zone and animalId then
		showAnimal(icon, zone, animalId, 20)
	end
	local cg = Instance.new("CanvasGroup")
	cg.Name = "ToastWrap"
	cg.BackgroundTransparency = 1
	cg.Size = t.Size
	cg.LayoutOrder = t.LayoutOrder
	cg.GroupTransparency = 1
	t.Position = UDim2.fromOffset(0, -20)
	t.Parent = cg
	cg.Parent = toastList
	tween(cg, 0.25, { GroupTransparency = 0 })
	tween(t, 0.35, { Position = UDim2.new() }, Enum.EasingStyle.Back)
	play(kind == "Error" and "Error" or "Toast")
	-- keep at most 4 on screen
	local all = kids(toastList, "CanvasGroup")
	for i = 5, #all do
		all[i]:Destroy()
	end
	task.delay(3, function()
		if cg.Parent then
			tween(t, 0.3, { Position = UDim2.fromOffset(0, 14) }, Enum.EasingStyle.Quad, Enum.EasingDirection.In)
			tween(cg, 0.3, { GroupTransparency = 1 }).Completed:Wait()
			cg:Destroy()
		end
	end)
end

-- the game's server messages (SeedRemotes.Notify) show as V2 toasts
SeedRemotes.Notify.OnClientEvent:Connect(function(message, kind)
	if type(message) ~= "string" then
		return
	end
	local lower = message:lower()
	local isError = lower:find("full") or lower:find("need") or lower:find("not enough") or lower:find("can't") or lower:find("closer") or lower:find("first")
	if isError then
		toast("Error", message, "Lock")
	elseif lower:find("hatch") then
		toast("Hatched", message, "EggRainbow")
	else
		toast("Speed", message, kind == "Secured" and "EggGold" or "Star")
	end
end)

-- "+$1.2M" rising off the currency counters
local function floatingGain(anchor, message, color)
	local tpl = T:FindFirstChild("FloatingGain")
	if not (tpl and anchor) then
		return
	end
	local f = tpl:Clone()
	f.Visible = true
	f.Text = message
	if color then
		f.TextColor3 = color
	end
	f.AnchorPoint = Vector2.new(0, 1)
	f.Position = UDim2.new(1, -10, 0, 10)
	f.Size = UDim2.fromOffset(260, f.Size.Y.Offset)
	f.ZIndex = 50
	f.Parent = anchor
	tween(f, 1.1, { Position = UDim2.new(1, -10, 0, -40), TextTransparency = 1 }, Enum.EasingStyle.Quad)
	local st = f:FindFirstChildOfClass("UIStroke")
	if st then
		tween(st, 1.1, { Transparency = 1 })
	end
	task.delay(1.2, function()
		f:Destroy()
	end)
end

---------------------------------------------------------------- currency (bottom left)
local currency = find(G("CurrencyDisplay"), "Body")
local leaderstats = player:WaitForChild("leaderstats")
local function bindStat(statName, rowName, fmt, color)
	local stat = leaderstats:WaitForChild(statName)
	local row = currency and currency:FindFirstChild(rowName)
	local label = row and text(row)
	if not label then
		return
	end
	label.TextXAlignment = Enum.TextXAlignment.Left
	local counter = Instance.new("NumberValue")
	counter.Value = stat.Value
	local plus = row:FindFirstChild("PlusButton")
	local function placePlus()
		if plus then
			local k = label.AbsoluteSize.X > 0 and label.Size.X.Offset / label.AbsoluteSize.X or 1
			plus.Position = UDim2.fromOffset(label.Position.X.Offset + label.TextBounds.X * k + 10, plus.Position.Y.Offset)
		end
	end
	label:GetPropertyChangedSignal("TextBounds"):Connect(placePlus)
	counter.Changed:Connect(function(v)
		label.Text = fmt(v)
	end)
	label.Text = fmt(stat.Value)
	task.defer(placePlus)
	stat.Changed:Connect(function(v)
		local diff = v - counter.Value
		tween(counter, 0.45, { Value = v })
		if diff > 0 then
			pop(iconIn(row), 1.18)
			pop(label, 1.1)
			if diff >= math.max(1, counter.Value * 0.002) then
				floatingGain(row, "+" .. (rowName:find("Cash") and "$" or "") .. short(diff), color)
			end
			if rowName:find("Cash") and os.clock() - (row:GetAttribute("LastTick") or 0) > 0.6 then
				row:SetAttribute("LastTick", os.clock())
				task.spawn(function()
					for i = 0, 3 do
						play("CountTick", 1 + i * 0.12)
						task.wait(0.09)
					end
				end)
			end
		end
	end)
end
task.spawn(bindStat, "Cash", "Currency/Cash", money, Color3.fromRGB(140, 255, 94))
task.spawn(bindStat, "Speed", "Currency/ShoeWinged", short, Color3.fromRGB(120, 220, 255))

---------------------------------------------------------------- windows (open / close)
local dim = gui:FindFirstChild("Dim")
local openWindow, openModal = nil, nil
local hudNames = { "LeftButtons", "CurrencyDisplay", "Hotbar", "ActivePets", "RightButtons", "Timers", "EggTimers" }
local hudShown = true
local function showHud(on)
	if on == hudShown then
		return
	end
	hudShown = on
	play(on and "HudIn" or "HudOut")
	for i, name in hudNames do
		local g = G(name)
		if g then
			local ax, ay = g:GetAttribute("AX"), g:GetAttribute("AY")
			local away = UDim2.fromScale(ax == 0 and -0.5 or (ax == 1 and 0.5 or 0), (ax == 0.5 and (ay == 1 and 0.5 or -0.5)) or 0)
			local goal = on and homeOf(g) or (homeOf(g) + away)
			g:SetAttribute("Sliding", not on)
			local info = on and TweenInfo.new(0.35, Enum.EasingStyle.Back, Enum.EasingDirection.Out, 0, false, (i - 1) * 0.025)
				or TweenInfo.new(0.22, Enum.EasingStyle.Back, Enum.EasingDirection.In)
			TweenService:Create(g, info, { Position = goal }):Play()
		end
	end
end

local function animateOpen(g)
	local w = g:FindFirstChild("Window") or g
	local s = scaleOf(w, "OpenScale")
	g.Visible = true
	s.Scale = 0.7
	tween(s, 0.3, { Scale = 1 }, Enum.EasingStyle.Back)
	local side = g:FindFirstChild("Side")
	if side then
		local ss = scaleOf(side, "OpenScale")
		ss.Scale = 0.5
		task.delay(0.08, function()
			tween(ss, 0.3, { Scale = 1 }, Enum.EasingStyle.Back)
		end)
	end
end
local function animateClose(g, stillOpen)
	local w = g:FindFirstChild("Window") or g
	local s = scaleOf(w, "OpenScale")
	tween(s, 0.16, { Scale = 0.75 }, Enum.EasingStyle.Quad, Enum.EasingDirection.In).Completed:Connect(function()
		if not stillOpen() then
			g.Visible = false
			s.Scale = 1
		end
	end)
end

local function refreshDim()
	if not dim then
		return
	end
	local on = openWindow ~= nil or openModal ~= nil
	dim.Visible = true
	tween(dim, 0.2, { BackgroundTransparency = on and 0.55 or 1 }).Completed:Connect(function()
		if not (openWindow or openModal) then
			dim.Visible = false
		end
	end)
end

local onOpen = {} -- [group name] = function() (re-render on open)
local function setWindow(g)
	if openWindow == g then
		g = nil
	end
	local prev = openWindow
	openWindow = g
	if openModal then
		local m = openModal
		openModal = nil
		animateClose(m, function()
			return openModal == m
		end)
	end
	if prev then
		play("Close")
		animateClose(prev, function()
			return openWindow == prev
		end)
	end
	showHud(g == nil)
	if g then
		play("Open")
		if onOpen[g.Name] then
			onOpen[g.Name]()
		end
		animateOpen(g)
	end
	refreshDim()
end
local function openByName(name)
	local g = G(name)
	if g and openWindow ~= g then
		setWindow(g)
	end
end
local function setModal(g)
	local prev = openModal
	openModal = g
	if prev and prev ~= g then
		animateClose(prev, function()
			return openModal == prev
		end)
	end
	if g then
		play("Open")
		animateOpen(g)
	elseif prev then
		play("Close")
	end
	refreshDim()
end

-- every window's red X closes it
for _, name in { "GrowingEggsWindow", "PetInventoryWindow", "IndexWindow", "ShopWindow", "SettingsWindow", "SellWindow", "TrailShopWindow", "FreeGiftWindow" } do
	local g = G(name)
	local close = g and find(g, "Window.Header.CloseButton")
	hookButton(close, function()
		setWindow(nil)
	end, "Close")
end
for _, name in { "ClaimModal", "ConfirmModal" } do
	local g = G(name)
	local close = g and find(g, "Window.Header.CloseButton")
	hookButton(close, function()
		setModal(nil)
	end, "Close")
end
if dim then
	dim.Active = true
end

---------------------------------------------------------------- left buttons (Shop / Index / Slow Mode)
local shopJump -- set in the Shop section
local left = find(G("LeftButtons"), "Body")
if left then
	local huds = {}
	for _, c in kids(left) do
		if c.Name == "HUDButton" then
			table.insert(huds, c)
		end
	end
	hookButton(huds[1], function()
		setWindow(G("ShopWindow"))
	end, false)
	hookButton(huds[2], function()
		setWindow(G("IndexWindow"))
	end, false)
	local slow = left:FindFirstChild("SlowModeToggle")
	local toggle = slow and slow:FindFirstChild("Toggle (ON)")
	local knob = toggle and toggle:FindFirstChild("Knob")
	if toggle and knob then
		local onPos = knob.Position
		local offPos = UDim2.fromOffset(6, onPos.Y.Offset)
		local onFill = toggle:FindFirstChildOfClass("UIGradient")
		local function show(on)
			tween(knob, 0.15, { Position = on and onPos or offPos })
			toggle.BackgroundColor3 = Color3.new(1, 1, 1)
			if onFill then
				onFill.Enabled = on
			end
			toggle.BackgroundTransparency = on and 0 or 0.1
			if not on then
				toggle.BackgroundColor3 = Color3.fromRGB(70, 72, 80)
			end
		end
		hookButton(toggle, function()
			local on = not player:GetAttribute("SlowMode")
			show(on)
			play(on and "ToggleOn" or "ToggleOff")
			SeedRemotes.SetSlowMode:FireServer(on)
		end, false)
		player:GetAttributeChangedSignal("SlowMode"):Connect(function()
			show(player:GetAttribute("SlowMode") == true)
		end)
		show(player:GetAttribute("SlowMode") == true)
	end
end
-- currency "+" buttons jump into the shop
if currency then
	for _, row in { "Currency/Cash", "Currency/ShoeWinged" } do
		local r = currency:FindFirstChild(row)
		local plus = r and r:FindFirstChild("PlusButton")
		hookButton(plus, function()
			setWindow(G("ShopWindow"))
			task.delay(0.05, function()
				if shopJump then
					shopJump(row == "Currency/Cash" and "Money" or "Speed", true)
				end
			end)
		end, false)
	end
end

---------------------------------------------------------------- timers (bottom right): day / night
local timers = find(G("Timers"), "Body")
if timers then
	local lock = timers:FindFirstChild("LockButton")
	if lock then
		lock.Visible = false -- no plot lock in this game
	end
	local base = timers:FindFirstChild("BaseTimer")
	local label = base and text(base)
	if base then
		-- sit where the lock was (right-aligned)
		base.Position = UDim2.fromOffset(422 - base.Size.X.Offset, base.Position.Y.Offset)
	end
	if label then
		label.TextXAlignment = Enum.TextXAlignment.Left
		RunService.Heartbeat:Connect(function()
			local endsAt = SeedShared:GetAttribute("PhaseEndsAt")
			if not endsAt then
				return
			end
			local secs = endsAt - workspace:GetServerTimeNow()
			local night = SeedShared:GetAttribute("CyclePhase") == "Night"
			label.Text = (night and "ends " or "in ") .. clock(secs)
			label.TextColor3 = (night or secs <= 60) and Color3.fromRGB(255, 90, 90) or Color3.new(1, 1, 1)
		end)
	end
end

---------------------------------------------------------------- hotbar (replaces the Roblox backpack)
local hotbarGroup = G("Hotbar")
local slotsFrame = find(hotbarGroup, "Body")
local slotTemplate = T:FindFirstChild("HotbarSlot")
local stacks = {}
local slotObjs = {}
local function backpack()
	return player:FindFirstChildOfClass("Backpack")
end
local function equipped()
	local char = player.Character
	return char and char:FindFirstChildOfClass("Tool")
end
local function useStack(s)
	local hum = player.Character and player.Character:FindFirstChildOfClass("Humanoid")
	if not (s and hum) then
		return
	end
	local cur = equipped()
	if cur and cur.Name == s.Name then
		hum:UnequipTools()
	else
		for _, t in s.Tools do
			if t.Parent == backpack() then
				hum:EquipTool(t)
				break
			end
		end
	end
end
local function rebuildHotbar()
	if not (slotsFrame and slotTemplate) then
		return
	end
	local order, byName = {}, {}
	local function add(tool)
		if not tool:IsA("Tool") then
			return
		end
		if not byName[tool.Name] then
			byName[tool.Name] = { Name = tool.Name, Tools = {} }
			table.insert(order, byName[tool.Name])
		end
		table.insert(byName[tool.Name].Tools, tool)
	end
	local bp = backpack()
	if bp then
		for _, t in bp:GetChildren() do
			add(t)
		end
	end
	local held = equipped()
	if held then
		add(held)
	end
	local rank = {}
	for i, s in stacks do
		rank[s.Name] = i
	end
	table.sort(order, function(a, b)
		return (rank[a.Name] or 1e6 + #a.Name) < (rank[b.Name] or 1e6 + #b.Name)
	end)
	stacks = order
	for i = #slotObjs, #stacks + 1, -1 do
		slotObjs[i]:Destroy()
		slotObjs[i] = nil
	end
	for i, stack in stacks do
		local slot = slotObjs[i]
		if not slot then
			slot = slotTemplate:Clone()
			slot.Name = "Slot" .. i
			slot.Visible = true
			slot.LayoutOrder = i
			slot.Parent = slotsFrame
			slotObjs[i] = slot
			local index = i
			hookButton(slot, function()
				useStack(stacks[index])
				play("Hotbar", 1 + (index - 1) * 0.06)
			end, false)
			pop(slot, 0.8)
		end
		local key = text(slot)
		if key then
			key.Text = i <= 9 and tostring(i) or ""
		end
		local count = slot:FindFirstChild("Count")
		if not count and key then
			count = key:Clone()
			count.Name = "Count"
			count.TextXAlignment = Enum.TextXAlignment.Right
			count.Position = UDim2.fromOffset(60, 90)
			count.Size = UDim2.fromOffset(56, 27)
			count.Parent = slot
		end
		if count then
			count.Text = #stack.Tools > 1 and ("x" .. #stack.Tools) or ""
		end
		local icon = slot:FindFirstChild("Icon")
		local vp = icon and viewportOver(icon)
		if vp and vp:GetAttribute("Showing") ~= stack.Name then
			vp:SetAttribute("Showing", stack.Name)
			local tool = stack.Tools[1]
			setPreview(vp, tool:FindFirstChild("AnimalModel") or tool, 25)
		end
		local sel = held ~= nil and held.Name == stack.Name
		local st = slot:FindFirstChildOfClass("UIStroke")
		if st then
			st.Color = sel and Color3.fromRGB(120, 255, 90) or Color3.fromRGB(14, 14, 16)
			st.Thickness = sel and 5 or 3
		end
	end
	hotbarGroup.Visible = #stacks > 0
end
local pending = false
local function queueHotbar()
	if pending then
		return
	end
	pending = true
	task.defer(function()
		pending = false
		rebuildHotbar()
	end)
end
local function watchContainer(c)
	if not c then
		return
	end
	c.ChildAdded:Connect(queueHotbar)
	c.ChildRemoved:Connect(queueHotbar)
	queueHotbar()
end
player.ChildAdded:Connect(function(c)
	if c:IsA("Backpack") then
		watchContainer(c)
	end
end)
watchContainer(backpack())
player.CharacterAdded:Connect(watchContainer)
if player.Character then
	watchContainer(player.Character)
end
UserInputService.InputBegan:Connect(function(input, processed)
	if processed or UserInputService:GetFocusedTextBox() or input.UserInputType ~= Enum.UserInputType.Keyboard then
		return
	end
	local n = input.KeyCode.Value - Enum.KeyCode.Zero.Value
	if n >= 1 and n <= 9 and slotObjs[n] then
		useStack(stacks[n])
		pop(slotObjs[n], 0.9)
		play("Hotbar", 1 + (n - 1) * 0.06)
	end
end)

---------------------------------------------------------------- right buttons + side panels (Hatching / Active Pets)
local rightBody = find(G("RightButtons"), "Body")
local eggPanel, petPanel = G("EggTimers"), G("ActivePets")
local panelOpen = {}
local function onDot(button)
	for _, c in button:GetChildren() do
		if c.Name:find("^OnDot") then
			return c
		end
	end
end
local function setPanel(panel, button, on)
	panelOpen[panel] = on
	if on then
		panel.Visible = true
		local s = scaleOf(panel, "OpenScale")
		s.Scale = 0.85
		tween(s, 0.25, { Scale = 1 }, Enum.EasingStyle.Back)
		play("PanelOpen")
	else
		local s = scaleOf(panel, "OpenScale")
		play("PanelClose")
		tween(s, 0.15, { Scale = 0.85 }).Completed:Connect(function()
			if not panelOpen[panel] then
				panel.Visible = false
			end
		end)
	end
	local dot = button and onDot(button)
	if dot then
		dot.Visible = on
		if on then
			pop(dot, 1.5)
		end
	end
end
if rightBody then
	local hatchB = rightBody:FindFirstChild("Right/HatchingToggle")
	local petsB = rightBody:FindFirstChild("Right/PetsToggle")
	-- big screens start with both panels open, phones with them tucked away
	local startOpen = not touchOnly() and gui.AbsoluteSize.X >= 1100
	if eggPanel then
		eggPanel.Visible = startOpen
		panelOpen[eggPanel] = startOpen
		local d = hatchB and onDot(hatchB)
		if d then
			d.Visible = startOpen
		end
	end
	if petPanel then
		petPanel.Visible = startOpen
		panelOpen[petPanel] = startOpen
		local d = petsB and onDot(petsB)
		if d then
			d.Visible = startOpen
		end
	end
	hookButton(hatchB, function()
		setPanel(eggPanel, hatchB, not panelOpen[eggPanel])
	end, false)
	hookButton(petsB, function()
		setPanel(petPanel, petsB, not panelOpen[petPanel])
	end, false)
	hookButton(rightBody:FindFirstChild("Right/Rewards"), function()
		setWindow(G("FreeGiftWindow"))
	end, false)
	hookButton(rightBody:FindFirstChild("Right/Settings"), function()
		setWindow(G("SettingsWindow"))
	end, false)
end

-- headers open the full windows
local function headerButton(panel, onClick)
	local header = find(panel, "Body.Header")
	if not header then
		return
	end
	local b = Instance.new("TextButton")
	b.Name = "HeaderHit"
	b.Text = ""
	b.BackgroundTransparency = 1
	b.Size = UDim2.new(0.75, 0, 1, 0)
	b.ZIndex = 100
	b.Parent = header
	hookButton(b, onClick, false)
end
headerButton(eggPanel, function()
	setWindow(G("GrowingEggsWindow"))
end)
headerButton(petPanel, function()
	setWindow(G("PetInventoryWindow"))
end)

---------------------------------------------------------------- Active Pets panel
-- shrink/grow a HUD panel's list to its rows (up to the Figma height), moving the footers under it
local function fitPanel(panel, maxH, footers)
	local body = panel and panel:FindFirstChild("Body")
	local list = body and body:FindFirstChild("List")
	local layout = list and list:FindFirstChildOfClass("UIListLayout")
	if not layout then
		return
	end
	task.defer(function()
		local k = list.AbsoluteSize.Y > 0 and list.Size.Y.Offset / list.AbsoluteSize.Y or 1
		local content = math.ceil(layout.AbsoluteContentSize.Y * k) + 4
		local h = math.clamp(content, 84, maxH)
		list.Size = UDim2.fromOffset(list.Size.X.Offset, h)
		list.CanvasSize = UDim2.fromOffset(0, content)
		local y = list.Position.Y.Offset + h
		for _, f in footers do
			local fr = body:FindFirstChild(f.Name)
			if fr then
				local fh = f.Height and f.Height() or fr.Size.Y.Offset
				fr.Position = UDim2.fromOffset(fr.Position.X.Offset, y)
				fr.Visible = fh > 0
				y += fh
			end
		end
		body.Size = UDim2.fromOffset(body.Size.X.Offset, y + 5)
	end)
end
local petList = find(petPanel, "Body.List")
local petRows = {}
local function renderPets()
	if not (petPanel and state and petList) then
		return
	end
	local pets = state.Pets
	local count = find(petPanel, "Body.Header.Count")
	setText(count and text(count), ("%d/%d"):format(#pets.Placed, pets.Slots))
	local seen = {}
	for i, a in pets.Placed do
		seen[a.Id] = true
		local row = petRows[a.Id]
		if not row then
			row = T.PetRow:Clone()
			row.Name = "Pet_" .. a.Id
			row.Visible = true
			row.Parent = petList
			petRows[a.Id] = row
			showAnimal(iconIn(row), a.Zone, a.AnimalId, 30)
			local id = a.Id
			hookButton(row:FindFirstChild("CloseButton"), function()
				Remote:FireServer("Unequip", id)
			end)
			pop(row, 0.9)
		end
		row.LayoutOrder = i
		local label = text(row)
		if label then
			label.RichText = true
			label.Text = ("%s <font size=\"20\" color=\"#8cff5e\">%s/s</font>"):format(a.Animal, money(a.Income))
			label.TextColor3 = rarityColor(a.Rarity)
		end
	end
	for id, row in petRows do
		if not seen[id] then
			row:Destroy()
			petRows[id] = nil
		end
	end
	-- empty slots
	for _, c in petList:GetChildren() do
		if c.Name == "EmptyPetRow" then
			c:Destroy()
		end
	end
	for i = #pets.Placed + 1, math.min(pets.Slots, #pets.Placed + 3) do
		local e = T.EmptyPetRow:Clone()
		e.Name = "EmptyPetRow"
		e.Visible = true
		e.LayoutOrder = 1000 + i
		e.Parent = petList
	end
	-- +1 slot: the plot upgrade (Cash)
	local buy1 = find(petPanel, "Body.RobuxSlots.BuySlot1")
	local buy3 = find(petPanel, "Body.RobuxSlots.BuySlot3")
	if buy3 then
		buy3.Visible = false
	end
	if buy1 then
		buy1.Visible = state.NextSlotCost ~= nil
		local price = buy1:FindFirstChild("RobuxPrice")
		if price then
			local coin = iconIn(price)
			if coin then
				coin.Visible = false
			end
			local l = text(price)
			if l and state.NextSlotCost then
				l.Text = money(state.NextSlotCost)
				l.Position = UDim2.fromOffset(4, l.Position.Y.Offset)
				l.Size = UDim2.fromOffset(price.Size.X.Offset - 8 + 40, l.Size.Y.Offset)
				l.TextXAlignment = Enum.TextXAlignment.Center
				price.Size = UDim2.fromOffset(110, price.Size.Y.Offset)
				price.Position = UDim2.fromOffset(366 - 12 - 110, price.Position.Y.Offset)
			end
		end
	end
	fitPanel(petPanel, 360, {
		{ Name = "Footer" },
		{ Name = "RobuxSlots", Height = function()
			return (buy1 and buy1.Visible) and 62 or 0
		end },
	})
end
if petPanel then
	hookButton(find(petPanel, "Body.Footer.EquipBestButton"), function()
		Remote:FireServer("EquipBest")
	end, "Equip")
	hookButton(find(petPanel, "Body.Footer.RemoveAllButton"), function()
		Remote:FireServer("RemoveAll")
	end)
	hookButton(find(petPanel, "Body.RobuxSlots.BuySlot1"), function(b)
		if state and state.NextSlotCost and leaderstats.Cash.Value < state.NextSlotCost then
			shake(b)
			toast("Error", ("Not enough cash! Need %s more"):format(money(state.NextSlotCost - leaderstats.Cash.Value)), "Lock")
			return
		end
		SeedRemotes.UpgradePlot:FireServer()
	end)
end

---------------------------------------------------------------- Hatching panel (eggs growing on your plot)
local eggList = find(eggPanel, "Body.List")
local eggRows = {}
local function renderEggPanel()
	if not (eggPanel and state and eggList) then
		return
	end
	local eggs = state.Pets.Eggs
	local count = find(eggPanel, "Body.Header.Count")
	setText(count and text(count), ("%d/%d"):format(#eggs, math.max(state.Pets.Slots - #state.Pets.Placed, #eggs)))
	local now = workspace:GetServerTimeNow()
	local seen = {}
	for i, e in eggs do
		local ready = now >= e.FinishAt
		local key = e.Id .. (ready and "_R" or "_G")
		seen[key] = true
		local row = eggRows[key]
		if not row then
			row = (ready and T.EggRowReady or T.EggRowGrowing):Clone()
			row.Name = "Egg_" .. key
			row.Visible = true
			row.Parent = eggList
			eggRows[key] = row
			row:SetAttribute("FinishAt", e.FinishAt)
			row:SetAttribute("GrowTime", e.GrowTime)
			showEgg(iconIn(row), e.Zone, e.EggId)
			local id = e.Id
			if ready then
				hookButton(row:FindFirstChild("HatchButton"), function()
					Remote:FireServer("Hatch", id)
				end, "Pop")
			else
				hookButton(row:FindFirstChild("SpeedUpButton"), function()
					Remote:FireServer("Buy", "GrowAll")
				end)
			end
			pop(row, 0.9)
		end
		row.LayoutOrder = i
	end
	for key, row in eggRows do
		if not seen[key] then
			row:Destroy()
			eggRows[key] = nil
		end
	end
	for _, c in eggList:GetChildren() do
		if c.Name == "EmptyEggRow" then
			c:Destroy()
		end
	end
	local free = state.Pets.Slots - #state.Pets.Placed - #eggs
	if free > 0 then
		local e = T.EmptyEggRow:Clone()
		e.Name = "EmptyEggRow"
		e.Visible = true
		e.LayoutOrder = 1000
		e.Parent = eggList
		hookButton(e:FindFirstChild("GetEggsButton"), function()
			setWindow(G("ShopWindow"))
			task.delay(0.05, function()
				if shopJump then
					shopJump("Featured", true)
				end
			end)
		end)
	end
	local ga = find(eggPanel, "Body.GrowFooter.GrowAllButton")
	if ga then
		local price = find(ga, "RobuxPrice")
		setText(price and text(price), tostring(C.Products.GrowAll and C.Products.GrowAll.Price or ""))
	end
	fitPanel(eggPanel, 276, { { Name = "GrowFooter" } })
end
if eggPanel then
	hookButton(find(eggPanel, "Body.GrowFooter.GrowAllButton"), function()
		Remote:FireServer("Buy", "GrowAll")
	end)
end

---------------------------------------------------------------- Growing Eggs window (big cards)
local growWin = G("GrowingEggsWindow")
local growRow = growWin and find(growWin, "Window.Body.Content.Row")
local growCards = {}
local function renderGrowWindow()
	if not (growRow and state) then
		return
	end
	local eggs = state.Pets.Eggs
	local seen = {}
	for i, e in eggs do
		seen[e.Id] = true
		local card = growCards[e.Id]
		if not card then
			card = T.EggSlot:Clone()
			card.Name = "Egg_" .. e.Id
			card.Visible = true
			card.Parent = growRow
			growCards[e.Id] = card
			card:SetAttribute("FinishAt", e.FinishAt)
			card:SetAttribute("GrowTime", e.GrowTime)
			showEgg(iconIn(card), e.Zone, e.EggId)
			local id = e.Id
			hookButton(card:FindFirstChild("Button"), function()
				if workspace:GetServerTimeNow() >= (card:GetAttribute("FinishAt") or 0) then
					Remote:FireServer("Hatch", id)
				else
					Remote:FireServer("Buy", "GrowAll")
				end
			end)
			local glow = card:FindFirstChild("Ellipse")
			if glow then
				glow.BackgroundColor3 = rarityColor(e.Rarity)
			end
		end
		card.LayoutOrder = i
	end
	for id, card in growCards do
		if not seen[id] then
			card:Destroy()
			growCards[id] = nil
		end
	end
	for _, c in growRow:GetChildren() do
		if c.Name == "EggSlotEmpty" then
			c:Destroy()
		end
	end
	local free = state.Pets.Slots - #state.Pets.Placed - #eggs
	for i = 1, math.clamp(free, 0, 4) do
		local e = T.EggSlotEmpty:Clone()
		e.Name = "EggSlotEmpty"
		e.Visible = true
		e.LayoutOrder = 1000 + i
		e.Parent = growRow
		hookButton(e:FindFirstChild("Button"), function()
			setWindow(G("ShopWindow"))
			task.delay(0.05, function()
				if shopJump then
					shopJump("Featured", true)
				end
			end)
		end)
	end
end
onOpen.GrowingEggsWindow = renderGrowWindow

-- live timers + progress bars (panel rows and window cards)
RunService.Heartbeat:Connect(function()
	local now = workspace:GetServerTimeNow()
	local function tick(obj, labelParent)
		local f, g = obj:GetAttribute("FinishAt"), obj:GetAttribute("GrowTime")
		if not f then
			return
		end
		local left = f - now
		local p = g and g > 0 and math.clamp(1 - left / g, 0, 1) or 1
		local bar = obj:FindFirstChild("ProgressBar", true)
		local fill = bar and bar:FindFirstChild("Fill")
		if fill then
			fill.Size = UDim2.new(p, 0, 1, 0)
		end
		local l = labelParent and text(labelParent)
		if l then
			l.Text = left <= 0 and "READY!" or clock(left)
			l.TextColor3 = left <= 0 and Color3.fromRGB(155, 247, 102) or Color3.new(1, 1, 1)
		end
		if left <= 0 and not obj:GetAttribute("WasReady") then
			obj:SetAttribute("WasReady", true)
			if obj.Parent == eggList or obj.Parent == growRow then
				task.defer(function()
					renderEggPanel()
					renderGrowWindow()
				end)
			end
		end
	end
	if eggPanel and eggPanel.Visible then
		for _, row in eggRows do
			tick(row, row:FindFirstChild("Info"))
		end
	end
	if growWin and growWin.Visible then
		for _, card in growCards do
			tick(card, card)
			local b = card:FindFirstChild("Button")
			local l = b and text(b)
			if l then
				local ready = now >= (card:GetAttribute("FinishAt") or 0)
				l.Text = ready and "HATCH!" or "SPEED UP"
			end
		end
	end
end)

---------------------------------------------------------------- My Pets (inventory)
local petsWin = G("PetInventoryWindow")
local invFilter = "All"
local invCards = {}
local RARITY_ORDER = { "Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythic", "Cosmic", "Secret" }
local RARITY_RANK = {}
for i, r in RARITY_ORDER do
	RARITY_RANK[r] = i
end
local function allOwned()
	local list = {}
	if not state then
		return list
	end
	for _, a in state.Pets.Placed do
		table.insert(list, { Id = a.Id, Zone = a.Zone, AnimalId = a.AnimalId, Animal = a.Animal, Rarity = a.Rarity, Income = a.Income, Placed = true })
	end
	for _, a in state.Pets.Hand or {} do
		table.insert(list, { Id = a.Id, Zone = a.Zone, AnimalId = a.AnimalId, Animal = a.Animal, Rarity = a.Rarity, Income = a.Income, Placed = false })
	end
	table.sort(list, function(a, b)
		return a.Income > b.Income
	end)
	return list
end
-- centred "nothing here yet" message over a grid
local function emptyNote(grid, show, msg)
	if not grid then
		return
	end
	local note = grid.Parent:FindFirstChild("EmptyNote_" .. grid.Name)
	if show and not note then
		note = Instance.new("TextLabel")
		note.Name = "EmptyNote_" .. grid.Name
		note.BackgroundTransparency = 1
		note.AnchorPoint = Vector2.new(0.5, 0.5)
		note.Size = UDim2.fromOffset(math.min(460, grid.Size.X.Offset - 20), 90)
		note.Position = UDim2.fromOffset(grid.Position.X.Offset + grid.Size.X.Offset / 2, grid.Position.Y.Offset + grid.Size.Y.Offset / 2)
		note.FontFace = Font.new("rbxasset://fonts/families/FredokaOne.json")
		note.TextSize = 30
		note.TextColor3 = Color3.fromRGB(200, 200, 210)
		note.TextWrapped = true
		note.ZIndex = 20
		local st = Instance.new("UIStroke")
		st.Thickness = 2.5
		st.Color = Color3.fromRGB(14, 14, 16)
		st.Parent = note
		note.Parent = grid.Parent
	end
	if note then
		note.Visible = show
		if show then
			note.Text = msg
		end
	end
end
local function renderInventory()
	if not (petsWin and state) then
		return
	end
	local body = find(petsWin, "Window.Body")
	local side = body.Sidebar
	local grid = find(body, "Content.Grid")
	-- tabs: All + every rarity you own
	local owned = allOwned()
	local has = {}
	for _, a in owned do
		has[a.Rarity] = true
	end
	local tabs = { "All" }
	for i, r in RARITY_ORDER do
		if has[r] or i <= 4 then
			table.insert(tabs, r)
		end
	end
	local key = table.concat(tabs, ",") .. "|" .. invFilter
	if side:GetAttribute("Key") ~= key then
		side:SetAttribute("Key", key)
		for _, c in side:GetChildren() do
			if c:IsA("GuiObject") then
				c:Destroy()
			end
		end
		for i, r in tabs do
			local tab = (r == invFilter and T.InvTabSelected or T.InvTab):Clone()
			tab.Name = "Tab_" .. r
			tab.Visible = true
			tab.LayoutOrder = i
			setText(text(tab), r)
			local ic = iconIn(tab)
			if ic and r ~= "All" then
				ic.ImageColor3 = rarityColor(r)
			end
			tab.Parent = side
			hookButton(tab, function()
				invFilter = r
				renderInventory()
			end, "Tab")
		end
	end
	local seen = {}
	local shown = 0
	for i, a in owned do
		if invFilter == "All" or a.Rarity == invFilter then
			shown += 1
			seen[a.Id] = true
			local card = invCards[a.Id]
			if not card then
				card = T.InvCard:Clone()
				card.Name = "Pet_" .. a.Id
				card.Visible = true
				card.Parent = grid
				invCards[a.Id] = card
				showAnimal(iconIn(card), a.Zone, a.AnimalId, 30)
				local l = text(card)
				if l then
					l.Text = a.Animal
					l.TextColor3 = rarityColor(a.Rarity)
				end
				local sub = l and l:Clone()
				if sub then
					sub.Name = "Income"
					sub.TextSize = 20
					sub.TextColor3 = Color3.fromRGB(140, 255, 94)
					sub.Position = l.Position + UDim2.fromOffset(0, 32)
					sub.Text = money(a.Income) .. "/s"
					sub.Parent = card
				end
				local id, placed = a.Id, a.Placed
				hookButton(card, function()
					if placed then
						Remote:FireServer("Unequip", id)
					else
						Remote:FireServer("EquipItem", id)
					end
				end, "Equip")
			end
			card.LayoutOrder = i
			local st = card:FindFirstChildOfClass("UIStroke")
			if st then
				st.Color = a.Placed and Color3.fromRGB(120, 255, 90) or Color3.fromRGB(14, 14, 16)
				st.Thickness = a.Placed and 5 or 3
			end
		end
	end
	for id, card in invCards do
		if not seen[id] then
			card:Destroy()
			invCards[id] = nil
		end
	end
	emptyNote(grid, shown == 0, invFilter == "All" and "No pets yet!\nHatch eggs to fill your collection." or ("No " .. invFilter .. " pets yet!"))
	local footer = find(body, "Content.Footer")
	if footer then
		local l = text(footer)
		setText(l, ("%d/%d Equipped"):format(#state.Pets.Placed, state.Pets.Slots))
		local buttons = {}
		for _, c in kids(footer) do
			if c.Name == "Button" then
				table.insert(buttons, c)
			end
		end
		if buttons[2] then
			setText(text(buttons[2]), "SELL")
		end
	end
end
onOpen.PetInventoryWindow = renderInventory
if petsWin then
	local footer = find(petsWin, "Window.Body.Content.Footer")
	if footer then
		local buttons = {}
		for _, c in kids(footer) do
			if c.Name == "Button" then
				table.insert(buttons, c)
			end
		end
		hookButton(buttons[1], function()
			Remote:FireServer("EquipBest")
		end, "Equip")
		hookButton(buttons[2], function()
			setWindow(G("SellWindow"))
		end)
	end
end

---------------------------------------------------------------- Pet Index
local indexWin = G("IndexWindow")
local indexZone = C.ZoneOrder[1]
local indexCards = {}
local function zoneAnimals(zone)
	local list, seen = {}, {}
	local z = DD.ZoneEggs[zone]
	if z then
		for _, egg in z.Eggs do
			for _, a in egg.Animals do
				if not seen[a.Id] then
					seen[a.Id] = true
					table.insert(list, a)
				end
			end
		end
	end
	table.sort(list, function(a, b)
		return (RARITY_RANK[a.Rarity] or 99) < (RARITY_RANK[b.Rarity] or 99)
	end)
	return list
end
local function isFound(zone, id)
	return state and state.Discovered and state.Discovered[zone .. "_" .. id] == true
end
local function zoneDone(zone)
	for _, a in zoneAnimals(zone) do
		if not isFound(zone, a.Id) then
			return false
		end
	end
	return true
end
local function renderIndex()
	if not (indexWin and state) then
		return
	end
	local body = find(indexWin, "Window.Body")
	local side = body.Sidebar
	local grid = find(body, "Content.Grid")
	local key = indexZone .. "|" .. tostring(state.Claimable)
	if side:GetAttribute("Key") ~= key then
		side:SetAttribute("Key", key)
		for _, c in side:GetChildren() do
			if c:IsA("GuiObject") then
				c:Destroy()
			end
		end
		for i, zone in C.ZoneOrder do
			local tab = (zone == indexZone and T.IndexTabSelected or T.IndexTab):Clone()
			tab.Name = "Tab_" .. zone
			tab.Visible = true
			tab.LayoutOrder = i
			setText(text(tab), C.ZoneNames[zone] or zone)
			local ic = iconIn(tab)
			if ic then
				ic.Image = img(C.ZoneIconsV2[zone] or "ZoneForest")
			end
			tab.Parent = side
			local claimable = zoneDone(zone) and not (state.Claimed and state.Claimed[zone])
			if claimable then
				local badge = Instance.new("Frame")
				badge.Name = "Badge"
				badge.Size = UDim2.fromOffset(22, 22)
				badge.Position = UDim2.new(1, -16, 0, -6)
				badge.BackgroundColor3 = Color3.fromRGB(255, 60, 60)
				local c = Instance.new("UICorner")
				c.CornerRadius = UDim.new(0.5, 0)
				c.Parent = badge
				badge.ZIndex = 50
				badge.Parent = tab
				pop(badge, 1.4)
			end
			hookButton(tab, function()
				if claimable then
					Remote:FireServer("ClaimIndex", zone)
				end
				indexZone = zone
				renderIndex()
			end, "Tab")
		end
	end
	for _, c in indexCards do
		c:Destroy()
	end
	indexCards = {}
	local found, total = 0, 0
	for i, a in zoneAnimals(indexZone) do
		total += 1
		local ok = isFound(indexZone, a.Id)
		if ok then
			found += 1
		end
		local card = (ok and T.IndexCard or T.IndexCardUnknown):Clone()
		card.Name = "Card_" .. a.Id
		card.Visible = true
		card.LayoutOrder = i
		card.Parent = grid
		table.insert(indexCards, card)
		local l = texts(card)
		if ok then
			setText(l[1], a.Animal)
			setText(l[2], a.Rarity)
			if l[2] then
				l[2].TextColor3 = rarityColor(a.Rarity)
			end
			showAnimal(iconIn(card), indexZone, a.Id, 30)
		else
			local ic = iconIn(card)
			local vp = viewportOver(ic)
			if vp then
				vp:SetAttribute("Showing", nil)
				task.spawn(function()
					setPreview(vp, waitFor(function()
						return animalPreview(indexZone, a.Id)
					end), 30)
					vp.ImageColor3 = Color3.new(0, 0, 0)
					vp.ImageTransparency = 0.35
				end)
			end
			setText(l[2], a.Rarity)
			if l[2] then
				l[2].TextColor3 = rarityColor(a.Rarity)
			end
		end
	end
	-- whole-game progress bar
	local allFound, allTotal = 0, 0
	for _, zone in C.ZoneOrder do
		for _, a in zoneAnimals(zone) do
			allTotal += 1
			if isFound(zone, a.Id) then
				allFound += 1
			end
		end
	end
	local bar = find(body, "Content.ProgressBar")
	if bar then
		local fill = bar:FindFirstChild("Fill")
		if fill then
			tween(fill, 0.4, { Size = UDim2.new(allTotal > 0 and allFound / allTotal or 0, 0, 1, 0) })
		end
		setText(text(bar), ("Unlocked: %d / %d"):format(allFound, allTotal))
	end
end
onOpen.IndexWindow = renderIndex

-- Claim modal (a zone reward)
local claimModal = G("ClaimModal")
local function showClaimed(zone)
	if not claimModal then
		return
	end
	local body = find(claimModal, "Window.Body")
	local reward = C.IndexRewards[zone] or {}
	local parts = {}
	if reward.Cash then
		table.insert(parts, money(reward.Cash))
	end
	if reward.Speed then
		table.insert(parts, short(reward.Speed) .. " Speed")
	end
	local msg
	for _, c in texts(body) do
		msg = c
	end
	setText(msg, ("%s complete! +%s"):format(C.ZoneNames[zone] or zone, table.concat(parts, " + ")))
	local row = body:FindFirstChild("Frame")
	if row then
		local frames = kids(row)
		local animals = zoneAnimals(zone)
		for i, f in frames do
			local a = animals[i]
			f.Visible = a ~= nil
			if a then
				showAnimal(iconIn(f), zone, a.Id, 30)
			end
		end
	end
	local btn = body:FindFirstChild("Button")
	setText(btn and text(btn), "AWESOME!")
	setModal(claimModal)
	local chest = find(body, "ChestBurst")
	if chest then
		pop(chest, 0.6)
	end
end
if claimModal then
	hookButton(find(claimModal, "Window.Body.Button"), function()
		setModal(nil)
	end)
end

---------------------------------------------------------------- Shop
local shopWin = G("ShopWindow")
local sections = {}
local sectionButtons = {}
if shopWin then
	local scroll = find(shopWin, "Window.Body.Scroll")
	for _, c in scroll:GetChildren() do
		local key = c:GetAttribute("Section")
		if key then
			sections[key] = c
		end
	end
	local suppress = 0
	local function selectCat(key)
		for k, b in sectionButtons do
			local on = k == key
			local st = b:FindFirstChildOfClass("UIStroke")
			tween(scaleOf(b, "SelScale"), 0.15, { Scale = on and 1.08 or 1 })
			if st then
				st.Color = on and Color3.fromRGB(255, 225, 77) or Color3.fromRGB(14, 14, 16)
			end
		end
	end
	shopJump = function(key, instant)
		local target = sections[key]
		if not (scroll and target) then
			return
		end
		local y = scroll.CanvasPosition.Y + (target.AbsolutePosition.Y - scroll.AbsolutePosition.Y)
		local maxY = math.max(0, scroll.AbsoluteCanvasSize.Y - scroll.AbsoluteWindowSize.Y)
		local goal = Vector2.new(0, math.clamp(y, 0, maxY))
		suppress = os.clock() + (instant and 0 or 0.5)
		if instant then
			scroll.CanvasPosition = goal
		else
			tween(scroll, 0.45, { CanvasPosition = goal }, Enum.EasingStyle.Quint)
		end
		selectCat(key)
	end
	for _, b in shopWin.Side:GetChildren() do
		local key = b:GetAttribute("Section")
		if key and b:IsA("GuiButton") then
			sectionButtons[key] = b
			hookButton(b, function()
				shopJump(key)
			end, "Tab")
		end
	end
	scroll:GetPropertyChangedSignal("CanvasPosition"):Connect(function()
		if os.clock() < suppress then
			return
		end
		local best, bestY = nil, -math.huge
		local edge = scroll.AbsoluteWindowSize.Y * 0.3
		for key, sec in sections do
			local y = sec.AbsolutePosition.Y - scroll.AbsolutePosition.Y
			if y <= edge and y > bestY and sectionButtons[key] then
				best, bestY = key, y
			end
		end
		if best then
			selectCat(best)
		end
	end)
	selectCat("Featured")

	local function buy(key)
		if key == "Treadmill" then
			SeedRemotes.RobuxTreadmill:FireServer()
		else
			Remote:FireServer("Buy", key)
		end
	end
	-- product cards from Config rows
	local function fillCard(card, key)
		local p = C.Products[key]
		if not p then
			card.Visible = false
			return
		end
		card:SetAttribute("Product", key)
		local l = texts(card)[1]
		if l then
			l.RichText = true
			if p.Kind == "Speed" then
				l.Text = ('<font color="#39e62b">+%s</font> SPEED'):format(short(p.Amount))
			else
				l.Text = money(p.Amount)
			end
			l.Size = UDim2.fromOffset(300, l.Size.Y.Offset)
			l.Position = UDim2.fromOffset((325 - 300) / 2, l.Position.Y.Offset)
			l.TextXAlignment = Enum.TextXAlignment.Center
		end
		local art = C.ProductArtV2 and C.ProductArtV2[key]
		for _, c in card:GetChildren() do
			if c:IsA("ImageLabel") and c.Name:match("^Icon/") and art then
				c.Image = img(art)
			end
		end
		local btn = find(card, "PriceRow.Button")
		if btn then
			setText(text(btn), tostring(p.Price))
			hookButton(btn, function()
				buy(key)
			end)
		end
		local gift = find(card, "PriceRow.GiftButton")
		hookButton(gift, function()
			toast("Error", "Gifting is coming soon!", "Gift")
		end, false)
	end
	local function grid(name, rows, tplName)
		local g = scroll:FindFirstChild(name)
		local tpl = T:FindFirstChild(tplName)
		if not (g and tpl) then
			return
		end
		local i = 0
		for _, row in rows do
			for _, key in row do
				i += 1
				local card = tpl:Clone()
				card.Name = "Product_" .. key
				card.Visible = true
				card.LayoutOrder = i
				card.Position = UDim2.new()
				card.Parent = g
				fillCard(card, key)
			end
		end
	end
	grid("SpeedGrid", C.ShopSpeedRows, "SpeedCard")
	grid("MoneyGrid", C.ShopMoneyRows, "MoneyCard")
	-- passes
	for key, pass in C.Passes do
		local card = scroll:FindFirstChild("Pass_" .. key, true)
		local btn = card and find(card, "PriceRow.Button")
		if btn then
			setText(text(btn), tostring(pass.Price))
			hookButton(btn, function()
				buy(key)
			end)
		end
		hookButton(card and find(card, "PriceRow.GiftButton"), function()
			toast("Error", "Gifting is coming soon!", "Gift")
		end, false)
	end
	-- treadmill upgrade banner
	local up = scroll:FindFirstChild("UpgradeBanner")
	if up then
		local btn = find(up, "Content.Frame.Button")
		hookButton(btn, function()
			buy("Treadmill")
		end)
		hookButton(find(up, "Content.Frame.GiftButton"), function()
			toast("Error", "Gifting is coming soon!", "Gift")
		end, false)
	end
	-- featured egg banner: the zone's real eggs / animals / chances
	local feat = scroll:FindFirstChild("FeaturedBanner")
	if feat then
		local zone = C.Featured.Zone
		local z = DD.ZoneEggs[zone]
		for _, c in feat:GetDescendants() do
			if c:IsA("GuiButton") and c:GetAttribute("Product") then
				local key = c:GetAttribute("Product")
				local gift = c:GetAttribute("Gift")
				if gift then
					hookButton(c, function()
						toast("Error", "Gifting is coming soon!", "Gift")
					end, false)
				elseif c.Name == "PriceButton" then
					local p = C.Products[key]
					setText(text(c), p and commas(p.Price) or "")
					hookButton(c, function()
						buy(key)
					end)
				end
			end
		end
		local title = feat:FindFirstChild("Title")
		setText(title, C.Featured.Title)
		local timer = feat:FindFirstChild("Timer")
		if timer then
			timer.Visible = C.Featured.EndsAt ~= nil
			local tl = text(timer)
			if C.Featured.EndsAt and tl then
				task.spawn(function()
					while timer.Parent do
						local secs = math.max(0, C.Featured.EndsAt - os.time())
						tl.Text = ("%dd %02dh %02dm %02ds"):format(secs // 86400, secs % 86400 // 3600, secs % 3600 // 60, secs % 60)
						task.wait(1)
					end
				end)
			end
		end
		setText(feat:FindFirstChild("Subtitle"), C.Featured.EndsAt and "Limited Time!" or "Random eggs")
		local eggIcon = feat:FindFirstChild("Icon/EggLava")
		if z and eggIcon then
			local best = z.Eggs[#z.Eggs]
			showEgg(eggIcon, zone, best.Id)
		end
		-- odds: most common first, the rarest in the big secret tile
		if z then
			local totalW = 0
			for _, e in z.Eggs do
				totalW += e.Weight
			end
			local odds = {}
			for _, e in z.Eggs do
				local aw = 0
				for _, a in e.Animals do
					aw += a.Weight
				end
				for _, a in e.Animals do
					table.insert(odds, { A = a, P = e.Weight / totalW * a.Weight / aw * 100 })
				end
			end
			table.sort(odds, function(a, b)
				return a.P > b.P
			end)
			local function fmtP(p)
				if p >= 10 then
					return ("%d%%"):format(math.floor(p + 0.5))
				elseif p >= 1 then
					return (("%.1f"):format(p):gsub("%.0$", "")) .. "%"
				end
				return (("%.2f"):format(p):gsub("0+$", "")) .. "%"
			end
			local oddsFrame = feat:FindFirstChild("Odds")
			local slots = oddsFrame and kids(oddsFrame) or {}
			local rarest = odds[#odds]
			for i, slot in slots do
				local o = (i == #slots) and rarest or (i < #odds and odds[i] or nil)
				if o then
					showAnimal(iconIn(slot), zone, o.A.Id, 35)
					local labels = {}
					for _, d in slot:GetDescendants() do
						if d:IsA("TextLabel") then
							table.insert(labels, d)
						end
					end
					for _, l in labels do
						if l.Text:find("%%") then
							l.Text = fmtP(o.P)
						elseif i == #slots then
							l.Text = string.upper(o.A.Rarity)
						end
					end
				else
					slot.Visible = false
				end
			end
			-- a regular odds card that runs under the SECRET card would have its % cut off
			local secret = slots[#slots]
			for i = 1, #slots - 1 do
				local s = slots[i]
				if secret and s.Position.X.Offset + s.Size.X.Offset > secret.Position.X.Offset + 4 then
					s.Visible = false
				end
			end
		end
	end
end
local function renderShop()
	if not (shopWin and state) then
		return
	end
	local scroll = find(shopWin, "Window.Body.Scroll")
	local up = scroll and scroll:FindFirstChild("UpgradeBanner")
	if up then
		local t = state.Treadmill or {}
		local mult = find(up, "Content.Multiplier")
		local l = mult and texts(mult)
		if l and l[1] then
			l[1].Text = "+" .. short(t.Gain or 0)
			l[1].TextScaled = true
		end
		if l and l[2] then
			l[2].Text = t.NextGain and ("+" .. short(t.NextGain)) or "MAX"
			l[2].TextScaled = true
		end
		local btn = find(up, "Content.Frame.Button")
		setText(btn and text(btn), t.NextGain and tostring(t.RobuxPrice or "") or "MAX")
	end
	for key in C.Passes do
		local card = scroll:FindFirstChild("Pass_" .. key, true)
		local btn = card and find(card, "PriceRow.Button")
		if btn and state.Passes and state.Passes[key] then
			setText(text(btn), "OWNED")
			local ic = iconIn(btn)
			if ic then
				ic.Visible = false
			end
		end
	end
end

---------------------------------------------------------------- Settings
local settingsWin = G("SettingsWindow")
local settings = {}
for k, v in C.SettingDefaults do
	settings[k] = v
end
local settingRows = {}
local function applySettings()
	player:SetAttribute("MusicOff", settings.Music == false or nil)
	sfxGroup.Volume = settings.SoundEffects == false and 0 or 1
	uiGroup.Volume = settings.SoundEffects == false and 0 or 1
	-- other players' pets
	for _, m in CollectionService:GetTagged("DDPlotAnimal") do
		local mine = m:GetAttribute("DDOwner") == player.UserId
		local hide = settings.ShowOtherPets == false and not mine
		for _, d in m:GetDescendants() do
			if d:IsA("BasePart") then
				d.LocalTransparencyModifier = hide and 1 or 0
			elseif d:IsA("BillboardGui") then
				d.Enabled = not hide
			end
		end
	end
	-- low graphics: no shadows / particles
	local low = settings.LowGraphics == true
	Lighting.GlobalShadows = not low
	for _, d in workspace:GetDescendants() do
		if d:IsA("ParticleEmitter") or d:IsA("Smoke") or d:IsA("Fire") or d:IsA("Sparkles") then
			if low then
				if d:GetAttribute("WasEnabled") == nil then
					d:SetAttribute("WasEnabled", d.Enabled)
				end
				d.Enabled = false
			elseif d:GetAttribute("WasEnabled") ~= nil then
				d.Enabled = d:GetAttribute("WasEnabled")
				d:SetAttribute("WasEnabled", nil)
			end
		end
	end
end
CollectionService:GetInstanceAddedSignal("DDPlotAnimal"):Connect(function()
	if settings.ShowOtherPets == false then
		task.delay(0.5, applySettings)
	end
end)
-- every non-music sound goes through the SFX group so the Sound Effects toggle mutes it
local function routeSound(s)
	if s:IsA("Sound") and not s.SoundGroup and not s.Name:find("^Music") and s.Name ~= "DD_ChaseMusic" then
		s.SoundGroup = sfxGroup
	end
end
for _, root in { workspace, SoundService, playerGui } do
	root.DescendantAdded:Connect(routeSound)
	for _, d in root:GetDescendants() do
		routeSound(d)
	end
end

local function toggleVisual(row, on)
	local toggle
	for _, c in row:GetChildren() do
		if c.Name:find("^Toggle") then
			toggle = c
		end
	end
	if not toggle then
		return
	end
	local knob = toggle:FindFirstChild("Knob")
	local label = text(toggle)
	local onX = 96
	local offX = 8
	if knob then
		tween(knob, 0.15, { Position = UDim2.fromOffset(on and onX or offX, knob.Position.Y.Offset) })
	end
	if label then
		label.Text = on and "ON" or "OFF"
		tween(label, 0.15, { Position = UDim2.fromOffset(on and 22 or 66, label.Position.Y.Offset) })
	end
	local g = toggle:FindFirstChildOfClass("UIGradient")
	toggle.BackgroundColor3 = on and Color3.new(1, 1, 1) or Color3.fromRGB(215, 40, 40)
	if g then
		g.Enabled = on
	end
end
if settingsWin then
	for _, d in settingsWin:GetDescendants() do
		local key = d.Name:match("^Setting/(.+)$")
		if key then
			settingRows[key] = d
			hookButton(d, function()
				if key == "SlowMode" then
					local on = not player:GetAttribute("SlowMode")
					SeedRemotes.SetSlowMode:FireServer(on)
					toggleVisual(d, on)
					play(on and "ToggleOn" or "ToggleOff")
					return
				end
				settings[key] = not settings[key]
				toggleVisual(d, settings[key])
				play(settings[key] and "ToggleOn" or "ToggleOff")
				Remote:FireServer("SetSetting", { Key = key, Value = settings[key] })
				applySettings()
			end, false)
		end
	end
	player:GetAttributeChangedSignal("SlowMode"):Connect(function()
		if settingRows.SlowMode then
			toggleVisual(settingRows.SlowMode, player:GetAttribute("SlowMode") == true)
		end
	end)
end
local function renderSettings()
	for key, row in settingRows do
		if key == "SlowMode" then
			toggleVisual(row, player:GetAttribute("SlowMode") == true)
		else
			toggleVisual(row, settings[key] ~= false)
		end
	end
end
onOpen.SettingsWindow = renderSettings

---------------------------------------------------------------- Sell
local sellWin = G("SellWindow")
local sellTab = "Pets"
local sellSort = "Value"
local selected = {} -- [id] = true
local sellCards = {}
local function sellItems()
	local list = {}
	if not state then
		return list
	end
	if sellTab == "Pets" then
		for _, a in allOwned() do
			table.insert(list, {
				Id = a.Id, Kind = "Pet", Name = a.Animal, Rarity = a.Rarity, Zone = a.Zone, AnimalId = a.AnimalId,
				Income = a.Income, Value = math.floor(a.Income * C.Sell.AnimalSeconds), Placed = a.Placed,
			})
		end
	else
		for _, e in (state.Extra and state.Extra.HandEggs) or {} do
			local egg = DD.zoneEgg(e.Zone, e.EggId)
			local total, w = 0, 0
			for _, a in egg and egg.Animals or {} do
				total += a.IncomePerSecond * (a.Weight or 1)
				w += a.Weight or 1
			end
			table.insert(list, {
				Id = e.Id, Kind = "Egg", Name = e.Name, Rarity = e.Rarity, Zone = e.Zone, EggId = e.EggId,
				Value = math.floor(total / math.max(w, 1) * C.Sell.EggSeconds),
			})
		end
	end
	table.sort(list, function(a, b)
		if sellSort == "Rarity" then
			local ra, rb = RARITY_RANK[a.Rarity] or 0, RARITY_RANK[b.Rarity] or 0
			if ra ~= rb then
				return ra > rb
			end
		end
		return a.Value > b.Value
	end)
	return list
end
local function sellTotal(list)
	local total, n = 0, 0
	for _, it in list do
		if selected[it.Id] then
			total += it.Value
			n += 1
		end
	end
	return total, n
end
local function renderSell()
	if not (sellWin and state) then
		return
	end
	local body = find(sellWin, "Window.Body")
	local grid = find(body, "Content.PetGrid")
	local list = sellItems()
	local present = {}
	for _, it in list do
		present[it.Id] = true
	end
	for id in selected do
		if not present[id] then
			selected[id] = nil
		end
	end
	for _, c in sellCards do
		c:Destroy()
	end
	sellCards = {}
	for i, it in list do
		local card = T.SellCard:Clone()
		card.Name = "Sell_" .. it.Id
		card.Visible = true
		card.LayoutOrder = i
		card.Parent = grid
		table.insert(sellCards, card)
		local l = texts(card)
		-- (weight) -> name, "$x/s", value
		setText(l[1], it.Name)
		if l[1] then
			l[1].TextColor3 = rarityColor(it.Rarity)
		end
		setText(l[2], it.Kind == "Pet" and (money(it.Income) .. "/s") or it.Rarity)
		local valueFrame = card:FindFirstChild("SellValue")
		setText(valueFrame and text(valueFrame), money(it.Value))
		local glow = card:FindFirstChild("RarityGlow")
		if glow then
			glow.BackgroundColor3 = rarityColor(it.Rarity)
		end
		local art
		for _, c in card:GetChildren() do
			if c:IsA("ImageLabel") and c.Name:match("^Icon/Pet") then
				art = c
			end
		end
		if it.Kind == "Pet" then
			showAnimal(art, it.Zone, it.AnimalId, 30)
		else
			showEgg(art, it.Zone, it.EggId)
		end
		local check = card:FindFirstChild("Icon/Check")
		if check then
			check.Visible = selected[it.Id] == true
		end
		local st = card:FindFirstChildOfClass("UIStroke")
		if st then
			st.Color = selected[it.Id] and Color3.fromRGB(120, 255, 90) or Color3.fromRGB(14, 14, 16)
		end
		local id = it.Id
		hookButton(card, function()
			selected[id] = not selected[id] or nil
			renderSell()
		end, "Select")
	end
	local total, n = sellTotal(list)
	local bar = find(body, "Content.TotalBar")
	if bar then
		local l = texts(bar)
		setText(l[2], money(total))
		local sb = bar:FindFirstChild("SellButton")
		setText(sb and text(sb), n > 0 and ("SELL (%d)"):format(n) or "SELL")
	end
	local clear = find(body, "SortPanel.ClearButton")
	setText(clear and text(clear), next(selected) and "Clear" or "Select All")
	-- sort / tab highlights
	for _, d in body.SortPanel:GetChildren() do
		local key = d.Name:match("^Sort/(.+)$")
		if key then
			local on = (key == "Weight" and sellSort == "Rarity") or (key == "Value" and sellSort == "Value")
			local st = d:FindFirstChildOfClass("UIStroke")
			if st then
				st.Color = on and Color3.fromRGB(255, 225, 77) or Color3.fromRGB(14, 14, 16)
			end
		end
	end
	for _, d in sellWin.Side:GetChildren() do
		local key = d.Name:match("^Tab/(.+)$")
		if key then
			local on = key == sellTab
			d.BackgroundTransparency = 1
			tween(scaleOf(d, "SelScale"), 0.15, { Scale = on and 1.12 or 0.95 })
			for _, c in d:GetDescendants() do
				if c:IsA("ImageLabel") then
					c.ImageTransparency = on and 0 or 0.4
				elseif c:IsA("TextLabel") then
					c.TextTransparency = on and 0 or 0.4
				end
			end
		end
	end
	emptyNote(grid, #list == 0, sellTab == "Eggs" and "No eggs to sell yet!\nGrab some eggs first." or "No pets to sell yet!\nHatch some eggs first.")
end
onOpen.SellWindow = function()
	selected = {}
	renderSell()
end
local confirmModal = G("ConfirmModal")
local pendingSell = nil
if sellWin then
	local body = find(sellWin, "Window.Body")
	local weight = find(body, "SortPanel.Sort/Weight")
	if weight then
		setText(text(weight), "Rarity")
		hookButton(weight, function()
			sellSort = "Rarity"
			renderSell()
		end, "Tab")
	end
	hookButton(find(body, "SortPanel.Sort/Value"), function()
		sellSort = "Value"
		renderSell()
	end, "Tab")
	hookButton(find(body, "SortPanel.ClearButton"), function()
		if next(selected) then
			selected = {}
		else
			for _, it in sellItems() do
				if not it.Placed then
					selected[it.Id] = true
				end
			end
		end
		renderSell()
	end)
	for _, d in sellWin.Side:GetChildren() do
		local key = d.Name:match("^Tab/(.+)$")
		if key then
			hookButton(d, function()
				sellTab = key
				selected = {}
				renderSell()
			end, "Tab")
		end
	end
	hookButton(find(body, "Content.TotalBar.SellButton"), function(b)
		local list = sellItems()
		local total, n = sellTotal(list)
		if n == 0 then
			shake(b)
			toast("Error", "Pick something to sell first!", "Lock")
			return
		end
		pendingSell = {}
		local chosen = {}
		for _, it in list do
			if selected[it.Id] then
				table.insert(pendingSell, { Kind = it.Kind, Id = it.Id })
				table.insert(chosen, it)
			end
		end
		if confirmModal then
			local mb = find(confirmModal, "Window.Body")
			local q = text(mb)
			if q then
				q.RichText = true
				q.Text = ('Would you like to sell %d %s for <font color="#8cff5e">%s</font>?'):format(n, sellTab == "Pets" and (n == 1 and "pet" or "pets") or (n == 1 and "egg" or "eggs"), money(total))
			end
			local strip = mb:FindFirstChild("PetsBeingSold")
			if strip then
				local frames = kids(strip)
				for i, f in frames do
					local it = chosen[i]
					f.Visible = it ~= nil
					if it then
						if it.Kind == "Pet" then
							showAnimal(iconIn(f), it.Zone, it.AnimalId, 30)
						else
							showEgg(iconIn(f), it.Zone, it.EggId)
						end
					end
				end
			end
			setModal(confirmModal)
		end
	end, "Click")
end
if confirmModal then
	hookButton(find(confirmModal, "Window.Body.Buttons.YesButton"), function()
		if pendingSell then
			Remote:FireServer("Sell", pendingSell)
			pendingSell = nil
			selected = {}
		end
		setModal(nil)
	end, "Sell")
	hookButton(find(confirmModal, "Window.Body.Buttons.NoButton"), function()
		pendingSell = nil
		setModal(nil)
	end, "Close")
end

---------------------------------------------------------------- Trail Shop
local trailWin = G("TrailShopWindow")
local trailCards = {}
local buttonStyles = {}
local lockedTpl, tipTpl = T:FindFirstChild("LockedOverlay"), T:FindFirstChild("Tooltip")
if trailWin then
	local list = find(trailWin, "Window.Body.Content.TrailList")
	for _, c in list:GetChildren() do
		local id = c:GetAttribute("Trail")
		if id then
			trailCards[id] = c
			local b = c:FindFirstChild("Buttons")
			if b then
				for _, s in b:GetChildren() do
					if s.Name == "Button/Equip" and not buttonStyles.Equip then
						buttonStyles.Equip = s:Clone()
					elseif s.Name == "Button/Unequip" and not buttonStyles.Unequip then
						buttonStyles.Unequip = s:Clone()
					elseif s.Name:match("^Button/%$") and not buttonStyles.Cash then
						buttonStyles.Cash = s:Clone()
					elseif s.Name == "RobuxPrice" and not buttonStyles.Robux then
						buttonStyles.Robux = s:Clone()
					end
				end
			end
			local eq = c:FindFirstChild("EQUIPPED")
			if eq and not buttonStyles.EquippedLabel then
				buttonStyles.EquippedLabel = eq:Clone()
			end
			if eq then
				eq:Destroy()
			end
		end
	end
end
local trailById = {}
for _, t in C.Trails do
	trailById[t.Id] = t
end
local function renderTrails()
	if not (trailWin and state and state.Extra) then
		return
	end
	local tr = state.Extra.Trails
	local cash = leaderstats.Cash.Value
	for id, card in trailCards do
		local t = trailById[id]
		if not t then
			card.Visible = false
			continue
		end
		local l = texts(card)
		setText(l[1], t.Name)
		setText(l[2], t.Rarity)
		local mult = card:FindFirstChild("SpeedMultiplier")
		setText(mult and text(mult), ("x%s Speed"):format(tostring(t.Mult)))
		local owned = tr.Owned and tr.Owned[id]
		local equipped = tr.Equipped == id
		local unlocked = tr.Unlocked == nil or tr.Unlocked[id] ~= false
		local key = ("%s|%s|%s|%s|%s"):format(tostring(owned), tostring(equipped), tostring(unlocked), tostring(cash >= t.Cash), tostring(t.Cash))
		if card:GetAttribute("StateKey") == key then
			continue
		end
		card:SetAttribute("StateKey", key)
		local buttons = card:FindFirstChild("Buttons")
		for _, c in buttons:GetChildren() do
			if c:IsA("GuiObject") then
				c:Destroy()
			end
		end
		local ov = card:FindFirstChild("LockedOverlay")
		if ov then
			ov:Destroy()
		end
		local eqLabel = card:FindFirstChild("EquippedLabel")
		if eqLabel then
			eqLabel:Destroy()
		end
		local st = card:FindFirstChildOfClass("UIStroke")
		if st then
			st.Color = equipped and Color3.new(1, 1, 1) or Color3.fromRGB(14, 14, 16)
			st.Thickness = equipped and 6 or 4
		end
		if equipped and buttonStyles.EquippedLabel then
			local e = buttonStyles.EquippedLabel:Clone()
			e.Name = "EquippedLabel"
			e.ZIndex = 40
			e.Parent = card
			pop(e, 1.3)
		end
		if owned then
			local b = (equipped and buttonStyles.Unequip or buttonStyles.Equip):Clone()
			b.Position = UDim2.new()
			b.Parent = buttons
			hookButton(b, function()
				Remote:FireServer("EquipTrail", equipped and false or id)
			end, "Equip")
		else
			local cb = buttonStyles.Cash:Clone()
			cb.Name = "Button/Cash"
			cb.Position = UDim2.new()
			cb.Parent = buttons
			local cl = text(cb)
			if cl then
				cl.Text = t.Cash > 0 and money(t.Cash) or "FREE"
				cl.Position = UDim2.fromOffset(2, cl.Position.Y.Offset)
				cl.Size = UDim2.fromOffset(100, cl.Size.Y.Offset)
				cl.TextXAlignment = Enum.TextXAlignment.Center
				cl.TextScaled = #cl.Text > 5
			end
			local affordable = cash >= t.Cash
			if not affordable then
				-- "Not enough cash": red, dimmed price
				local g = cb:FindFirstChildOfClass("UIGradient")
				if g then
					g.Enabled = false
				end
				cb.BackgroundColor3 = Color3.fromRGB(200, 40, 40)
			end
			hookButton(cb, function()
				if not unlocked then
					shake(card)
					toast("Error", ("Reach Zone %d to unlock!"):format(t.Zone), "Lock")
					return
				end
				if leaderstats.Cash.Value < t.Cash then
					shake(cb)
					if tipTpl then
						local tip = tipTpl:Clone()
						tip.Visible = true
						setText(text(tip), ("Need %s more!"):format(money(t.Cash - leaderstats.Cash.Value)))
						tip.AnchorPoint = Vector2.new(0.5, 1)
						tip.Position = UDim2.new(0.5, 0, 0, buttons.Position.Y.Offset - 8)
						tip.ZIndex = 60
						tip.Parent = card
						pop(tip, 0.7)
						task.delay(2, function()
							tip:Destroy()
						end)
					end
					play("Error")
					return
				end
				Remote:FireServer("BuyTrail", id)
			end)
			local rb = buttonStyles.Robux:Clone()
			rb.Position = UDim2.fromOffset(110, 0)
			rb.Parent = buttons
			setText(text(rb), tostring(t.Robux or ""))
			rb.Visible = t.Robux ~= nil
			hookButton(rb, function()
				Remote:FireServer("BuyTrailRobux", id)
			end)
			if not unlocked and lockedTpl then
				local o = lockedTpl:Clone()
				o.Visible = true
				o.ZIndex = 45
				o.Parent = card
				for _, d in o:GetDescendants() do
					if d:IsA("TextLabel") and d.Text:find("Reach") then
						d.Text = ("Reach Zone %d to unlock"):format(t.Zone)
					end
				end
			end
		end
	end
end
onOpen.TrailShopWindow = renderTrails
leaderstats:WaitForChild("Cash").Changed:Connect(function()
	if trailWin and trailWin.Visible then
		renderTrails()
	end
end)

---------------------------------------------------------------- Free Gift
local giftWin = G("FreeGiftWindow")
local function renderGift()
	if not (giftWin and state and state.Extra) then
		return
	end
	local g = state.Extra.FreeGift
	local steps = find(giftWin, "Window.Body.Steps")
	for i, key in { "Like", "Favorite", "Group" } do
		local step = steps and steps:FindFirstChild("Step" .. i)
		local status = step and step:FindFirstChild("Status")
		if status then
			local done = g[key]
			local check = status:FindFirstChild("Icon/Check")
			local l = text(status)
			if check then
				check.Visible = done
			end
			if l then
				l.Text = done and "Done!" or "Tap to do it!"
				l.TextColor3 = done and Color3.fromRGB(155, 247, 102) or Color3.fromRGB(255, 225, 77)
			end
		end
	end
	local claim = find(giftWin, "Window.Body.ClaimButton")
	setText(claim and text(claim), g.Claimed and "CLAIMED" or "CLAIM!")
	local offer = find(giftWin, "Window.Body.Hero.Offer")
	local ol = offer and texts(offer)
	if ol and ol[2] then
		ol[2].Text = short(C.FreeGift.Speed) .. " SPEED!"
	end
end
onOpen.FreeGiftWindow = renderGift
if giftWin then
	local steps = find(giftWin, "Window.Body.Steps")
	local function step(i, fn)
		local s = steps and steps:FindFirstChild("Step" .. i)
		hookButton(s, fn)
	end
	step(1, function()
		-- no API can check a like: trust the tap
		Remote:FireServer("GiftStep", "Like")
		toast("Speed", "Thanks for the like!", "ThumbsUp")
	end)
	step(2, function()
		local ok = pcall(function()
			game:GetService("AvatarEditorService"):PromptSetFavorite(game.PlaceId, Enum.AvatarItemType.Asset, true)
		end)
		if not ok then
			Remote:FireServer("GiftStep", "Favorite")
		end
	end)
	pcall(function()
		game:GetService("AvatarEditorService").PromptSetFavoriteCompleted:Connect(function(result)
			if result == Enum.AvatarPromptResult.Success then
				Remote:FireServer("GiftStep", "Favorite")
			end
		end)
	end)
	step(3, function()
		task.spawn(function()
			pcall(function()
				game:GetService("GroupService"):PromptJoinAsync(C.FreeGift.GroupId)
			end)
			task.wait(0.5)
			Remote:FireServer("GiftStep", "Group")
		end)
	end)
	hookButton(find(giftWin, "Window.Body.ClaimButton"), function(b)
		local g = state and state.Extra and state.Extra.FreeGift
		if g and g.Claimed then
			shake(b)
			return
		end
		Remote:FireServer("ClaimGift")
	end)
end

---------------------------------------------------------------- Hatch reveal (V2 16)
local reveal = G("HatchReveal")
local revealDim = gui:FindFirstChild("HatchDim")
local revealQueue = {}
local revealing = false
local revealItem = nil
local showReveal
local function closeReveal()
	if not reveal then
		return
	end
	local s = scaleOf(reveal, "OpenScale")
	tween(s, 0.2, { Scale = 0.6 }, Enum.EasingStyle.Back, Enum.EasingDirection.In).Completed:Connect(function()
		reveal.Visible = false
		if revealDim then
			revealDim.Visible = false
		end
		revealing = false
		if #revealQueue > 0 then
			local nxt = table.remove(revealQueue, 1)
			task.defer(function()
				showReveal(nxt)
			end)
		end
	end)
end
showReveal = function(info)
	if not reveal then
		return
	end
	if revealing then
		table.insert(revealQueue, info)
		return
	end
	revealing = true
	revealItem = info.ItemId
	local color = rarityColor(info.Rarity)
	local glow = reveal:FindFirstChild("RarityGlow")
	if glow then
		-- soft radial glow: stacked translucent discs (Figma's radial gradient has no UIGradient equivalent)
		glow.BackgroundTransparency = 1
		for _, c in glow:GetChildren() do
			if c:IsA("UIGradient") or c:IsA("UIStroke") then
				c.Enabled = false
			end
		end
		if not glow:FindFirstChild("Soft1") then
			for i = 1, 8 do
				local d = Instance.new("Frame")
				d.Name = "Soft" .. i
				d.AnchorPoint = Vector2.new(0.5, 0.5)
				d.Position = UDim2.fromScale(0.5, 0.5)
				local k = 1 - (i - 1) * 0.11
				d.Size = UDim2.fromScale(k, k)
				d.BackgroundTransparency = 0.88
				d.BorderSizePixel = 0
				d.ZIndex = glow.ZIndex
				local corner = Instance.new("UICorner")
				corner.CornerRadius = UDim.new(1, 0)
				corner.Parent = d
				d.Parent = glow
			end
		end
		for i = 1, 8 do
			local d = glow:FindFirstChild("Soft" .. i)
			if d then
				d.BackgroundColor3 = color:Lerp(Color3.new(1, 1, 1), (i - 1) / 14)
			end
		end
	end
	setText(reveal:FindFirstChild("PetName"), string.upper(info.Animal))
	local ribbon = reveal:FindFirstChild("RarityRibbon")
	if ribbon then
		setText(text(ribbon), string.upper(info.Rarity))
		ribbon.BackgroundColor3 = color
	end
	local stats = reveal:FindFirstChild("Stats")
	if stats then
		local f = stats:FindFirstChild("Frame")
		setText(f and text(f), "$" .. commas(info.Income) .. "/s")
		local l = texts(stats)
		if l[1] then
			l[1].Text = "(" .. (C.ZoneNames[info.Zone] or info.Zone) .. ")"
		end
	end
	local newText = reveal:FindFirstChild("NewText")
	local burst = reveal:FindFirstChild("NewBurst")
	if newText then
		newText.Visible = info.New == true
	end
	if burst then
		burst.Visible = info.New == true
	end
	local art = reveal:FindFirstChild("PetArt")
	if art then
		local vp = viewportOver(art)
		if vp then
			vp:SetAttribute("Showing", nil)
			setPreview(vp, animalPreview(info.Zone, info.AnimalId), 20)
		end
	end
	local equipB = find(reveal, "Buttons.EquipButton")
	if equipB then
		equipB.Visible = info.ItemId ~= nil
	end
	if revealDim then
		revealDim.Visible = true
		revealDim.BackgroundTransparency = 1
		tween(revealDim, 0.25, { BackgroundTransparency = 0.35 })
	end
	reveal.Visible = true
	local s = scaleOf(reveal, "OpenScale")
	s.Scale = 0.3
	tween(s, 0.45, { Scale = 1 }, Enum.EasingStyle.Back)
	-- confetti burst outwards
	for _, c in reveal:GetChildren() do
		if c.Name == "Confetti" then
			local home = c:GetAttribute("Home") or c.Position
			c:SetAttribute("Home", home)
			c.Position = UDim2.fromOffset(960, 540)
			c.Rotation = rng:NextNumber(-180, 180)
			tween(c, 0.7, { Position = home, Rotation = rng:NextNumber(-40, 40) }, Enum.EasingStyle.Back)
		end
	end
	if art then
		pop(art.Parent:FindFirstChild(art.Name .. "_VP"), 0.4)
	end
	play("Hatch")
end
if reveal then
	-- the rays rotate slowly while it's up; the NEW! burst pulses
	local rays = reveal:FindFirstChild("Rays")
	local burst = reveal:FindFirstChild("NewBurst")
	local shine = reveal:FindFirstChild("Art/Shine")
	RunService.RenderStepped:Connect(function(dt)
		if reveal.Visible then
			if rays then
				rays.Rotation = (rays.Rotation + dt * 12) % 360
			end
			if shine then
				shine.Rotation = (shine.Rotation - dt * 20) % 360
			end
			if burst then
				local s = 1 + math.sin(os.clock() * 6) * 0.06
				scaleOf(burst, "Pulse").Scale = s
			end
		end
	end)
	hookButton(find(reveal, "Buttons.OkButton"), function()
		closeReveal()
	end)
	hookButton(find(reveal, "Buttons.EquipButton"), function()
		if revealItem then
			Remote:FireServer("EquipItem", revealItem)
		end
		closeReveal()
	end, "Equip")
end

---------------------------------------------------------------- Rays / shines spin everywhere (shop cards, gift)
task.spawn(function()
	local spinners = {}
	for _, d in gui:GetDescendants() do
		if (d.Name == "Shine" or d.Name == "Art/Shine" or d.Name == "Rays") and d:IsA("GuiObject") and not d:IsDescendantOf(reveal) then
			table.insert(spinners, d)
		end
	end
	RunService.RenderStepped:Connect(function(dt)
		for i, d in spinners do
			if d.Visible then
				d.Rotation = (d.Rotation + dt * (i % 2 == 0 and 10 or -8)) % 360
			end
		end
	end)
end)

---------------------------------------------------------------- server messages
local function renderAll()
	if state and state.Extra and state.Extra.Settings then
		local changed = false
		for k, v in state.Extra.Settings do
			if settings[k] ~= v then
				settings[k] = v
				changed = true
			end
		end
		if changed or not player:GetAttribute("SettingsApplied") then
			player:SetAttribute("SettingsApplied", true)
			applySettings()
		end
	end
	renderPets()
	renderEggPanel()
	if growWin and growWin.Visible then
		renderGrowWindow()
	end
	if petsWin and petsWin.Visible then
		renderInventory()
	end
	if indexWin and indexWin.Visible then
		renderIndex()
	end
	renderShop()
	if sellWin and sellWin.Visible then
		renderSell()
	end
	if trailWin and trailWin.Visible then
		renderTrails()
	end
	if giftWin and giftWin.Visible then
		renderGift()
	end
	if settingsWin and settingsWin.Visible then
		renderSettings()
	end
	-- red badge on the gift button while the gift is unclaimed
	local gb = rightBody and rightBody:FindFirstChild("Right/Rewards")
	if gb and state and state.Extra then
		local dot = gb:FindFirstChild("GiftDot")
		local want = not state.Extra.FreeGift.Claimed
		if want and not dot then
			dot = Instance.new("Frame")
			dot.Name = "GiftDot"
			dot.Size = UDim2.fromOffset(24, 24)
			dot.Position = UDim2.fromOffset(66, -6)
			dot.BackgroundColor3 = Color3.fromRGB(255, 60, 60)
			local c = Instance.new("UICorner")
			c.CornerRadius = UDim.new(0.5, 0)
			c.Parent = dot
			local s = Instance.new("UIStroke")
			s.Thickness = 3
			s.Color = Color3.fromRGB(14, 14, 16)
			s.Parent = dot
			dot.ZIndex = 20
			dot.Parent = gb
		elseif dot and not want then
			dot:Destroy()
		end
	end
end

Remote.OnClientEvent:Connect(function(kind, a, b)
	if kind == "State" then
		state = a
		renderAll()
	elseif kind == "Discovered" then
		play("Discover")
	elseif kind == "Hatched" then
		if type(a) == "table" then
			if settings.HatchAnimation ~= false then
				showReveal(a)
			else
				toast("Hatched", ("Hatched a %s %s!"):format(a.Rarity, a.Animal), nil, a.Zone, a.AnimalId)
			end
		end
	elseif kind == "Claimed" then
		play("Claim")
		showClaimed(a)
	elseif kind == "Purchased" then
		play("Purchase")
		local p = C.Products[a]
		if p and p.Kind == "Speed" then
			toast("Speed", ("+%s Speed!"):format(commas(p.Amount)), "ShoeWinged")
		elseif p and p.Kind == "Cash" then
			toast("Speed", ("+%s Cash!"):format(money(p.Amount)), "Cash")
		elseif C.Passes[a] then
			toast("Speed", C.Passes[a].Title .. " unlocked!", "Crown")
		else
			toast("Speed", "Purchase complete!", "Star")
		end
	elseif kind == "TrailBought" or kind == "TrailEquipped" then
		local t = trailById[a]
		if t then
			toast("TrailEquipped", t.Name .. " equipped!", t.Art)
			play("Equip")
		elseif kind == "TrailEquipped" then
			toast("TrailEquipped", "Trail unequipped", "Shoe")
		end
		if trailWin then
			for _, c in trailCards do
				c:SetAttribute("StateKey", nil)
			end
		end
	elseif kind == "NotEnough" then
		toast("Error", ("Not enough cash! Need %s more"):format(money(a)), "Lock")
	elseif kind == "Sold" then
		play("Sell")
		toast("Speed", ("Sold %d for %s!"):format(a, money(b)), "CashPile")
	elseif kind == "GiftClaimed" then
		play("Claim")
		toast("Speed", ("+%s Speed!"):format(commas(a)), "ShoeWinged")
	elseif kind == "Error" then
		if a == "GiftSteps" then
			toast("Error", "Finish all 3 steps first!", "Lock")
		elseif a == "Locked" then
			toast("Error", "That trail is still locked!", "Lock")
		end
	end
end)
Remote:FireServer("Request")
Previews.DescendantAdded:Connect(function()
	if indexWin and indexWin.Visible then
		task.defer(renderIndex)
	end
end)
task.delay(3, renderAll)

---------------------------------------------------------------- open windows from the world (booth sellers etc.)
-- any ProximityPrompt with an OpenUI attribute ("TrailShopWindow", "SellWindow", ...) opens that window
ProximityPromptService.PromptTriggered:Connect(function(prompt)
	local name = prompt:GetAttribute("OpenUI")
	if name then
		openByName(name)
	end
end)
local openEvent = Shared:FindFirstChild("OpenWindow")
if openEvent and openEvent:IsA("BindableEvent") then
	openEvent.Event:Connect(openByName)
end

-- Escape / gamepad B closes whatever is open
UserInputService.InputBegan:Connect(function(input, processed)
	if input.KeyCode == Enum.KeyCode.ButtonB or (input.KeyCode == Enum.KeyCode.Escape and not processed) then
		if reveal and reveal.Visible then
			closeReveal()
		elseif openModal then
			setModal(nil)
		elseif openWindow then
			setWindow(nil)
		end
	end
end)
