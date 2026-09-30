-- Server side of the V2 UI features that didn't exist in the game yet: Trails (buy with Cash / Robux, equip, a Speed
-- multiplier on treadmill gains + a trail on your character), Selling pets / eggs for Cash, saved Settings, and the
-- Free Gift (like / favourite / join the group -> one-time Speed reward). UIService merges these actions into its
-- remote handler and adds snapshot() to the State it sends. Nothing here trusts the client: prices, values, locks
-- and ownership are all looked up on the server.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")
local MarketplaceService = game:GetService("MarketplaceService")

local Shared = ReplicatedStorage:WaitForChild("GameUI")
local C = require(Shared:WaitForChild("Config"))
local Remote = Shared:WaitForChild("Remote")
local DD = require(ReplicatedStorage:WaitForChild("DingDong"):WaitForChild("Config"))
local SeedShared = ReplicatedStorage:WaitForChild("ForestSeedSystem")
local SeedConfig = require(SeedShared:WaitForChild("Config"))
local SeedRemotes = SeedShared:WaitForChild("Remotes")
local PlantService = require(ServerScriptService:WaitForChild("ForestSeedSystem"):WaitForChild("PlantService"))
local ZoneEggService = require(ServerScriptService:WaitForChild("DingDong"):WaitForChild("ZoneEggService"))
local Router = require(script.Parent:WaitForChild("ReceiptRouter"))

local X = { actions = {} }

local function notify(player, text, kind)
	if player.Parent then
		SeedRemotes.Notify:FireClient(player, text, kind)
	end
end

local function profileOf(player)
	local p = PlantService.getProfile(player)
	return p and p.Loaded and p or nil
end

local function speedOf(player)
	local ls = player:FindFirstChild("leaderstats")
	local s = ls and ls:FindFirstChild("Speed")
	return s and s.Value or 0
end

local function cashOf(player)
	local ls = player:FindFirstChild("leaderstats")
	local s = ls and ls:FindFirstChild("Cash")
	return s and s.Value or 0
end

---------------------------------------------------------------- trails
local trailById = {}
for i, t in C.Trails do
	t.Order = i
	trailById[t.Id] = t
end

local function trailData(profile)
	local d = profile.Data.Trails
	if type(d) ~= "table" then
		d = { Owned = {}, Equipped = nil }
		profile.Data.Trails = d
	end
	d.Owned = type(d.Owned) == "table" and d.Owned or {}
	for _, t in C.Trails do
		if t.Free then
			d.Owned[t.Id] = true
		end
	end
	return d
end

local function zoneUnlocked(player, zone)
	local z = SeedConfig.Zones[zone or 1]
	return not z or speedOf(player) >= (z.SpeedRequired or 0)
end

