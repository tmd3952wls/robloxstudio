-- (별이떨어지는마을 원본, ReplicatedStorage.FilmLighting) 낮/밤 조명 프리셋. M.apply("day") / M.apply("night")
local L = game:GetService("Lighting")
local CS = game:GetService("CollectionService")
local M = {}
M.presets = {
	day = {
		L = {ClockTime = 16.3, GeographicLatitude = 35, Brightness = 3.2, ExposureCompensation = -0.75, Ambient = Color3.fromRGB(70, 75, 95), OutdoorAmbient = Color3.fromRGB(110, 120, 145), ColorShift_Top = Color3.fromRGB(255, 236, 205), ShadowSoftness = 0.05, EnvironmentDiffuseScale = 1, EnvironmentSpecularScale = 1},
		cc = {Saturation = 0.1, Contrast = 0.12, TintColor = Color3.fromRGB(255, 248, 238), Brightness = 0},
		bloom = {Intensity = 0.45, Threshold = 1.8, Size = 24},
		atmo = {Density = 0.24, Offset = 0.3, Haze = 0.6, Glare = 0.2, Color = Color3.fromRGB(200, 215, 235), Decay = Color3.fromRGB(170, 190, 220)},
		rays = 0.2,
	},
	night = {
		L = {ClockTime = 18.75, GeographicLatitude = 35, Brightness = 1.0, ExposureCompensation = -0.4, Ambient = Color3.fromRGB(30, 42, 90), OutdoorAmbient = Color3.fromRGB(62, 84, 165), ColorShift_Top = Color3.fromRGB(130, 160, 255), ShadowSoftness = 0.25, EnvironmentDiffuseScale = 0.5, EnvironmentSpecularScale = 0.4},
		cc = {Saturation = 0.15, Contrast = 0.2, TintColor = Color3.fromRGB(196, 212, 255), Brightness = 0},
		bloom = {Intensity = 0.8, Threshold = 1.15, Size = 30},
		atmo = {Density = 0.42, Offset = 0.05, Haze = 2.4, Glare = 0, Color = Color3.fromRGB(78, 108, 196), Decay = Color3.fromRGB(42, 62, 134)},
		rays = 0,
	},
}
local function inst(class, name)
	local o = L:FindFirstChild(name)
	if not o then o = Instance.new(class); o.Name = name; o.Parent = L end
	return o
end
function M.apply(which)
	local p = M.presets[which]; assert(p, which)
	for k, v in pairs(p.L) do L[k] = v end
	L.GlobalShadows = true
	local cc = inst("ColorCorrectionEffect", "FilmCC"); for k, v in pairs(p.cc) do cc[k] = v end
	local bl = inst("BloomEffect", "FilmBloom"); for k, v in pairs(p.bloom) do bl[k] = v end
	local at = inst("Atmosphere", "FilmAtmo"); for k, v in pairs(p.atmo) do at[k] = v end
	local sr = inst("SunRaysEffect", "FilmRays"); sr.Intensity = p.rays
	local night = which == "night"
	-- 창문: 밤에는 따뜻하게 빛남 (일부는 꺼진 채로)
	for i, pane in ipairs(CS:GetTagged("WindowPane")) do
		if night and (pane:GetAttribute("Lit") ~= false) then
			pane.Material = Enum.Material.Neon; pane.Color = Color3.fromRGB(255, 196, 110); pane.Transparency = 0.05
		else
			pane.Material = Enum.Material.Glass; pane.Color = pane:GetAttribute("DayColor") or pane.Color; pane.Transparency = pane:GetAttribute("DayTransparency") or 0.3
		end
	end
	for _, l in ipairs(CS:GetTagged("NightLight")) do l.Enabled = night end
	L:SetAttribute("Preset", which)
end
return M
