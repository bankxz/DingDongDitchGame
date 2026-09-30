
---------------------------------------------------------------- V2 UI (Figma "UI System" V2 screens)
-- Images: Figma image name -> rbxassetid (filled in by the import; "" = not uploaded yet)
C.ImagesV2 = C.ImagesV2 or {}

-- Trails (Trail Shop). Mult = Speed gained per treadmill step is multiplied by this while equipped.
-- Cash price, Robux ProductId (nil = "Coming soon!" until you create the Developer Product and paste its id),
-- Zone = SpeedRequired of ForestSeedSystem Config.Zones[Zone] needed before it can be bought.
local function rgb(r, g, b)
	return Color3.fromRGB(r, g, b)
end
C.Trails = {
	{ Id = "GreyTrail", Name = "Grey Trail", Rarity = "Common", Mult = 1.5, Cash = 0, Free = true, Robux = nil, ProductId = nil, Art = "TrailGrey", Zone = 1, Colors = { rgb(205, 210, 218), rgb(150, 155, 165) } },
	{ Id = "GreenTrail", Name = "Green Trail", Rarity = "Uncommon", Mult = 2, Cash = 5000, Robux = 16, ProductId = nil, Art = "TrailGreen", Zone = 1, Colors = { rgb(110, 255, 90), rgb(40, 200, 40) } },
	{ Id = "BlueTrail", Name = "Blue Trail", Rarity = "Rare", Mult = 2.5, Cash = 75000, Robux = 24, ProductId = nil, Art = "TrailBlue", Zone = 2, Colors = { rgb(90, 200, 255), rgb(30, 110, 255) } },
	{ Id = "PurpleTrail", Name = "Purple Trail", Rarity = "Epic", Mult = 3, Cash = 750000, Robux = 40, ProductId = nil, Art = "TrailPurple", Zone = 3, Colors = { rgb(205, 120, 255), rgb(130, 40, 230) } },
	{ Id = "GoldenTrail", Name = "Golden Trail", Rarity = "Legendary", Mult = 3.5, Cash = 2500000, Robux = 64, ProductId = nil, Art = "TrailGold", Zone = 4, Colors = { rgb(255, 235, 110), rgb(255, 170, 20) }, Glow = 0.6 },
	{ Id = "RedTrail", Name = "Red Trail", Rarity = "Mythic", Mult = 4, Cash = 50000000, Robux = 99, ProductId = nil, Art = "TrailRed", Zone = 5, Colors = { rgb(255, 110, 90), rgb(220, 20, 30) }, Glow = 0.6 },
	{ Id = "GalaxyTrail", Name = "Galaxy Trail", Rarity = "Cosmic", Mult = 5, Cash = 1000000000, Robux = 149, ProductId = nil, Art = "TrailGalaxy", Zone = 6, Colors = { rgb(40, 20, 120), rgb(200, 70, 255), rgb(60, 180, 255) }, Glow = 0.8 },
	{ Id = "SecretTrail", Name = "Secret Trail", Rarity = "Secret", Mult = 7, Cash = 100000000000, Robux = 249, ProductId = nil, Art = "TrailZebra", Zone = 7, Colors = { rgb(20, 20, 22), rgb(245, 245, 245), rgb(20, 20, 22), rgb(245, 245, 245) } },
	{ Id = "EternalTrail", Name = "Eternal Trail", Rarity = "Eternal", Mult = 10, Cash = 12500000000000, Robux = 480, ProductId = nil, Art = "TrailPink", Zone = 8, Colors = { rgb(255, 95, 200), rgb(60, 220, 255) }, Glow = 1 },
}
C.Rarity.Cosmic = C.Rarity.Cosmic or { Color = rgb(40, 220, 255), Dark = rgb(10, 100, 140) }
C.Rarity.Eternal = { Color = rgb(255, 95, 200), Dark = rgb(120, 20, 90) }

-- Selling: an animal sells for IncomePerSecond x AnimalSeconds; an egg for the average income of what can hatch
-- from it x EggSeconds.
C.Sell = { AnimalSeconds = 60, EggSeconds = 30 }

-- Settings window defaults (saved per player)
C.SettingDefaults = { Music = true, SoundEffects = true, ShowOtherPets = true, HatchAnimation = true, LowGraphics = false }

-- Free Gift: like + favourite + join the group -> Speed, once
C.FreeGift = { GroupId = 785823446, Speed = 10000 }

-- Pet Index / My Pets art for each zone tab (V2 zone icons)
C.ZoneIconsV2 = { forest = "ZoneForest", lake = "ZoneOcean", desert = "ZoneDesert", jungle = "ZoneForest", snow = "ZoneSpace", volcano = "ZoneVolcano", underwater = "ZoneOcean", prehistoric = "ZoneVolcano" }
C.ZoneOrder = { "forest", "lake", "desert", "jungle", "snow", "volcano", "underwater" }
C.ZoneNames = { forest = "Forest", lake = "Lake", desert = "Desert", jungle = "Jungle", snow = "Snow", volcano = "Volcano", underwater = "Underwater", prehistoric = "Prehistoric" }
C.IndexRewards.snow = C.IndexRewards.snow or { Cash = 1000000000, Speed = 2500000 }
C.IndexRewards.volcano = C.IndexRewards.volcano or { Cash = 25000000000, Speed = 25000000 }
C.IndexRewards.underwater = C.IndexRewards.underwater or { Cash = 500000000000, Speed = 250000000 }
C.Products.Cash6 = C.Products.Cash6 or { Id = nil, Price = 1500, Kind = "Cash", Amount = 20000000, Art = "MoneySafe" }
C.ShopMoneyRows = { { "Cash1", "Cash2", "Cash3" }, { "Cash4", "Cash5", "Cash6" } }
-- V2 art for each shop product (Figma icon names)
C.ProductArtV2 = {
	Speed1 = "Shoe", Speed2 = "ShoeWinged", Speed3 = "Bolt", Speed4 = "Stopwatch", Speed5 = "ChestGold", Speed6 = "Crown",
	Cash1 = "Cash", Cash2 = "CashPile", Cash3 = "CashMountain", Cash4 = "ChestCash", Cash5 = "ChestGold", Cash6 = "PremiumCoin",
}
