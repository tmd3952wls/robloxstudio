-- (별이떨어지는마을 원본, ReplicatedStorage.FilmDirector, 자식 ModuleScript "Shots" 필요)
-- 촬영 감독 모듈: 샷마다 배우·조명·별 효과를 세팅하고 카메라 위치를 계산한다.
-- 편집 모드에서는 D.preview(n) 으로 첫 프레임을 미리 볼 수 있다.
local RS = game:GetService("ReplicatedStorage")
local CS = game:GetService("CollectionService")
local RunService = game:GetService("RunService")
local Faces = require(RS:WaitForChild("HaruFaces"))
local Lights = require(RS:WaitForChild("FilmLighting"))
local town = workspace:WaitForChild("Town")
local cast = workspace:WaitForChild("Cast")
local V = Vector3.new
local rad, sin, cos = math.rad, math.sin, math.cos
local D = {}
local RUN = RunService:IsRunning()
local rng = Random.new(3)
local GOLD = Color3.fromRGB(255, 232, 150)
D.SQ, D.ST, D.ROOM = 2.45, 2.35, 3.35
D.peak = V(0, 266, -430)
D.pathHome = {V(0, 40, -140), V(0, 150, -320), V(0, 268, -430), V(0, 520, -500)}

---------------------------------------------------------------- 배우
local footOff, actorYaw, tracks, origC0 = {}, {}, {}, {}
local ANIM = {idle = 507766388, walk = 507777826, run = 507767714, wave = 507770239, point = 507770453, cheer = 507770677, laugh = 507770818, dance = 507771019}
function D.init()
	for _, rig in ipairs(cast:GetChildren()) do
		local lf, rf = rig:FindFirstChild("LeftFoot"), rig:FindFirstChild("RightFoot")
		if lf and rf then
			local foot = math.min(lf.Position.Y - lf.Size.Y / 2, rf.Position.Y - rf.Size.Y / 2)
			footOff[rig.Name] = rig:GetPivot().Position.Y - foot
			local an = rig:FindFirstChild("Animate"); if an then an:Destroy() end
		end
	end
end
function D.hideAll()
	local i = 0
	for _, rig in ipairs(cast:GetChildren()) do
		i += 1
		rig:PivotTo(CFrame.new(i * 10, -300, 600))
		actorYaw[rig.Name] = 0
	end
end
function D.anim(name, key, speed)
	if not RUN then return end
	local rig = cast:FindFirstChild(name); if not rig then return end
	local hum = rig:FindFirstChildOfClass("Humanoid"); if not hum then return end
	local animator = hum:FindFirstChildOfClass("Animator") or Instance.new("Animator", hum)
	tracks[name] = tracks[name] or {}
	for k, tr in pairs(tracks[name]) do if k ~= key then tr:Stop(0.1) end end
	if not key then return end
	local tr = tracks[name][key]
	if not tr then
		local a = Instance.new("Animation"); a.AnimationId = "rbxassetid://" .. ANIM[key]
		local ok, res = pcall(function() return animator:LoadAnimation(a) end)
		if not ok then return end
		tr = res; tr.Looped = true; tracks[name][key] = tr
	end
	if not tr.IsPlaying then tr:Play(0.1) end
	tr:AdjustSpeed(speed or 1)
end
function D.face(name, expr)
	local rig = cast:FindFirstChild(name); if rig then Faces.apply(rig.Head, rig, expr) end
end
-- yaw: 배우가 바라보는 방향. 0 = 남쪽(+Z), 90 = 동쪽(+X), 180 = 북쪽, -90 = 서쪽
function D.put(name, x, z, yaw, face, anim, y)
	local rig = cast:FindFirstChild(name); if not rig then return end
	actorYaw[name] = yaw or 0
	rig:PivotTo(CFrame.new(x, (y or D.SQ) + (footOff[name] or 3), z) * CFrame.Angles(0, rad((yaw or 0) + 180), 0))
	if face then D.face(name, face) end
	D.anim(name, anim or "idle")
	return rig
