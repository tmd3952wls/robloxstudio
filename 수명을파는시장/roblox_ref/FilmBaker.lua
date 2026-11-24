-- (별이떨어지는마을 원본, ServerStorage.FilmBaker)
-- 블렌더 이전용: 샷을 프레임 단위로 돌려 카메라·배우·별 효과·세트 상태를 기록한다.
local RS = game:GetService("ReplicatedStorage")
local CS = game:GetService("CollectionService")
local ES = game:GetService("EncodingService")
local D = require(RS.FilmDirector)
local fmt = string.format
local M = {}

local function quat(cf)
	local _, _, _, m00, m01, m02, m10, m11, m12, m20, m21, m22 = cf:GetComponents()
	local tr = m00 + m11 + m22
	local w, x, y, z
	if tr > 0 then local s = math.sqrt(tr + 1) * 2; w = 0.25 * s; x = (m21 - m12) / s; y = (m02 - m20) / s; z = (m10 - m01) / s
	elseif m00 > m11 and m00 > m22 then local s = math.sqrt(1 + m00 - m11 - m22) * 2; w = (m21 - m12) / s; x = 0.25 * s; y = (m01 + m10) / s; z = (m02 + m20) / s
	elseif m11 > m22 then local s = math.sqrt(1 + m11 - m00 - m22) * 2; w = (m02 - m20) / s; x = (m01 + m10) / s; y = 0.25 * s; z = (m12 + m21) / s
	else local s = math.sqrt(1 + m22 - m00 - m11) * 2; w = (m10 - m01) / s; x = (m02 + m20) / s; y = (m12 + m21) / s; z = 0.25 * s end
	return w, x, y, z
end
M.quat = quat
local function hex(c) return fmt("%02x%02x%02x", math.floor(c.R * 255 + 0.5), math.floor(c.G * 255 + 0.5), math.floor(c.B * 255 + 0.5)) end
M.hex = hex
local function kind(p)
	if p:IsA("WedgePart") then return "W" elseif p:IsA("CornerWedgePart") then return "K"
	elseif p:IsA("MeshPart") then
		if p.Name == "Head" then return "H" elseif p.Name == "Handle" then return "A" end
		return "M"
	elseif p:IsA("UnionOperation") then return "U"
	elseif p:IsA("Part") then
		if p.Shape == Enum.PartType.Ball then return "S" elseif p.Shape == Enum.PartType.Cylinder then return "C" end
	end
	return "B"
end
M.kind = kind
local function partLine(p, idx, isFace, cfOverride)
	local c = cfOverride or p.CFrame; local w, x, y, z = quat(c)
	return fmt("%d|%d|%s|%.2f,%.2f,%.2f|%.2f,%.2f,%.2f|%.4f,%.4f,%.4f,%.4f|%s|%s|%.2f", idx, isFace and 1 or 0, kind(p),
		p.Size.X, p.Size.Y, p.Size.Z, c.X, c.Y, c.Z, w, x, y, z, hex(p.Color), p.Material.Name, p.Transparency)
end
-- 편집 모드에서는 관절을 못 움직이므로 팔 자세를 직접 계산
local POSES = {
	hold = {CFrame.Angles(math.rad(80), 0, 0), nil},
	ear = {CFrame.Angles(math.rad(70), 0, math.rad(-12)), CFrame.Angles(math.rad(115), 0, 0)},
}
local function poseOverrides(rig)
	local ov = {}
	local pose = POSES[rig:GetAttribute("Pose") or ""]
	if not pose then return ov end
	local ok = pcall(function()
		local ut, ua, la, hand = rig.UpperTorso, rig.LeftUpperArm, rig.LeftLowerArm, rig.LeftHand
		local sh, el = ua.LeftShoulder, la.LeftElbow
		local J = ut.CFrame * sh.C0
		local Rsh = J * pose[1] * J:Inverse()
		local lower = {la, hand}
		local hj = rig:FindFirstChild("HandJar")
		if hj then for _, p in ipairs(hj:GetDescendants()) do if p:IsA("BasePart") then table.insert(lower, p) end end end
		ov[ua] = Rsh * ua.CFrame
		local Rel = Rsh
		if pose[2] then
			local Je = Rsh * (ua.CFrame * el.C0)
			Rel = Je * pose[2] * Je:Inverse() * Rsh
		end
		for _, p in ipairs(lower) do ov[p] = Rel * p.CFrame end
	end)
	return ok and ov or {}
