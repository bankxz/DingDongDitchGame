-- Idle animations for the lobby merchants (models with attribute MerchantIdle = true).
-- Loops the R15 idle, waves now and then, and turns to face the nearest player who walks up.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

local IDLE = { "rbxassetid://507766666", "rbxassetid://507766951" }
local WAVE = "rbxassetid://507770239"
local LOOK_RANGE = 24

local function anim(id)
	local a = Instance.new("Animation")
	a.AnimationId = id
	return a
end

local function setup(npc)
	local hum = npc:FindFirstChildOfClass("Humanoid")
	local hrp = npc:FindFirstChild("HumanoidRootPart")
	if not hum or not hrp then
		return
	end
	local animator = hum:FindFirstChildOfClass("Animator") or Instance.new("Animator", hum)
	local tracks = {}
	for i, id in IDLE do
		local ok, t = pcall(animator.LoadAnimation, animator, anim(id))
		if ok then
			t.Looped = true
			t.Priority = Enum.AnimationPriority.Idle
			tracks[i] = t
		end
	end
	if tracks[1] then
		tracks[1]:Play(0.3)
	end
	local okW, wave = pcall(animator.LoadAnimation, animator, anim(WAVE))
	if okW then
		wave.Priority = Enum.AnimationPriority.Action
	end

	local home = hrp.CFrame
	local lastWave = 0
	local lastNear = nil
	-- alternate the two idles + wave when someone new comes close, or every ~12s
	task.spawn(function()
		local which = 1
		while npc.Parent do
			task.wait(6 + math.random() * 4)
			local nxt = (which % #tracks) + 1
			if tracks[nxt] and tracks[nxt] ~= tracks[which] then
				tracks[nxt]:Play(0.6)
				tracks[which]:Stop(0.6)
				which = nxt
			end
			if okW and os.clock() - lastWave > 12 then
				lastWave = os.clock()
				wave:Play(0.2)
			end
		end
	end)
	-- face the nearest player (yaw only, smoothed)
	local yaw = 0
	local acc = 0
	RunService.Heartbeat:Connect(function(dt)
		acc += dt
		if acc < 1 / 20 then
			return
		end
		local step = acc
		acc = 0
		if not npc.Parent then
			return
		end
		local best, bestD = nil, LOOK_RANGE
		for _, p in Players:GetPlayers() do
			local r = p.Character and p.Character:FindFirstChild("HumanoidRootPart")
			if r then
				local d = (r.Position - home.Position).Magnitude
				if d < bestD then
					best, bestD = r, d
				end
			end
		end
		local target = 0
		if best then
			local rel = home:PointToObjectSpace(best.Position)
			target = math.clamp(math.atan2(-rel.X, -rel.Z), -1.1, 1.1)
			if best ~= lastNear and okW and os.clock() - lastWave > 4 then
				lastWave = os.clock()
				wave:Play(0.2)
			end
		end
		lastNear = best
		yaw += (target - yaw) * math.min(1, step * 5)
		hrp.CFrame = home * CFrame.Angles(0, yaw, 0)
	end)
end

local function scan(root)
	for _, d in root:GetDescendants() do
		if d:IsA("Model") and d:GetAttribute("MerchantIdle") then
			task.spawn(setup, d)
		end
	end
end

local booths = workspace:WaitForChild("Map"):WaitForChild("spawn"):WaitForChild("MerchantBooths", 30)
if booths then
	scan(booths)
end