end
local rp = RaycastParams.new(); rp.FilterType = Enum.RaycastFilterType.Include
function D.roofY(x, z)
	rp.FilterDescendantsInstances = {town.Houses}
	local r = workspace:Raycast(V(x, 120, z), V(0, -200, 0), rp)
	return r and r.Position.Y or 20
end
function D.onRoof(name, x, z, yaw, face, anim)
	return D.put(name, x, z, yaw, face, anim, D.roofY(x, z))
end
function D.pose(name, kind)
	local rig = cast:FindFirstChild(name); if not rig then return end
	rig:SetAttribute("Pose", kind or "")
	pcall(function()
		local sh, el = rig.LeftUpperArm.LeftShoulder, rig.LeftLowerArm.LeftElbow
		origC0[name] = origC0[name] or {sh.C0, el.C0}
		local o = origC0[name]
		if kind == "hold" then sh.C0 = o[1] * CFrame.Angles(rad(80), 0, 0); el.C0 = o[2]
		elseif kind == "ear" then sh.C0 = o[1] * CFrame.Angles(rad(70), 0, rad(-12)); el.C0 = o[2] * CFrame.Angles(rad(115), 0, 0)
		else sh.C0 = o[1]; el.C0 = o[2] end
	end)
end
function D.handJar(name, on, open)
	local rig = cast:FindFirstChild(name); local hj = rig and rig:FindFirstChild("HandJar"); if not hj then return end
	hj.Glass.Transparency = on and 0.6 or 1
	hj.Lid.Transparency = (on and not open) and 0 or 1
	hj.Star.Transparency = (on and not open) and 0 or 1
	local pl = hj.Star:FindFirstChildOfClass("PointLight"); if pl then pl.Enabled = on and not open end
end
-- 굽기(FilmBaker)와 같은 방식으로 팔 자세를 적용한 위치 (편집 모드에선 관절이 안 움직이므로)
local POSES = {hold = {CFrame.Angles(rad(80), 0, 0), nil}, ear = {CFrame.Angles(rad(70), 0, rad(-12)), CFrame.Angles(rad(115), 0, 0)}}
function D.posedPos(name, path)
	local p = D.partPos(name, path)
	local rig = cast:FindFirstChild(name); if not rig then return p end
	local pose = POSES[rig:GetAttribute("Pose") or ""]; if not pose then return p end
	local ok, res = pcall(function()
		local ut, ua, la = rig.UpperTorso, rig.LeftUpperArm, rig.LeftLowerArm
		local J = ut.CFrame * ua.LeftShoulder.C0
		local Rsh = J * pose[1] * J:Inverse()
		local Rel = Rsh
		if pose[2] then local Je = Rsh * (ua.CFrame * la.LeftElbow.C0); Rel = Je * pose[2] * Je:Inverse() * Rsh end
		return Rel * p
	end)
	return ok and res or p
end
function D.partPos(name, path)
	local o = cast:FindFirstChild(name)
	for seg in string.gmatch(path, "[^%.]+") do o = o and o:FindFirstChild(seg) end
	return o and o.Position or V(0, 5, 0)
end

---------------------------------------------------------------- 세트 상태
function D.lamps(on)
	for _, jar in ipairs(CS:GetTagged("StarJar")) do
		if not CS:HasTag(jar, "RoomJar") then
			local s = jar:FindFirstChild("Star")
			if s then
				s.Transparency = on and 0 or 1
				local pl = s:FindFirstChildOfClass("PointLight"); if pl then pl.Enabled = on and D.night end
			end
		end
	end
end
function D.roomJars(open)
	for _, jar in ipairs(CS:GetTagged("RoomJar")) do
		local s, lid = jar:FindFirstChild("Star"), jar:FindFirstChild("Lid")
		if s then s.Transparency = open and 1 or 0; local pl = s:FindFirstChildOfClass("PointLight"); if pl then pl.Enabled = not open end end
		if lid then lid.Transparency = open and 1 or 0 end
	end
end
function D.sky(mode)
	local sk = town:FindFirstChild("SkyStars"); if not sk then return end
	for i, s in ipairs(sk:GetChildren()) do
		local show = mode == "full" or (mode == "some" and i % 3 == 0) or (mode == "few" and i <= 6)
		s.Transparency = show and 0 or 1
	end
