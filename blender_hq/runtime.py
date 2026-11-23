"""수명을 파는 시장 — 렌더 중 프레임마다 장면을 움직인다.
사용: blender --background market.blend --python runtime.py -a
"""
import bisect
import importlib
import json
import math
import os
import sys

import bpy
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

DIR = os.path.dirname(bpy.data.filepath) or os.path.dirname(os.path.abspath(__file__))
if DIR not in sys.path:
    sys.path.insert(0, DIR)
import faces  # noqa: E402
import shots as SH  # noqa: E402

_S = {"init": False}
UP = Vector((0, 0, 1))


def bpos(x, y, z):
    return Vector((x, -z, y))


def _k(t, t0, t1):
    if t1 <= t0:
        return 1.0 if t >= t0 else 0.0
    x = min(max((t - t0) / (t1 - t0), 0.0), 1.0)
    return x * x * (3 - 2 * x)


def _bump(t, t0, dur):
    if t < t0 or t > t0 + dur or dur <= 0:
        return 0.0
    return math.sin(math.pi * (t - t0) / dur)


def _rot_about(p, axis, deg):
    if abs(deg) < 1e-4:
        return Matrix.Identity(4)
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-p)


def _seed(name):
    return (sum(ord(c) * (i + 3) for i, c in enumerate(name)) % 97) / 97.0


def _init():
    sc = bpy.context.scene
    importlib.reload(SH)
    _S["chars"] = json.loads(sc["chars"])
    _S["lights"] = json.loads(sc["lights"])
    _S["dyn"] = json.loads(sc["dyn"])
    for info in _S["chars"].values():
        for p in info["parts"]:
            p["Mm"] = Matrix(p["M"])
        if info["head"]:
            info["head"]["Rm"] = Matrix(info["head"]["R"])
        if info["larm"]:
            info["larm"]["Rm"] = Matrix(info["larm"]["R"])
        info["J"] = {k: Vector(v) for k, v in info["joints"].items()}
        info["skin"] = info["parts"][info["head"]["idx"]]["col"] if info["head"] else (1, 1, 1)
    _S["shots"] = SH.SHOTS
    _S["starts"] = [s["start"] for s in SH.SHOTS]
    _S["last"] = None
    _S["vis"] = set()
    _S["init"] = True


# ------------------------------------------------------------------ 조명
def _light(scene, sh):
    O = bpy.data.objects
    mode = sh.get("light", "day")
    day = mode == "day"
    nodes = scene.world.node_tree.nodes
    nodes["DAY"].outputs[0].default_value = 1.0 if day else 0.0
    sun = O["Sun"]
    if day:
        sun.data.energy = 4.2
        sun.data.color = (1.0, 0.82, 0.62)
        sun.rotation_euler = Vector((0, 0, 1)).rotation_difference(bpos(-0.7, 0.42, 0.58).normalized()).to_euler()
    else:
        sun.data.energy = 0.0
    O["Moon"].data.energy = 0.0 if day else 0.9
    O["RoomMoon"].data.energy = 0.0 if day else 900
    for n in _S["dyn"]["Window"]:
        ob = O[n]
        ob["emit"] = 0.5 if day else 3.0
    for n in _S["dyn"]["Lamp"]:
        ob = O[n]
        ob["emit"] = 1.2 if day else 8.0
    for n in _S["lights"]:
        lo = O[n]
        ld = lo.data
        if lo["tag"] == "Lamps":
            ld.energy = ld["base_energy"] * (0.0 if day else 1.0)
        else:
            ld.energy = ld["base_energy"]
    vs = scene.view_settings
    vs.use_white_balance = True
    vs.white_balance_temperature = sh.get("temp", 6500 if day else 6800)
    vs.white_balance_tint = 10.0
    vs.exposure = (0.0 if day else 0.55) + sh.get("exp", 0.0)
    ng = scene.compositing_node_group
    if ng:
        for nd in ng.nodes:
            if nd.bl_idname == "CompositorNodeGlare":
                nd.inputs["Strength"].default_value = sh.get("bloom", 0.45 if day else 0.65)


