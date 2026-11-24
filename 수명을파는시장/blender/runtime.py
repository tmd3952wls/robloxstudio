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
def fmt_secs(v):
    v = max(0, int(math.floor(v + 1e-6)))
    h, r = divmod(v, 3600)
    m, s = divmod(r, 60)
    hs = f"{h:,}"
    return f"{hs}:{m:02d}:{s:02d}"


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
            return txt(t)
        return txt
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
        ob.matrix_world = Pm @ G @ Xg.get(pr["g"], Xg["T"]) @ pr["Mm"]
        col = pr["col"]
        hidden = False
        if bare and pr["name"] in ("LeftLowerArm", "RightLowerArm"):
            col = skin
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
        offs = Matrix.Translation(Vector((-sx / 2 - 0.012, 0, spec.get("dz", 0.0))))
        M = Pm @ G @ Xg["LA"] @ R @ offs @ frame
        num.matrix_world = M @ Matrix.Diagonal((spec.get("size", 1.0),) * 3 + (1,))
        body = _num_text(spec, t, gt)
        if num.data.body != body:
            num.data.body = body
        glow = 0.0
        for g0, g1 in spec.get("glow", []):
            glow = max(glow, _k(t, g0, g0 + 0.15) * (1 - _k(t, g1, g1 + 0.3)))
        c0, c1 = (0.025, 0.03, 0.07), (1.0, 0.62, 0.22)
        num.color = tuple(c0[i] + (c1[i] - c0[i]) * glow for i in range(3)) + (1.0,)
        num["emit"] = 6.0 * glow
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