end
function D.light(which)
	D.night = which ~= "day"
	Lights.apply(which)
	for _, l in ipairs(CS:GetTagged("GlowLoaf")) do l.Material = Enum.Material.Neon end
end

---------------------------------------------------------------- 별 효과
local fxFolder, parts = nil, {}
function D.clearFX()
	if fxFolder then fxFolder:Destroy() end
	for _, o in ipairs(workspace:GetChildren()) do if o.Name == "FilmFX" then o:Destroy() end end
	fxFolder = Instance.new("Folder"); fxFolder.Name = "FilmFX"; fxFolder.Parent = workspace
	parts = {}
end
function D.star(pos, size, trail)
	size = size or 1
	local p = Instance.new("Part"); p.Shape = Enum.PartType.Ball; p.Size = V(size, size, size)
	p.Material = Enum.Material.Neon; p.Color = GOLD; p.Anchored = true; p.CanCollide = false; p.CastShadow = false
	p.Position = pos
	if trail then
		local a0 = Instance.new("Attachment"); a0.Position = V(0, size * 0.35, 0); a0.Parent = p
		local a1 = Instance.new("Attachment"); a1.Position = V(0, -size * 0.35, 0); a1.Parent = p
		local tr = Instance.new("Trail"); tr.Attachment0 = a0; tr.Attachment1 = a1; tr.Lifetime = 0.8; tr.LightEmission = 1
		tr.Color = ColorSequence.new(GOLD); tr.Transparency = NumberSequence.new(0.25, 1); tr.FaceCamera = true
		tr.WidthScale = NumberSequence.new(1, 0.1); tr.Parent = p
	end
	p.Parent = fxFolder
	return p
end
-- 눈처럼 내리는(또는 speed 가 음수면 솟아오르는) 별
function D.fall(center, radius, n, top, bot, speed, size)
	for i = 1, n do
		local a, r = rng:NextNumber(0, 6.283), radius * math.sqrt(rng:NextNumber())
		local it = {kind = "fall", x = center.X + sin(a) * r, z = center.Z + cos(a) * r, y = rng:NextNumber(bot, top), top = top, bot = bot,
			v = speed * rng:NextNumber(0.7, 1.3), ph = rng:NextNumber(0, 6.28)}
		it.p = D.star(V(it.x, it.y, it.z), (size or 1.3) * rng:NextNumber(0.75, 1.25), true)
		table.insert(parts, it)
	end
