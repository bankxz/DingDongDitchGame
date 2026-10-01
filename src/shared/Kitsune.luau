--!strict
--[[
	Kitsune animation controller.

	Usage (server or client, on the imported kitsune Model):
		local Kitsune = require(ReplicatedStorage.Shared.Kitsune)
		local k = Kitsune.new(workspace.Kitsune, {
			Idle = "rbxassetid://<idle id>",
			Run = "rbxassetid://<run id>",
			Sleep = "rbxassetid://<sleep id>",
		})
		k:Play("Idle")          -- crossfades from whatever is playing
		k:Play("Run", 0.15)
		k:Destroy()

	The model needs the skinned MeshPart + bones from Kitsune.fbx (3D Importer,
	Rig type: R15/Custom with "Import as skinned mesh").  An AnimationController
	and Animator are created if they do not exist.
]]

local Kitsune = {}
Kitsune.__index = Kitsune

export type AnimName = "Idle" | "Run" | "Sleep"
export type AnimIds = { Idle: string, Run: string, Sleep: string }

local PRIORITY: { [string]: Enum.AnimationPriority } = {
	Idle = Enum.AnimationPriority.Idle,
	Sleep = Enum.AnimationPriority.Idle,
	Run = Enum.AnimationPriority.Movement,
}

export type Kitsune = typeof(setmetatable(
	{} :: {
		Model: Model,
		Animator: Animator,
		Tracks: { [string]: AnimationTrack },
		Current: string?,
	},
	Kitsune
))

local function getAnimator(model: Model): Animator
	local controller = model:FindFirstChildOfClass("AnimationController")
		or model:FindFirstChildOfClass("Humanoid")
	if not controller then
		local ac = Instance.new("AnimationController")
		ac.Parent = model
		controller = ac
	end
	assert(controller)
	local animator = controller:FindFirstChildOfClass("Animator")
	if not animator then
		local a = Instance.new("Animator")
		a.Parent = controller
		animator = a
	end
	return animator :: Animator
end

function Kitsune.new(model: Model, ids: AnimIds): Kitsune
	local self = setmetatable({
		Model = model,
		Animator = getAnimator(model),
		Tracks = {},
		Current = nil,
	}, Kitsune)
	for name, id in ids :: any do
		local anim = Instance.new("Animation")
		anim.Name = "Kitsune_" .. name
		anim.AnimationId = id
		local track = self.Animator:LoadAnimation(anim)
		track.Looped = true -- all three clips are authored as seamless loops
		track.Priority = PRIORITY[name] or Enum.AnimationPriority.Core
		self.Tracks[name] = track
	end
	return self
end

function Kitsune.Play(self: Kitsune, name: AnimName, fadeTime: number?)
	local fade = fadeTime or 0.25
	if self.Current == name then
		return
	end
	local nextTrack = self.Tracks[name]
	assert(nextTrack, "unknown kitsune animation " .. tostring(name))
	if self.Current then
		self.Tracks[self.Current]:Stop(fade)
	end
	nextTrack:Play(fade)
	self.Current = name
end

function Kitsune.Stop(self: Kitsune, fadeTime: number?)
	if self.Current then
		self.Tracks[self.Current]:Stop(fadeTime or 0.25)
		self.Current = nil
	end
end

function Kitsune.Destroy(self: Kitsune)
	for _, track in self.Tracks do
		track:Stop(0)
		track:Destroy()
	end
	table.clear(self.Tracks)
	self.Current = nil
end

return Kitsune