# ------------------------------------------------------------------ 카메라
def _cam(scene, sh, t):
    keys = sh["cam"]
    k0, k1 = keys[0], keys[0]
    for i in range(len(keys) - 1):
        if t >= keys[i][0]:
            k0, k1 = keys[i], keys[i + 1]
    if t >= keys[-1][0]:
        k0, k1 = keys[-1], keys[-1]
    a = 0.0 if k1[0] <= k0[0] else min(max((t - k0[0]) / (k1[0] - k0[0]), 0.0), 1.0)
    e = sh.get("ease", "smooth")
    if e == "smooth":
        a = a * a * (3 - 2 * a) * 0.5 + a * 0.5
    elif e == "out":
        a = 1 - (1 - a) ** 3
    p = bpos(*k0[1]).lerp(bpos(*k1[1]), a)
    l = bpos(*k0[2]).lerp(bpos(*k1[2]), a)
    fov = k0[3] + (k1[3] - k0[3]) * a
    d = l - p
    w = min(0.0012 * d.length, 0.06) * sh.get("shake", 1.0)
    gt = sh["start"] + t
    p = p + Vector((math.sin(gt * 2.1) * w, math.sin(gt * 1.7 + 1) * w, math.sin(gt * 2.9 + 2) * w * 0.7))
    q = (l - p).to_track_quat("-Z", "Y")
    roll = sh.get("roll", 0.0)
    M = Matrix.Translation(p) @ q.to_matrix().to_4x4() @ Matrix.Rotation(math.radians(roll), 4, "Z")
    cam = scene.camera
    cam.matrix_world = M
    cam.data.angle = math.radians(fov)
    dof = cam.data.dof
    fd = sh.get("focus")
    dof.focus_distance = max(0.2, (l - p).length if fd is None else fd)
    dof.aperture_fstop = sh.get("fstop", 2.8 if (l - p).length < 6 else 8.0)


