
---------------------------------------------------------------- GameUI V2 (sell / equip from UI / remove all)
-- Eggs in your hotbar (not placed yet), for the Sell window.
function ZoneEggService.handEggs(player)
	local profile = PlantService.getProfile(player)
	local out = {}
	if not (profile and profile.Loaded) then
		return out
	end
	for _, it in items(profile) do
		local egg = Config.zoneEgg(it.Zone, it.EggId)
		if egg then
			table.insert(out, { Id = it.Id, Zone = it.Zone, EggId = it.EggId, Name = egg.Name, Rarity = egg.Rarity })
		end
	end
	return out
end

-- Sell one thing: kind "Pet" = a placed animal (record) or one in the hotbar (animal item); "Egg" = an egg in the
-- hotbar. Returns its Cash value (the caller pays it) or nil. Values come from the passed-in valuers (GameUI Config).
function ZoneEggService.sellThing(player, kind, id, animalValue, eggValue)
	local profile = PlantService.getProfile(player)
	if not (profile and profile.Loaded) then
		return nil
	end
	if kind == "Egg" then
		local list = items(profile)
		for i, it in list do
			if it.Id == id then
				table.remove(list, i)
				profile.Dirty = true
				ZoneEggService.refreshTools(player)
				return eggValue(it.Zone, it.EggId)
			end
		end
		return nil
	end
	local list = records(profile)
	for i, r in list do
		if r.Id == id and r.Hatched then
			table.remove(list, i)
			profile.Dirty = true
			clearVisual(player, r.Id)
			return animalValue(r.Zone, r.EggId, r.AnimalId)
		end
	end
	local hand = animalItems(profile)
	for i, it in hand do
		if it.Id == id then
			table.remove(hand, i)
			profile.Dirty = true
			ZoneEggService.refreshTools(player)
			return animalValue(it.Zone, it.EggId, it.AnimalId)
		end
	end
	return nil
end

-- Put one hotbar animal onto the plot (free slot, laid out by slot) - the Hatch reveal's EQUIP / My Pets.
function ZoneEggService.equipItem(player, itemId)
	local profile = PlantService.getProfile(player)
	if not (profile and profile.Loaded) then
		return false
	end
	local hand = animalItems(profile)
	for i, it in hand do
		if it.Id == itemId then
			if not freeSlot(player, profile) then
				return false
			end
			if ZoneEggService.addEgg(player, it.Zone, it.EggId, true, nil, it.AnimalId) then
				table.remove(hand, i)
				profile.Dirty = true
				ZoneEggService.refreshTools(player)
				return true
			end
			return false
		end
	end
	return false
end

-- Remove All: every placed animal goes back to the hotbar.
function ZoneEggService.removeAll(player)
	local profile = PlantService.getProfile(player)
	if not (profile and profile.Loaded) then
		return 0
	end
	local ids = {}
	for _, r in records(profile) do
		if r.Hatched then
			table.insert(ids, r.Id)
		end
	end
	local n = 0
	for _, id in ids do
		if ZoneEggService.pickUp(player, id) then
			n += 1
		end
	end
	return n
end