end
local function snapshot(rig)
	local face = rig:FindFirstChild("Face")
	local ov = poseOverrides(rig)
	local out, i, fi = {}, 0, 0
	for _, p in ipairs(rig:GetDescendants()) do
		if p:IsA("BasePart") and p.Name ~= "HumanoidRootPart" then
			if face and p:IsDescendantOf(face) then fi += 1; table.insert(out, partLine(p, fi, true))
			else i += 1; table.insert(out, partLine(p, i, false, ov[p])) end
		end
	end
	return table.concat(out, "~")
end
local function signature(rig)
	local root = rig:GetPivot()
	local face = rig:FindFirstChild("Face")
	local lh = rig:FindFirstChild("LeftHand")
	local hj = rig:FindFirstChild("HandJar")
	local rel = lh and root:PointToObjectSpace(lh.Position) or Vector3.zero
	return (rig:GetAttribute("Pose") or "") .. fmt("%s|%s|%.2f,%.2f,%.2f|%.2f,%.2f,%.2f|%s|%s", face and (face:GetAttribute("Expression") or "") or "", hex(rig.Head.Color),
		root.X, root.Y, root.Z, rel.X, rel.Y, rel.Z,
		hj and tostring(hj.Lid.Transparency) or "", hj and tostring(hj.Glass.Transparency) or "")
end
local function worldState(s)
	local lamps, room = "1", "0"
	for _, jar in ipairs(CS:GetTagged("StarJar")) do
		local st = jar:FindFirstChild("Star")
		if st then
			if CS:HasTag(jar, "RoomJar") then room = (st.Transparency > 0.5) and "1" or "0"
			else lamps = (st.Transparency > 0.5) and "0" or "1" end
		end
	end
	return (s.l or "night"), (s.sky or "some"), lamps, room
end

-- 샷 i0..i1 기록. frameStart 는 앞 샷들의 프레임 수 누적
function M.bake(i0, i1)
	D.init()
	local frameStart = 0
	for i = 1, i0 - 1 do frameStart += math.floor((D.shots[i].dn or D.shots[i].d) * 30 + 0.5) end
	local out = {}
	for i = i0, i1 do
		local s = D.setup(i)
		local n = math.floor((s.dn or s.d) * 30 + 0.5)
		local k = s.k or (s.d * 30 / n)      -- 새 프레임 1개 = 연출 시간 k/30 초
		local light, sky, lamps, room = worldState(s)
		table.insert(out, fmt("S|%d|%d|%d|%s|%s|%s|%s|%.6f", i, frameStart, n, light, sky, lamps, room, k))
		local last = {}
		local starDecl = false
		for f = 0, n - 1 do
			local t = f / 30 * k
			D.update(f == 0 and 0 or k / 30, t)
			local cf, fov = D.camCF(s, t)
			cf = cf * CFrame.Angles(0, 0, -math.rad(90))   -- Studio용 눕힘 제거 (기울임은 유지)
			local w, x, y, z = quat(cf)
			local fd = D.focusDist(s, t, cf)
			table.insert(out, fmt("c|%d|%.3f,%.3f,%.3f|%.5f,%.5f,%.5f,%.5f|%.2f|%.2f|%.1f", f, cf.X, cf.Y, cf.Z, w, x, y, z, fov, fd, s.c.fstop or 0))
			local fx = workspace:FindFirstChild("FilmFX")
			if fx then
				local kids = fx:GetChildren()
				if #kids > 0 then
					if not starDecl then
						local decl = {}
						for _, p in ipairs(kids) do table.insert(decl, fmt("%.2f,%d", p.Size.X, p:FindFirstChildOfClass("Trail") and 1 or 0)) end
						table.insert(out, "d|" .. table.concat(decl, ";"))
						starDecl = true
					end
					local pos = {}
					for _, p in ipairs(kids) do
						if p.Transparency > 0.5 then table.insert(pos, "-")
						else table.insert(pos, fmt("%.2f,%.2f,%.2f", p.Position.X, p.Position.Y, p.Position.Z)) end
					end
					table.insert(out, "f|" .. table.concat(pos, ";"))
				end
			end
			for _, rig in ipairs(workspace.Cast:GetChildren()) do
				if rig:GetPivot().Y > -100 then
					local sig = signature(rig)
					if last[rig.Name] ~= sig then
						last[rig.Name] = sig
						table.insert(out, fmt("k|%d|%s|", f, rig.Name) .. snapshot(rig))
					end
				end
			end
		end
		frameStart += n
		task.wait()
	end
	return table.concat(out, "\n"), frameStart