-- the trail on your character: two attachments on the root, a coloured Trail between them
local function applyTrailVisual(player)
	local profile = profileOf(player)
	local char = player.Character
	local root = char and char:FindFirstChild("HumanoidRootPart")
	if not root then
		return
	end
	local old = root:FindFirstChild("GameTrail")
	if old then
		old:Destroy()
	end
	for _, n in { "GameTrailA0", "GameTrailA1" } do
		local a = root:FindFirstChild(n)
		if a then
			a:Destroy()
		end
	end
	local id = profile and trailData(profile).Equipped
	local t = id and trailById[id]
	player:SetAttribute("TrailMultiplier", t and t.Mult or nil)
	player:SetAttribute("Trail", t and t.Id or nil)
	if not t then
		return
	end
	local a0 = Instance.new("Attachment")
	a0.Name = "GameTrailA0"
	a0.Position = Vector3.new(0, 0.9, 0.3)
	a0.Parent = root
	local a1 = Instance.new("Attachment")
	a1.Name = "GameTrailA1"
	a1.Position = Vector3.new(0, -1.1, 0.3)
	a1.Parent = root
	local tr = Instance.new("Trail")
	tr.Name = "GameTrail"
	tr.Attachment0 = a0
	tr.Attachment1 = a1
	tr.Lifetime = 0.55
	tr.MinLength = 0.05
	tr.FaceCamera = true
	tr.LightEmission = t.Glow or 0.35
	tr.LightInfluence = 0.4
	tr.WidthScale = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(1, 0.15) })
	tr.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.05), NumberSequenceKeypoint.new(1, 1) })
	local cs = {}
	for i, c in t.Colors do
		table.insert(cs, ColorSequenceKeypoint.new((i - 1) / math.max(1, #t.Colors - 1), c))
	end
	if #cs == 1 then
		table.insert(cs, ColorSequenceKeypoint.new(1, t.Colors[1]))
	end
	tr.Color = ColorSequence.new(cs)
	tr.Parent = root
end

local function grantTrail(player, id)
	local profile = profileOf(player)
	local t = trailById[id]
	if not (profile and t) then
		return false
	end
	local d = trailData(profile)
	d.Owned[id] = true
	d.Equipped = id
	profile.Dirty = true
	applyTrailVisual(player)
	Remote:FireClient(player, "TrailBought", id)
	return true
end

function X.actions.BuyTrail(player, id)
	local profile = profileOf(player)
	local t = type(id) == "string" and trailById[id]
	if not (profile and t) then
		return
	end
	local d = trailData(profile)
	if d.Owned[id] then
		return
	end
	if not zoneUnlocked(player, t.Zone) then
		Remote:FireClient(player, "Error", "Locked")
		return
	end
	if cashOf(player) < t.Cash then
		Remote:FireClient(player, "NotEnough", t.Cash - cashOf(player), id)
		return
	end
	if PlantService.addStat(player, "Cash", -t.Cash) == nil then
		return
	end
	grantTrail(player, id)
end

function X.actions.BuyTrailRobux(player, id)
	local t = type(id) == "string" and trailById[id]
	if not t then
		return
	end
	if t.ProductId then
		MarketplaceService:PromptProductPurchase(player, t.ProductId)
	else
		notify(player, "Coming soon!")
	end
end

function X.actions.EquipTrail(player, id)
	local profile = profileOf(player)
	if not profile then
		return
	end
	local d = trailData(profile)
	if id == nil or id == false then
		d.Equipped = nil
	elseif type(id) == "string" and d.Owned[id] then
		d.Equipped = id
	else
		return
	end
	profile.Dirty = true
	applyTrailVisual(player)
	Remote:FireClient(player, "TrailEquipped", d.Equipped)
end

for _, t in C.Trails do
	if t.ProductId then
		Router.register(t.ProductId, function(player)
			return grantTrail(player, t.Id)
		end)
	end
end

---------------------------------------------------------------- selling
-- value of one animal / egg (Config.Sell)
local function animalValue(zone, eggId, animalId)
	local egg = DD.zoneEgg(zone, eggId)
	local a = egg and DD.eggAnimal(egg, animalId)
	return a and math.floor(a.IncomePerSecond * C.Sell.AnimalSeconds) or 0
end
local function eggValue(zone, eggId)
	local egg = DD.zoneEgg(zone, eggId)
	if not egg then
		return 0
	end
	local total, w = 0, 0
	for _, a in egg.Animals do
		total += a.IncomePerSecond * (a.Weight or 1)
		w += a.Weight or 1
	end
	return math.floor(total / math.max(w, 1) * C.Sell.EggSeconds)
end
X.animalValue = animalValue
X.eggValue = eggValue

-- list = { { Kind = "Pet" / "Egg", Id = recordId or itemId }, ... }
function X.actions.Sell(player, list)
	if type(list) ~= "table" or #list == 0 or #list > 200 then
		return
	end
	local total, count = 0, 0
	for _, e in list do
		if type(e) == "table" and type(e.Id) == "string" then
			local v = ZoneEggService.sellThing(player, e.Kind == "Egg" and "Egg" or "Pet", e.Id, animalValue, eggValue)
			if v then
				total += v
				count += 1
			end
		end
	end
	if count > 0 then
		PlantService.addStat(player, "Cash", total)
		Remote:FireClient(player, "Sold", count, total)
	end
end

---------------------------------------------------------------- settings
local SETTING_KEYS = { Music = true, SoundEffects = true, ShowOtherPets = true, HatchAnimation = true, LowGraphics = true }
local function settingsOf(profile)
	local s = profile.Data.Settings
	if type(s) ~= "table" then
		s = {}
		profile.Data.Settings = s
	end
	for k, v in C.SettingDefaults do
		if s[k] == nil then
			s[k] = v
		end
	end
	return s
end

function X.actions.SetSetting(player, arg)
	local profile = profileOf(player)
	if not (profile and type(arg) == "table" and SETTING_KEYS[arg.Key] and type(arg.Value) == "boolean") then
		return
	end
	settingsOf(profile)[arg.Key] = arg.Value
	profile.Dirty = true
end

---------------------------------------------------------------- free gift
local function giftOf(profile)
	local g = profile.Data.FreeGift
	if type(g) ~= "table" then
		g = {}
		profile.Data.FreeGift = g
	end
	return g
end

local GroupService = game:GetService("GroupService")
local function inGroup(player)
	-- a fresh lookup (GetRankInGroup is cached from when they joined the server)
	local ok, groups = pcall(GroupService.GetGroupsAsync, GroupService, player.UserId)
	if ok and type(groups) == "table" then
		for _, g in groups do
			if g.Id == C.FreeGift.GroupId then
				return true
			end
		end
		return false
	end
	local ok2, rank = pcall(player.GetRankInGroup, player, C.FreeGift.GroupId)
	return ok2 and rank > 0
end

function X.actions.GiftStep(player, step)
	local profile = profileOf(player)
	if not profile then
		return
	end
	local g = giftOf(profile)
	if step == "Like" or step == "Favorite" then
		g[step] = true
	elseif step == "Group" then
		if inGroup(player) then
			g.Group = true
		else
			notify(player, "Join the group first!")
			return
		end
	else
		return
	end
	profile.Dirty = true
end

function X.actions.ClaimGift(player)
	local profile = profileOf(player)
	if not profile then
		return
	end
	local g = giftOf(profile)
	if g.Claimed then
		return
	end
	if not g.Group and inGroup(player) then
		g.Group = true
	end
	if not (g.Like and g.Favorite and g.Group) then
		Remote:FireClient(player, "Error", "GiftSteps")
		return
	end
	g.Claimed = true
	profile.Dirty = true
	PlantService.addStat(player, "Speed", C.FreeGift.Speed)
	Remote:FireClient(player, "GiftClaimed", C.FreeGift.Speed)
end

---------------------------------------------------------------- pets / eggs
function X.actions.Hatch(player, recordId)
	if type(recordId) == "string" then
		ZoneEggService.hatch(player, recordId)
	end
end

function X.actions.EquipItem(player, itemId)
	if type(itemId) == "string" then
		if not ZoneEggService.equipItem(player, itemId) then
			notify(player, "Your plot is full!")
		end
	end
end

function X.actions.RemoveAll(player)
	local n = ZoneEggService.removeAll(player)
	if n > 0 then
		notify(player, ("Removed %d pet%s - they're in your hotbar."):format(n, n == 1 and "" or "s"))
	end
end

---------------------------------------------------------------- snapshot
function X.snapshot(player, profile)
	local d = trailData(profile)
	local unlocked = {}
	for _, t in C.Trails do
		unlocked[t.Id] = zoneUnlocked(player, t.Zone)
	end
	local g = giftOf(profile)
	return {
		Trails = { Owned = d.Owned, Equipped = d.Equipped, Unlocked = unlocked },
		Settings = settingsOf(profile),
		FreeGift = { Like = g.Like == true, Favorite = g.Favorite == true, Group = g.Group == true, Claimed = g.Claimed == true },
		HandEggs = ZoneEggService.handEggs(player),
	}
end

---------------------------------------------------------------- players
function X.onPlayer(player)
	local function onChar()
		task.wait(0.5)
		applyTrailVisual(player)
	end
	player.CharacterAdded:Connect(onChar)
	if player.Character then
		task.spawn(onChar)
	end
	-- profile arrives later than the character on join
	task.spawn(function()
		for _ = 1, 180 do
			if profileOf(player) then
				applyTrailVisual(player)
				return
			end
			task.wait(0.5)
		end
	end)
end

return X