# ------------------------------------------------------------------ 숫자
def fmt_secs(v, two_line=True):
    """남은 수명을 '20일 / 17:56:59' (일 + 시:분:초) 로. 한 줄이 필요하면 two_line=False."""
    v = max(0, int(math.floor(v + 1e-6)))
    d, r = divmod(v, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    return f"{d:,}일" + ("\n" if two_line else " ") + f"{h:02d}:{m:02d}:{s:02d}"


_HMS = __import__("re").compile(r"(\d[\d,]*):(\d\d):(\d\d)")


def to_days(txt):
    """'8,760,000:00:00' 처럼 시간 단위로 적힌 글자를 일 표시로 바꾼다. 한 줄짜리는 두 줄(일 / 시:분:초)로."""
    lines = txt.split("\n")
    one = len(lines) == 1

    def rep(mt):
        h = int(mt.group(1).replace(",", ""))
        return fmt_secs(h * 3600 + int(mt.group(2)) * 60 + int(mt.group(3)), two_line=one)
    return "\n".join(_HMS.sub(rep, ln) for ln in lines)


def fit_size(txt, w, h):
    """팔 바깥면(가로 w, 세로 h)에 꽉 차되 넘치지 않는 글자 크기."""
    lines = txt.split("\n")

    def lw(ln):
        return sum(1.08 if ord(c) > 0x3000 else 0.4 if c in ",: " else 0.82 for c in ln)
    widest = max(lw(ln) for ln in lines) or 1.0
    return min(0.62 * w / widest, 0.8 * h / (len(lines) * 1.15), 0.34)


GLYPH = {}   # hq_upgrade.numbers() 가 실제 글꼴로 잰 글자 폭(크기 1 기준)


def _text_em(txt):
    """글자 크기 1 일 때 (가장 긴 줄 폭, 전체 높이)."""
    lines = txt.split("\n")
    if GLYPH:
        w = GLYPH["w"]
        widest = max(sum(w.get(c, w["0"]) for c in ln) for ln in lines)
        return widest, GLYPH["h"] + GLYPH["pitch"] * (len(lines) - 1)
    widest = max(sum(1.08 if ord(c) > 0x3000 else 0.4 if c in ",: " else 0.82 for c in ln) for ln in lines) * 0.6
    return widest, 0.75 + 1.15 * (len(lines) - 1)


def _num_fit(info, M, body, la):
    """M(숫자 판 좌표, x=팔 길이 방향 손목->팔꿈치, y=팔 둘레)에서 보이는 맨살 구간을 재서 (글자 크기, 중심 x, 중심 y)."""
    O = bpy.data.objects
    Mi = M.inverted()
    ext = {}
    for pr in info["parts"]:
        if pr["name"] in ("LeftUpperArm", "LeftLowerArm", "LeftHand"):
            ob = O[pr["ob"]]
            Mw = Mi @ ob.matrix_world
            pts = [Mw @ Vector(c) for c in ob.bound_box]
            ext[pr["name"]] = (min(p.x for p in pts), max(p.x for p in pts), min(p.y for p in pts), max(p.y for p in pts))
    lo = ext.get("LeftLowerArm")
    if not lo:
        return fit_size(body, la["size"][2], la["size"][1]), -0.15, 0.0
    a, b = lo[0], lo[1]
    if "LeftHand" in ext:
        h = ext["LeftHand"]
        if h[1] < b and h[1] > a:   # 손이 손목 쪽 끝을 덮음
            a = h[1]
    if "LeftUpperArm" in ext:
        u = ext["LeftUpperArm"]
        if u[0] > a and u[0] < b:   # 소매가 팔꿈치 쪽 끝을 덮음
            b = u[0]
    span = b - a
    W = span * 0.70                   # 맨살 구간의 70%
    H = (lo[3] - lo[2]) * 0.78
    tw, th = _text_em(body)
    fs = min(W / max(tw, 1e-6), H / max(th, 1e-6), 0.34)
    # 클로즈업 카메라가 소매 쪽을 비추므로 글자는 소매 바로 옆(여백 7%)에 붙임
    cx = b - span * 0.07 - tw * fs / 2
    return fs, cx, (lo[2] + lo[3]) / 2


def _num_value(spec, t, gt):
    if "keys" in spec:
        ks = spec["keys"]
        if t <= ks[0][0]:
            v = ks[0][1]
        elif t >= ks[-1][0]:
            v = ks[-1][1]
        else:
            for (t0, v0), (t1, v1) in zip(ks, ks[1:]):
                if t0 <= t <= t1:
                    e = spec.get("ease", "lin")
                    a = (t - t0) / max(t1 - t0, 1e-6)
                    if e == "smooth":
                        a = a * a * (3 - 2 * a)
                    elif e == "step":
                        a = 0.0
                    v = v0 + (v1 - v0) * a
                    break
        return v + spec.get("rate", 0.0) * (t - ks[0][0]) if spec.get("tick") else v
    return spec.get("v", 0) + spec.get("rate", -1.0) * t


def _num_text(spec, t, gt):
    if "text" in spec:
        txt = spec["text"]
        if callable(txt):
            txt = txt(t)
        return to_days(txt)
    return fmt_secs(_num_value(spec, t, gt))


# ------------------------------------------------------------------ 연기
def _perf(name, a, t, gt):
    acts = a.get("acts", [])
    sd = _seed(name)
    tau = 2 * math.pi
    P = {"bob": 0.012 * math.sin(tau * 0.35 * gt + sd * 6), "pitch": 0.0, "yaw": 1.5 * math.sin(tau * 0.22 * gt + sd * 5),
         "roll": 0.0, "arm_up": 0.0, "walk": 0.0,
         "LA": [3 * math.sin(tau * 0.4 * gt + sd * 4), -4.0, 0.0], "RA": [3 * math.sin(tau * 0.4 * gt + sd * 4 + 1.3), 4.0, 0.0],
         "LL": [0.0, 0.0], "RL": [0.0, 0.0], "expr": a.get("face", "기본 미소")}
    cyc = 0.0
    if a.get("lie"):
        P["bob"] *= 0.3
        P["yaw"] = 0.0
        P["LA"] = [0.0, -3.0, 0.0]
        P["RA"] = [0.0, 3.0, 0.0]
    for ac in acts:
        k = ac[0]
        if k == "walk":            # ("walk", 속도, 시작)
            t0 = ac[2] if len(ac) > 2 else 0.0
            tt = max(t - t0, 0.0)
            P["walk"] = ac[1] * (tt - 0.1) if tt > 0.2 else ac[1] * tt * tt / 0.4
            cyc = max(cyc, ac[1] * min(tt / 0.2, 1.0))
        elif k == "wave":          # ("wave", "R", 시작, 횟수)
            s = 1 if ac[1] == "R" else -1
            t0, n = ac[2], (ac[3] if len(ac) > 3 else 2)
            span = 0.2 + 0.4 * n
            e = _k(t, t0, t0 + 0.2) * (1 - _k(t, t0 + span, t0 + span + 0.25))
            ph = max(t - t0 - 0.2, 0.0)
            wv = 18 * math.sin(tau * 2.5 * ph) if ph < 0.4 * n else 0.0
            arm = P["RA" if s > 0 else "LA"]
            arm[0] = arm[0] * (1 - e) + 12 * e
            arm[1] = arm[1] * (1 - e) + s * (150 + wv) * e
        elif k == "arm":           # ("arm", "L", 앞각도, 옆각도, 시작, 걸리는시간, [내리는 시각], [안쪽각도])
            s = 1 if ac[1] == "R" else -1
            e = _k(t, ac[4], ac[4] + ac[5])
            if len(ac) > 6 and ac[6] is not None:
                e *= 1 - _k(t, ac[6], ac[6] + ac[5])
            arm = P["RA" if s > 0 else "LA"]
            arm[0] = arm[0] * (1 - e) + ac[2] * e
            arm[1] = arm[1] * (1 - e) + s * ac[3] * e
            if len(ac) > 7:
                arm[2] = arm[2] * (1 - e) + s * ac[7] * e
        elif k == "arms_up":
            e = _k(t, ac[1], ac[1] + 0.2)
            P["LA"] = [20 * e + P["LA"][0] * (1 - e), -140 * e + P["LA"][1] * (1 - e)]
            P["RA"] = [20 * e + P["RA"][0] * (1 - e), 140 * e + P["RA"][1] * (1 - e)]
            P["pitch"] += 8 * e
        elif k == "look":          # ("look", 위아래, 좌우, 시작, 끝)
            e = _k(t, ac[3], ac[4])
            P["pitch"] += ac[1] * e
            P["yaw"] += ac[2] * e
        elif k == "nod":
            P["pitch"] -= ac[1] * _bump(t, ac[2], ac[3])
        elif k == "shake":         # ("shake", 각도, 시작, 길이)
            if ac[2] <= t <= ac[2] + ac[3]:
                P["yaw"] += ac[1] * math.sin(tau * 3 * (t - ac[2])) * math.sin(math.pi * (t - ac[2]) / ac[3])
        elif k == "tilt":
            P["roll"] += ac[1] * _k(t, ac[2], ac[3])
        elif k == "bounce":
            t0, n = ac[2], (ac[3] if len(ac) > 3 else 1)
            b = sum(_bump(t, t0 + i * 0.32, 0.3) for i in range(n))
            P["bob"] += ac[1] * b
        elif k == "shrug":
            e = _k(t, ac[1], ac[1] + 0.15) * (1 - _k(t, ac[1] + 0.4, ac[1] + 0.6))
            P["arm_up"] = 0.2 * e
            P["LA"] = [P["LA"][0] + 20 * e, P["LA"][1] - 25 * e]
            P["RA"] = [P["RA"][0] + 20 * e, P["RA"][1] + 25 * e]
        elif k == "jerk":
            dt = t - ac[1]
            amp = ac[2] if len(ac) > 2 else 1.0
            if dt > 0:
                pulse = dt / 0.06 if dt < 0.06 else math.exp(-(dt - 0.06) * 9)
                P["pitch"] += 12 * amp * pulse
                P["bob"] += 0.06 * amp * pulse
        elif k == "lean":          # ("lean", 각도, 시작, 끝)  몸 전체 앞으로 기울이기
            P["lean"] = P.get("lean", 0.0) + ac[1] * _k(t, ac[2], ac[3])
        elif k == "expr":
            cur = None
            for tt, nm in ac[1]:
                if t >= tt:
                    cur = nm
            if cur:
                P["expr"] = cur
        elif k == "freeze":
            w = 1 - _k(t, ac[1], ac[1] + 0.2)
            P["bob"] *= w
            P["yaw"] *= w
    if a.get("_speed", 0) > 0.3:
        cyc = max(cyc, a["_speed"])
    if cyc > 0:
        dist = a.get("_dist", P["walk"])
        ph = tau * dist / 4.5
        amp = min(1.0, cyc / 3)
        leg = 28 * amp
        P["LL"][0] = leg * math.sin(ph)
        P["RL"][0] = -leg * math.sin(ph)
        if not any(ac[0] == "arm" and ac[1] == "L" for ac in acts):
            P["LA"][0] += -0.8 * leg * math.sin(ph)
        if not any(ac[0] == "arm" and ac[1] == "R" for ac in acts):
            P["RA"][0] += 0.8 * leg * math.sin(ph)
        P["bob"] += 0.1 * amp * abs(math.sin(ph))
    period = 2.4 + sd * 1.6
    P["blink"] = ((gt + sd * 3.1) % period) < 0.12
    return P


def _path(a, t):
    """배우 위치 (x, z, yaw) + 속도·누적거리"""
    ks = a.get("path")
    if not ks:
        return a.get("x", 0.0), a.get("z", 0.0), a.get("yaw", 0.0), 0.0, 0.0
    if t <= ks[0][0]:
        k = ks[0]
        return k[1], k[2], k[3], 0.0, 0.0
    dist = 0.0
    for k0, k1 in zip(ks, ks[1:]):
        seg = math.hypot(k1[1] - k0[1], k1[2] - k0[2])
        if t <= k1[0]:
            u = (t - k0[0]) / max(k1[0] - k0[0], 1e-6)
            x = k0[1] + (k1[1] - k0[1]) * u
            z = k0[2] + (k1[2] - k0[2]) * u
            yaw = k0[3] + (k1[3] - k0[3]) * min(1.0, u * 3)
            sp = seg / max(k1[0] - k0[0], 1e-6)
            return x, z, yaw, sp, dist + seg * u
        dist += seg
    k = ks[-1]
    return k[1], k[2], k[3], 0.0, dist


def _bare(a, t):
    b = a.get("bare", False)
    if isinstance(b, list):
        cur = False
        for tt, v in b:
            if t >= tt:
                cur = v
        return cur
    return bool(b)


_THIN = {}
THIN_S = 0.96


def _thin(ob):
    """메시 로컬 bbox 중심 기준, 가장 긴 축(팔 길이)은 그대로 두고 나머지 두 축만 THIN_S 배."""
    key = ob.data.name
    if key not in _THIN:
        bb = [Vector(c) for c in ob.bound_box]
        lo = Vector((min(v[i] for v in bb) for i in range(3)))
        hi = Vector((max(v[i] for v in bb) for i in range(3)))
        c, d = (lo + hi) / 2, hi - lo
        L = max(range(3), key=lambda i: d[i])
        s = [THIN_S] * 3
        s[L] = 1.0
        _THIN[key] = Matrix.Translation(c) @ Matrix.Diagonal((s[0], s[1], s[2], 1)) @ Matrix.Translation(-c)
    return _THIN[key]


def _actor(name, a, t, gt):
    O = bpy.data.objects
    info = _S["chars"][name]
    x, z, yaw, sp, dist = _path(a, t)
    a["_speed"], a["_dist"] = sp, dist
    y = a.get("y", 0.4 if abs(x) < 11.2 and abs(z) < 150 and x < 300 else 0.6 if x < 300 else 0.0)
    sc = a.get("scale", 1.0)
    Pm = Matrix.Translation(bpos(x, y, z)) @ Matrix.Rotation(math.radians(yaw - 180), 4, "Z")
    if a.get("lie"):
        Pm = Pm @ Matrix.Rotation(math.radians(90), 4, "X")
    if sc != 1.0:
        Pm = Pm @ Matrix.Diagonal((sc, sc, sc, 1))
    P = _perf(name, a, t, gt)
    J = info["J"]
    X, UPv, FWD = Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, 1, 0))
    G = Matrix.Translation(FWD * P["walk"] + Vector((0, 0, P["bob"])))
    if P.get("lean"):
        G = G @ Matrix.Rotation(math.radians(-P["lean"]), 4, "X")
    Xg = {"T": Matrix.Identity(4)}
    for side in ("LA", "RA", "LL", "RL"):
        ang = P[side]
        p = J[side]
        M = _rot_about(p, FWD, -ang[1]) @ _rot_about(p, X, ang[0])
        if len(ang) > 2 and ang[2]:
            M = _rot_about(p, UPv, ang[2]) @ M
        if side in ("LA", "RA") and P["arm_up"]:
            M = Matrix.Translation(UPv * P["arm_up"]) @ M
        Xg[side] = M
    p = J["HD"]
    Xg["HD"] = _rot_about(p, UPv, P["yaw"]) @ _rot_about(p, X, P["pitch"]) @ _rot_about(p, FWD, P["roll"])
    bare = _bare(a, t)
    skin = info["skin"]
    tint = a.get("tint")
    for pi, pr in enumerate(info["parts"]):
        ob = O[pr["ob"]]
        Mw = Pm @ G @ Xg.get(pr["g"], Xg["T"]) @ pr["Mm"]
        col = pr["col"]
        hidden = False
        if bare and pr["name"] in ("LeftLowerArm", "RightLowerArm"):
            col = skin
            # 소매(윗팔)와 겹치는 면이 같은 자리라 프레임마다 깜빡임(z-fighting) -> 맨살 팔을 굵기 방향으로만 살짝 줄여 소매 안쪽으로
            Mw = Mw @ _thin(ob)
        ob.matrix_world = Mw
        if bare and "Cuff" in pr["name"]:
            hidden = True
        if tint and pr["g"] == "T" and pr["name"] in ("UpperTorso", "LowerTorso"):
            col = tint
        ob.color = (col[0], col[1], col[2], pr["a"])
        ob.hide_render = hidden
    # 얼굴
    if info["head"]:
        headM = Pm @ G @ Xg["HD"] @ info["head"]["Rm"]
        if sc != 1.0:
            # 표정 조각은 크기 없는 행렬을 받으므로 머리 크기를 비율로 넘김
            loc, rot, _ = headM.decompose()
            headM = Matrix.Translation(loc) @ rot.to_matrix().to_4x4()
            hs = tuple(v * sc for v in info["head"]["size"])
        else:
            hs = info["head"]["size"]
        faces._draw_face(info, headM, hs, P["expr"], P["blink"] and not P["expr"].endswith("|closed"))
    # 팔 숫자
    num = O[info["num"]]
    spec = a.get("num")
    if spec and bare and info["larm"]:
        la = info["larm"]
        sx = la["size"][0]
        R = la["Rm"]
        frame = Matrix(((0, 0, -1), (0, 1, 0), (1, 0, 0))).to_4x4()   # 열: 읽는 방향 +Z(손목->팔꿈치), +Y, 바깥(-X)
        offs = Matrix.Translation(Vector((-sx * THIN_S / 2 - 0.012, 0, spec.get("dz", 0.0))))
        M = Pm @ G @ Xg["LA"] @ R @ offs @ frame
        body = _num_text(spec, t, gt)
        if num.data.body != body:
            num.data.body = body
        # 보이는 맨살 = 아랫팔 중 손(손목 쪽)과 소매(윗팔) 사이. 그 안에만 들어가게 크기·위치를 맞춤
        fs, cx, cy = _num_fit(info, M, body, la)
        sz = fs / max(num.data.size, 1e-6)
        num.matrix_world = M @ Matrix.Translation(Vector((cx, cy, 0))) @ Matrix.Diagonal((sz, sz, sz, 1))
        glow = 0.0
        for g0, g1 in spec.get("glow", []):
            glow = max(glow, _k(t, g0, g0 + 0.15) * (1 - _k(t, g1, g1 + 0.3)))
        # 초가 넘어갈 때마다 숫자만 살짝 반짝 (팔은 그대로)
        tick = 0.0
        if "keys" not in spec and "text" not in spec:
            ph = (spec.get("v", 0) + spec.get("rate", -1.0) * t) % 1.0
            tick = math.exp(-(1.0 - ph) * 9.0) if spec.get("rate", -1.0) < 0 else 0.0
        c0, c1 = (0.02, 0.025, 0.06), (1.0, 0.62, 0.22)
        num.color = tuple(c0[i] + (c1[i] - c0[i]) * glow for i in range(3)) + (1.0,)
        num["emit"] = 6.0 * glow + 1.6 * tick
        num.hide_render = False
    else:
        num.hide_render = True
    return Pm, G, Xg