end

-- 고정 세트(마을) 내보내기. 바뀌는 조각에는 dyn 표시
function M.world()
	D.init(); D.setup(3)
	local lines, lights, texts = {}, {}, {}
	local function dyn(p)
		local par = p.Parent
		if par and CS:HasTag(par, "StarJar") then
			if p.Name == "Star" then return CS:HasTag(par, "RoomJar") and "RoomStar" or "LampStar" end
			if p.Name == "Lid" and CS:HasTag(par, "RoomJar") then return "RoomLid" end
		end
		if CS:HasTag(p, "DressStar") then return "LampStar" end
		if CS:HasTag(p, "WindowPane") then return "Window" end
		if CS:HasTag(p, "GlowLoaf") then return "Loaf" end
		return "-"
	end
	local function add(p, tag)
		if p.Transparency >= 0.99 then return end
		local c = p.CFrame; local w, x, y, z = quat(c)
		table.insert(lines, fmt("%s|%s|%.2f,%.2f,%.2f|%.2f,%.2f,%.2f|%.4f,%.4f,%.4f,%.4f|%s|%s|%.2f|%s", kind(p), tag,
			p.Size.X, p.Size.Y, p.Size.Z, c.X, c.Y, c.Z, w, x, y, z, hex(p.Color), p.Material.Name, p.Transparency, dyn(p)))
		for _, l in ipairs(p:GetChildren()) do
			if (l:IsA("PointLight") or l:IsA("SpotLight") or l:IsA("SurfaceLight")) then
				table.insert(lights, fmt("%.2f,%.2f,%.2f|%s|%.2f|%.1f|%s", c.X, c.Y, c.Z, hex(l.Color), l.Brightness, l.Range, dyn(p)))
			end
			if l:IsA("SurfaceGui") then
				local tl = l:FindFirstChildOfClass("TextLabel")
				if tl then table.insert(texts, fmt("%s|%.2f,%.2f,%.2f|%.2f,%.2f,%.2f|%.4f,%.4f,%.4f,%.4f|%s", l.Face.Name, p.Size.X, p.Size.Y, p.Size.Z, c.X, c.Y, c.Z, w, x, y, z, (tl.Text:gsub("\n", "\\n")))) end
			end
		end
	end
	for _, ch in ipairs(workspace.Town:GetChildren()) do
		if ch.Name ~= "SkyStars" then
			if ch:IsA("BasePart") then add(ch, ch.Name) else for _, p in ipairs(ch:GetDescendants()) do if p:IsA("BasePart") then add(p, ch.Name) end end end
		end
	end
	local rp = RaycastParams.new(); rp.FilterType = Enum.RaycastFilterType.Include; rp.FilterDescendantsInstances = {workspace.Terrain}
	local MAT = {Grass = "g", LeafyGrass = "l", Rock = "r", Snow = "s", Ground = "d"}
	local trows = {}
	local X0, X1, Z0, Z1, STEP = -320, 320, -660, 260, 8
	for z = Z0, Z1, STEP do
		local row = {}
		for x = X0, X1, STEP do
			local r = workspace:Raycast(Vector3.new(x, 400, z), Vector3.new(0, -500, 0), rp)
			table.insert(row, r and fmt("%d%s", math.floor(r.Position.Y * 10 + 0.5), MAT[r.Material.Name] or "g") or "0g")
		end
		table.insert(trows, table.concat(row, ","))
	end
	return table.concat({"L;" .. table.concat(lights, ";"), "X;" .. table.concat(texts, ";"),
		fmt("T;%d;%d;%d;%d;%d;", X0, X1, Z0, Z1, STEP) .. table.concat(trows, ";"), "P;" .. table.concat(lines, "\n")}, "\n#\n")
end

function M.pack(text)
	local c = ES:CompressBuffer(buffer.fromstring(text), Enum.CompressionAlgorithm.Zstd, 19)
	return "B64START" .. buffer.tostring(ES:Base64Encode(c)) .. "B64END", #text, buffer.len(c)
end
return M