end
local function sample(pts, lens, u)
	if u <= 0 then return pts[1] end
	for i = 1, #lens do
		if u <= lens[i] then
			local prev = (i == 1) and 0 or lens[i - 1]
			return pts[i]:Lerp(pts[i + 1], (u - prev) / (lens[i] - prev))
		end
	end
	return pts[#pts]
end
-- 길을 따라 흐르는 별. opts: loop, prefill(처음부터 길 위에 흩어 둠), gap(줄지어 출발할 때 간격), size, spread
function D.stream(pts, n, speed, opts)
	opts = opts or {}
	local lens, total = {}, 0
	for i = 1, #pts - 1 do total += (pts[i + 1] - pts[i]).Magnitude; lens[i] = total end
	for i = 1, n do
		local sp = opts.spread or 0
		local it = {kind = "stream", pts = pts, lens = lens, total = total, v = speed * rng:NextNumber(0.85, 1.15), loop = opts.loop,
			off = V(rng:NextNumber(-sp, sp), rng:NextNumber(-sp, sp) * 0.6, rng:NextNumber(-sp, sp)),
			u = opts.prefill and rng:NextNumber(0, total) or -(i - 1) * (opts.gap or 4), tighten = opts.tighten, hold = opts.holdVisible}
		if opts.delay then it.u = -rng:NextNumber(0, opts.delay) * it.v end
		it.p = D.star(sample(pts, lens, math.max(it.u, 0)) + it.off, (opts.size or 1.2) * rng:NextNumber(0.8, 1.2), true)
		if it.u < 0 and not it.hold then it.p.Transparency = 1 end
		table.insert(parts, it)
	end
end
local function val(x) if type(x) == "function" then return x() end return x end
D.val = val
local function E(a, kind)
	if kind == "lin" then return a elseif kind == "out" then return 1 - (1 - a) ^ 3 elseif kind == "in" then return a ^ 3 end
	return a * a * (3 - 2 * a)
end
D.E = E
-- keys: {{t, pos, ease}, ...}  opts: hideBefore, hideAfter
function D.track(keys, size, trail, opts)
	opts = opts or {}
	local ks = {}
	for _, k in ipairs(keys) do table.insert(ks, {t = k[1], p = val(k[2]), e = k[3]}) end
	local it = {kind = "track", keys = ks, hideBefore = opts.hideBefore, hideAfter = opts.hideAfter}
	it.p = D.star(ks[1].p, size or 1, trail)
	if opts.hideBefore and ks[1].t > 0 then it.p.Transparency = 1 end
	table.insert(parts, it)
	return it
end
function D.orbit(centerFn, r, n, w)
	for i = 1, n do
		local it = {kind = "orbit", c = centerFn, r = r * rng:NextNumber(0.8, 1.2), a = i / n * 6.283, w = w or 2.2, dy = rng:NextNumber(-1.2, 1.2)}
		it.p = D.star(centerFn() + V(sin(it.a) * it.r, it.dy, cos(it.a) * it.r), 0.55, true)
		table.insert(parts, it)
	end
end
function D.update(dt, t)
	for _, it in ipairs(parts) do
		if it.kind == "fall" then
			it.y -= it.v * dt
			if it.v > 0 and it.y < it.bot then it.y = it.top elseif it.v < 0 and it.y > it.top then it.y = it.bot end
			it.p.Position = V(it.x + sin(t * 0.8 + it.ph) * 1.3, it.y, it.z + cos(t * 0.6 + it.ph) * 1.3)
		elseif it.kind == "stream" then
			it.u += it.v * dt
			if it.u > it.total then if it.loop then it.u = 0 else it.p.Transparency = 1 end end
			if it.u >= 0 and it.u <= it.total then
				it.p.Transparency = 0
				local k = math.min(1, it.u / 30)
				if it.tighten then k *= math.max(0, 1 - t / it.tighten) end
				it.p.Position = sample(it.pts, it.lens, it.u) + it.off * k
			end
		elseif it.kind == "track" then
			local ks = it.keys
			local k0, k1 = ks[1], ks[1]
			for i = 1, #ks - 1 do if t >= ks[i].t then k0, k1 = ks[i], ks[i + 1] end end
			if t >= ks[#ks].t then k0, k1 = ks[#ks], ks[#ks] end
			local a = (k1.t > k0.t) and math.clamp((t - k0.t) / (k1.t - k0.t), 0, 1) or 0
			it.p.Position = k0.p:Lerp(k1.p, E(a, k1.e))
			local hide = (it.hideBefore and t < ks[1].t) or (it.hideAfter and t > ks[#ks].t)
			it.p.Transparency = hide and 1 or 0
		elseif it.kind == "orbit" then
			it.a += it.w * dt
			it.p.Position = it.c() + V(sin(it.a) * it.r, it.dy + sin(it.a * 2) * 0.3, cos(it.a) * it.r)
		end
	end
	local s = D.current
	if s and s.upd then s.upd(t, dt) end
end

---------------------------------------------------------------- 카메라
local SIZE = {close = 4.4, mid = 7.2, full = 10.5, wide = 17}
local FOV = {close = 30, mid = 36, full = 42, wide = 48}
-- 대상 주위로 수평 회전 (옆으로 돌며 다가가는 시차 효과)
local function orbitAround(p, l, deg)
	local off = p - l
	local d = off.Magnitude
	-- 먼 곳을 볼 때는 옆으로 6 스터드 이상 움직이지 않게 제한
	local maxDeg = math.deg(math.asin(math.min(1, 6 / math.max(d, 0.01))))
	deg = math.clamp(deg, -maxDeg, maxDeg)
	local c, s = cos(rad(deg)), sin(rad(deg))
	return l + V(off.X * c + off.Z * s, off.Y, -off.X * s + off.Z * c)
end
local function resolve(c, n)
	if c.keys then
		local ks, fov, roll = {}, c.fov or 44, c.roll or 0
		for _, k in ipairs(c.keys) do
			fov = k[4] or fov; roll = k[6] or roll
			table.insert(ks, {t = k[1], p = val(k[2]), l = val(k[3]), fov = fov, e = k[5], roll = roll})
		end
		return {keys = ks, n = n, hand = c.hand or 1}
	end
	local p0, l0, p1, l1, ps
	local side = (n % 2 == 0) and 1 or -1
	if c.fn then p0, l0, p1, l1 = c.fn()
	elseif c.from then p0, l0, p1, l1 = c.from, c.look, c.from2, c.look2
	else
		local T, yaw, dist
		if c.on then
			local rig = cast:FindFirstChild(c.on)
			local part = (c.size == "close") and rig.Head or rig.UpperTorso
			T = part.Position + V(0, c.h or ((c.size == "close") and 0.05 or 0.7), 0)
			yaw = (actorYaw[c.on] or 0) + (c.yaw or 0); dist = c.dist or SIZE[c.size or "mid"]
		else
			T = type(c.at) == "function" and c.at() or c.at; yaw = c.yaw or 0; dist = c.dist or 10
		end
		-- 인물: 중간·전신은 아래에서 올려다보기, 클로즈업은 눈높이 살짝 위
		local defPitch = c.on and ((c.size == "close") and 3 or -8) or 2
		local pitch = rad(c.pitch or defPitch)
		local function posAt(d, yw) return T + V(sin(rad(yw)) * cos(pitch), sin(pitch), cos(rad(yw)) * cos(pitch)) * d end
		p0, l0 = posAt(dist, yaw), T
		if c.move == "orbit" then p1 = posAt(dist, yaw + (c.arc or 32)) end
	end
	local dir = l0 - p0
	local L = dir.Magnitude
	local u = dir.Unit
	local mv = c.move or "push"
	if not p1 then
		if mv == "push" then p1 = orbitAround(p0 + u * math.min(L * 0.24, 45), l0, c.arc or 0)
		elseif mv == "pull" then p1 = orbitAround(p0 - u * math.min(L * 0.28, 45), l0, c.arc or 0)
		elseif mv == "snap" then p1 = p0 + u * math.min(L * 0.06, 6); ps = p0 - u * math.min(L * 0.75, 70)
		elseif mv == "snapout" then p1 = p0 - u * math.min(L * 0.06, 6); ps = p0 + u * math.min(L * 0.5, 60)
		elseif mv == "crane" then p1 = p0 + V(0, c.rise or 20, 0); l1 = l1 or (l0 + V(0, (c.rise or 20) * 0.7, 0))
		elseif mv == "tiltup" then p1 = p0 + u * math.min(L * 0.05, 4); l1 = l1 or (l0 + V(0, c.rise or 30, 0))
		else p1 = p0 end
	end
	local roll = c.roll
	if roll == nil then roll = 0 end
	local fov = c.fov or (c.size and FOV[c.size]) or 44
	return {p0 = p0, l0 = l0, p1 = p1, l1 = l1 or l0, ps = ps, roll = roll, fov = fov, n = n}
end
local function ease(a) return a * a * (3 - 2 * a) * 0.35 + a * 0.65 end
-- 움직이며 찍는 카메라: 바라보는 쪽으로 일정한 속도로 밀고 들어가며 옆으로 살짝 돎 (컷 처음·끝에도 멈추지 않음)
local function moving(shot, t, pos, look)
	local pf = shot.push
	if pf == nil then pf = 0.22 end
	if pf <= 0 then return pos end
	local dir = look - pos
	local L = dir.Magnitude
	if L < 1e-3 then return pos end
	local u = math.clamp(t / shot.d, 0, 1) - 0.5
	local amt = math.min(pf * L, 30)
	local right = dir.Unit:Cross(Vector3.yAxis)
	right = right.Magnitude > 1e-3 and right.Unit or Vector3.xAxis
	local side = (shot.n % 2 == 0) and 1 or -1
	return pos + dir.Unit * (amt * u) + right * (side * 0.35 * amt * u)
end
D.moving = moving
-- 세로 영상용 카메라. 반환값 CFrame 에는 Studio 창용 90도 눕힘이 포함됨
function D.camCF(shot, t)
	local c = shot._cam
	local pos, look
	if c.keys then
		local ks = c.keys
		local k0, k1 = ks[1], ks[1]
		for i = 1, #ks - 1 do if t >= ks[i].t then k0, k1 = ks[i], ks[i + 1] end end
		if t >= ks[#ks].t then k0, k1 = ks[#ks], ks[#ks] end
		local a = (k1.t > k0.t) and math.clamp((t - k0.t) / (k1.t - k0.t), 0, 1) or 0
		a = E(a, k1.e)
		pos, look = k0.p:Lerp(k1.p, a), k0.l:Lerp(k1.l, a)
		local fov = k0.fov + (k1.fov - k0.fov) * a
		local roll = k0.roll + (k1.roll - k0.roll) * a
		pos = moving(shot, t, pos, look)
		local w = math.min(0.0009 * (pos - look).Magnitude, 0.12) * c.hand
		pos += V(sin(t * 2.1 + c.n) * w, sin(t * 2.9 + c.n * 1.7) * w * 0.7, 0)
		return CFrame.lookAt(pos, look) * CFrame.Angles(0, 0, rad(90 + roll)), fov
	end
	if shot.camFn then
		local f2, r2
		pos, look, f2, r2 = shot.camFn(t)
		if f2 then return CFrame.lookAt(pos, look) * CFrame.Angles(0, 0, rad(90 + (r2 or 0))), f2 end
	elseif c.ps and t < 0.3 then
		local k = 1 - (1 - t / 0.3) ^ 3
		pos, look = c.ps:Lerp(c.p0, k), c.l0
	else
		local a = math.clamp((c.ps and (t - 0.3) / math.max(shot.d - 0.3, 0.01)) or (t / shot.d), 0, 1)
		a = ease(a)
		pos, look = c.p0:Lerp(c.p1, a), c.l0:Lerp(c.l1, a)
		pos = moving(shot, t, pos, look)
	end
	-- 손으로 든 듯한 아주 작은 흔들림
	local w = math.min(0.0022 * (pos - look).Magnitude, 0.5)
	pos += V(sin(t * 2.1 + c.n) * w, sin(t * 2.9 + c.n * 1.7) * w * 0.7, 0)
	return CFrame.lookAt(pos, look) * CFrame.Angles(0, 0, rad(90 + c.roll)), c.fov
end

function D.focusDist(shot, t, cf)
	local fl = shot.c.focus
	if not fl then return -1 end
	local pos, look = cf.Position, cf.LookVector
	local function dist(tg)
		local p = type(tg) == "string" and D.partPos(tg, "Head") or val(tg)
		return math.max((p - pos):Dot(look), 0.3)
	end
	local k0, k1 = fl[1], fl[1]
	for i = 1, #fl - 1 do if t >= fl[i][1] then k0, k1 = fl[i], fl[i + 1] end end
	if t >= fl[#fl][1] then k0, k1 = fl[#fl], fl[#fl] end
	local a = (k1[1] > k0[1]) and math.clamp((t - k0[1]) / (k1[1] - k0[1]), 0, 1) or 0
	local d0, d1 = dist(k0[2]), dist(k1[2])
	return d0 + (d1 - d0) * E(a)
end

---------------------------------------------------------------- 샷 세팅
function D.setup(i)
	local s = D.shots[i]
	D.current = nil
	D.clearFX(); D.hideAll()
	for _, rig in ipairs(cast:GetChildren()) do D.pose(rig.Name, nil); D.handJar(rig.Name, false) end
	D.light(s.l or "night")
	D.lamps(true); D.roomJars(false); D.sky(s.sky or "some")
	if s.st then s.st() end
	s._cam = resolve(s.c, i)
	D.current = s
	return s
end
function D.preview(i, t)
	if not next(footOff) then D.init() end
	local s = D.setup(i)
	local cam = workspace.CurrentCamera
	local cf, fov = D.camCF(s, t or 0)
	cam.CFrame = cf; cam.FieldOfView = fov
	return s
end
D.shots = require(script:WaitForChild("Shots"))(D)
return D