def _hide(name):
    O = bpy.data.objects
    info = _S["chars"][name]
    for pr in info["parts"]:
        O[pr["ob"]].hide_render = True
    for lst in info["pool"].values():
        for n in lst:
            O[n].hide_render = True
    O[info["num"]].hide_render = True


def _door(sh, t):
    O = bpy.data.objects
    for n in _S["dyn"]["Door"]:
        ob = O[n]
        M0 = Matrix(ob["base_M"])
        d = sh.get("door")
        ang = 0.0
        if d:
            ang = d[2] * _k(t, d[0], d[1])
        hinge = M0.translation + Vector((0, 1.8, 0))
        ob.matrix_world = _rot_about(hinge, UP, ang) @ M0


def _glow(sh, t, poses):
    O = bpy.data.objects
    gl = O["TouchGlow"]
    g = sh.get("touchglow")
    if not g:
        gl.data.energy = 0.0
        return
    t0, t1, who, energy = g
    info = _S["chars"].get(who)
    if who not in poses or not info:
        gl.data.energy = 0.0
        return
    Pm, G, Xg = poses[who]
    for pr in info["parts"]:
        if pr["name"] == "LeftHand":
            gl.location = (Pm @ G @ Xg["LA"] @ pr["Mm"]).translation
    gl.data.energy = energy * _k(t, t0, t0 + 0.3) * (1 - _k(t, t1, t1 + 0.4))


@persistent
def film_frame(scene, depsgraph=None):
    if not _S["init"]:
        _init()
    ff = scene.frame_current + scene.frame_subframe
    T = max(ff - 1, 0) / 30.0
    i = max(0, bisect.bisect_right(_S["starts"], T + 1e-6) - 1)
    sh = _S["shots"][i]
    t = T - sh["start"]
    if _S["last"] != i:
        _light(scene, sh)
        _S["last"] = i
    gt = T
    present = set()
    poses = {}
    for name, a in sh["actors"].items():
        if name not in _S["chars"]:
            continue
        poses[name] = _actor(name, a, t, gt)
        present.add(name)
    for name in _S["vis"] - present:
        _hide(name)
    _S["vis"] = present
    _door(sh, t)
    _glow(sh, t, poses)
    _cam(scene, sh, t)
    rb = bpy.data.objects.get("RuleBoard")
    show_rule = sh.get("rule", False)
    for n in ("RuleBoard", "RuleText", "RulePost", "RulePost.001"):
        ob = bpy.data.objects.get(n)
        if ob:
            ob.hide_render = not show_rule


@persistent
def film_load(_dummy=None):
    _S["init"] = False


def register():
    for lst in (bpy.app.handlers.frame_change_pre, bpy.app.handlers.load_post):
        for hnd in list(lst):
            if getattr(hnd, "__name__", "") in ("film_frame", "film_load"):
                lst.remove(hnd)
    bpy.app.handlers.frame_change_pre.append(film_frame)
    bpy.app.handlers.load_post.append(film_load)
    _S["init"] = False


register()
