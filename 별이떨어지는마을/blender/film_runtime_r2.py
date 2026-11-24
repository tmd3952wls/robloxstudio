"""별이 떨어지는 마을 — 렌더 중 프레임마다 장면을 움직이는 실행 스크립트.

film_data.pkl 을 읽어 프레임마다 카메라, 배우(자세·표정), 별 효과, 낮/밤, 가로등, 초점을 맞춘다.
모션 블러용 중간 프레임(서브프레임)도 이어지게 보간한다.

사용법:
  blender --background town_film.blend --python film_runtime.py -a
"""
import bisect
import math
import os
import pickle

import bpy
from bpy.app.handlers import persistent
from mathutils import Matrix, Quaternion, Vector

_S = {"data": None, "starts": None, "last_shot": None, "char_key": {}}
STAR_THRESH = {"few": 0.985, "some": 0.86, "full": 0.6}
UP = Vector((0, 0, 1))


def _load(scene):
    path = scene.get("film_data", "")
    if not path or not os.path.exists(path):
        path = os.path.join(os.path.dirname(bpy.data.filepath), "film_data.pkl")
    with open(path, "rb") as f:
        _S["data"] = pickle.load(f)
    _S["starts"] = [s["start"] for s in _S["data"]["shots"]]
    _S["last_shot"] = None
    _S["char_key"] = {}


def _mat(name):
    return bpy.data.materials.get(name) or bpy.data.materials.get("R_SmoothPlastic_C")


def _shot_state(scene, sh, data):
    O = bpy.data.objects
    day = sh["day"]
    nodes = scene.world.node_tree.nodes
    nodes["DAY"].outputs[0].default_value = 1.0 if day else 0.0
    nodes["STARS"].outputs[0].default_value = STAR_THRESH.get(sh["sky"], 0.86)
    far = bpy.data.materials.get("FarMtn")
    if far:
        far.node_tree.nodes["DAY"].outputs[0].default_value = 1.0 if day else 0.0
    O["Sun"].data.energy = 3.5 if day else 0.0
    O["Moon"].data.energy = 0.0 if day else 1.1
    scene.view_settings.exposure = -0.3 if day else 0.4
    lamps_on, room_open = sh["lamps"], sh["room_open"]
    for n in data["dyn"]["LampStar"]:
        O[n].hide_render = not lamps_on
    for n in data["dyn"]["RoomStar"] + data["dyn"]["RoomLid"]:
        O[n].hide_render = room_open
    for n in data["dyn"]["Window"]:
        ob = O[n]
        ob["emit"] = 0.0 if day else 3.2
        ob.update_tag()
    for n in data["lights"]["LampStar"]:
        ld = O[n].data
        ld.energy = ld["base_energy"] if (lamps_on and not day) else 0.0
    for n in data["lights"]["RoomStar"]:
        ld = O[n].data
        ld.energy = 0.0 if room_open else ld["base_energy"]


def _place(ob, loc, rq, scale):
    ob.matrix_world = Matrix.Translation(loc) @ Quaternion(rq).to_matrix().to_4x4() @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1))


def _hide_char(info):
    O = bpy.data.objects
    for n in info["parts"].values():
        O[n].hide_render = True
    for lst in info["pool"].values():
        for n in lst:
            O[n].hide_render = True


# ------------------------------------------------------------------ 표정 (HaruFaces 모듈을 그대로 옮김)
def _lin(r, g, b):
    return tuple(((c / 255 + 0.055) / 1.055) ** 2.4 if c / 255 > 0.04045 else c / 255 / 12.92 for c in (r, g, b))


DARK, WHITE, BLUE, RED = _lin(40, 30, 26), _lin(255, 255, 255), _lin(90, 170, 255), _lin(230, 50, 70)
PINK, GOLD, NAVY = _lin(255, 120, 140), _lin(255, 205, 60), _lin(60, 80, 140)
FACES = {
    "기본 미소": ("open", (.27, -9), "smile", ()), "활짝 웃음": ("happy", (.3, -6), "grin", ()),
    "폭소": ("squint", (.3, -10), "laugh", ("joytears",)), "윙크": (("open", "happy"), (.27, -6), "smirk", ()),
    "메롱": (("happy", "open"), (.28, -6), "tongue", ()), "뿌듯": ("happy", (.31, 8), "smirk", ()),
    "감동": ("star", (.31, -12), "opensmile", ("sparkle",)), "사랑": ("heart", (.31, -10), "grin", ()),
    "신남": ("wide", (.33, -8), "laugh", ("sparkle",)), "놀람": ("wide", (.34, -4), "o", ()),
    "충격": ("dot", (.3, -14), "bigo", ("gloom",)), "비명": ("wide", (.33, -18), "bigo", ("sweat",)),
    "겁먹음": ("dot", (.24, -20), "wavy", ("gloom", "sweat")), "슬픔": ("open", (.27, -20), "frown", ()),
    "울먹": ("teary", (.27, -22), "wavy", ()), "엉엉": ("cry", (.24, -22), "bigo", ()),
    "실망": ("half", (.24, -14), "frown", ()), "절망": ("closed", (.2, -20), "bigfrown", ("gloom",)),
    "짜증": ("half", (.2, 14), "flat", ()), "화남": ("open", (.2, 22), "frown", ()),
    "분노": ("open", (.19, 28), "teeth", ("vein",)), "삐짐": ("closed", (.22, 16), "pout", ()),
    "의심": ("half", ((.2, 6), (.31, -4)), "smallflat", (), .05), "장난기": ("half", (.2, 16), "grin", ()),
    "당황": ("wide", (.33, -14), "wavy", ("sweat",)), "민망": ("open", (.27, -14), "smallflat", ("sweat",), -.06),
    "무표정": ("open", (.26, 0), "flat", ()), "졸림": ("half", (.26, -8), "o", ()),
    "잠": ("closed", (.24, -4), "o", ("zzz",)), "생각 중": ("open", ((.27, 0), (.33, -6)), "smallflat", (), .05, .04),
    "깨달음": ("wide", (.35, -4), "opensmile", ("sparkle",)), "결심": ("open", (.2, 18), "smile", ()),
    "어지러움": ("x", (.27, -12), "wavy", ()), "기절": ("x", (.27, 0), "tongue", ()),
    "메스꺼움": ("half", (.24, -16), "wavy", ("sweat",)), "딴청": ("open", (.3, -4), "o", (), -.06, .03),
}
BLINKABLE = {"open", "wide", "dot", "teary", "half", "heart", "star"}


def _face_parts(name, blink):
    """표정 -> [(종류 B/C, vx, vy, w, h, 각도, 색, 겹, 네온)] (머리 크기 비율 좌표)"""
    closed = False
    if "|" in name:
        name, mod = name.split("|", 1)
        closed = mod == "closed"
    spec = FACES.get(name, FACES["기본 미소"])
    e, b, m, x = spec[0], spec[1], spec[2], spec[3]
    ex = spec[4] if len(spec) > 4 else 0
    ey = spec[5] if len(spec) > 5 else 0
    out = []

    def bar(vx, vy, w, h, ang=0, color=DARK, layer=0, neon=False):
        out.append(("B", vx, vy, w, h, ang, color, layer, neon))

    def dot(vx, vy, d, color=DARK, layer=0):
        out.append(("C", vx, vy, d, d, 0, color, layer, False))

    def eye(s, kind):
        if (blink or closed) and kind in BLINKABLE:
            kind = "closed"
        X, Y = s * 0.2 + ex, 0.03 + ey
        if kind == "open": dot(X, Y, .27); dot(X + .04, Y + .055, .08, WHITE, 1)
        elif kind == "wide": dot(X, Y, .34); dot(X + .05, Y + .07, .095, WHITE, 1)
        elif kind == "dot": dot(X, Y, .08)
        elif kind == "happy": bar(X - .045, Y + .02, .13, .042, 35); bar(X + .045, Y + .02, .13, .042, -35)
        elif kind == "sadclosed": bar(X - .045, Y - .02, .13, .042, -35); bar(X + .045, Y - .02, .13, .042, 35)
        elif kind == "closed": bar(X, Y - .02, .19, .042)
        elif kind == "half": dot(X, Y - .045, .21); dot(X + .035, Y - .06, .06, WHITE, 1); bar(X, Y + .035, .28, .06, 0, DARK, 2)
        elif kind == "x": bar(X, Y, .21, .045, 45); bar(X, Y, .21, .045, -45)
        elif kind == "squint": bar(X, Y + .04, .15, .042, s * 28); bar(X, Y - .04, .15, .042, -s * 28)
        elif kind == "heart": bar(X, Y - .02, .15, .15, 45, RED); dot(X - .055, Y + .045, .125, RED); dot(X + .055, Y + .045, .125, RED)
        elif kind == "star": bar(X, Y, .17, .17, 0, GOLD, 0, True); bar(X, Y, .17, .17, 45, GOLD, 0, True); bar(X + .02, Y + .02, .05, .05, 0, WHITE, 1, True)
        elif kind == "teary": dot(X, Y, .28); dot(X + .04, Y + .06, .09, WHITE, 1); dot(X - .045, Y - .04, .055, WHITE, 1); bar(X, Y - .15, .26, .06, 0, BLUE, 2)
        elif kind == "cry": bar(X - .045, Y - .02, .13, .042, -35); bar(X + .045, Y - .02, .13, .042, 35); bar(X, Y - .25, .1, .4, 0, BLUE, 0)

    eL, eR = (e if isinstance(e, tuple) else (e, e))
    eye(-1, eL)
    eye(1, eR)
    bL, bR = (b if isinstance(b[0], tuple) else (b, b))
    bar(-.2, bL[0], .19, .042, -bL[1])
    bar(.2, bR[0], .19, .042, bR[1])
    y = -0.24
    if m in ("smile", "tongue"):
        bar(0, y, .13, .035); bar(.085, y + .018, .065, .035, 32); bar(-.085, y + .018, .065, .035, -32)
        if m == "tongue": bar(.02, y - .055, .09, .085, 0, PINK, 1)
    elif m == "frown": bar(0, y, .13, .035); bar(.085, y - .018, .065, .035, -32); bar(-.085, y - .018, .065, .035, 32)
    elif m == "bigfrown": bar(0, y, .2, .04); bar(.13, y - .03, .09, .04, -40); bar(-.13, y - .03, .09, .04, 40)
    elif m == "flat": bar(0, y, .2, .035)
    elif m == "smallflat": bar(0, y, .09, .035)
    elif m == "pout": bar(0, y, .08, .035); bar(.05, y - .015, .045, .035, -35); bar(-.05, y - .015, .045, .035, 35)
    elif m == "grin": bar(0, y - .01, .3, .13); bar(0, y + .03, .26, .04, 0, WHITE, 1); bar(0, y - .045, .15, .05, 0, PINK, 1)
    elif m == "laugh": bar(0, y - .03, .32, .19); bar(0, y + .04, .28, .045, 0, WHITE, 1); bar(0, y - .085, .18, .07, 0, PINK, 1)
    elif m == "opensmile": bar(0, y - .01, .2, .1); bar(0, y - .035, .11, .045, 0, PINK, 1)
    elif m == "o": dot(0, y - .01, .11)
    elif m == "bigo": bar(0, y - .04, .19, .23); bar(0, y - .115, .12, .06, 0, PINK, 1)
    elif m == "wavy":
        for i, xx in enumerate((-.105, -.035, .035, .105)):
            bar(xx, y, .085, .035, 28 if i % 2 == 0 else -28)
    elif m == "teeth":
        bar(0, y, .31, .13); bar(0, y, .27, .09, 0, WHITE, 1)
        for xx in (-.07, 0, .07):
            bar(xx, y, .014, .09, 0, DARK, 2)
        bar(0, y, .27, .014, 0, DARK, 2)
    elif m == "smirk": bar(-.01, y, .16, .035, 6); bar(.1, y + .035, .07, .035, 40)
    for k in x:
        if k == "sweat": bar(.4, .2, .07, .11, 0, BLUE); bar(.4, .255, .05, .05, 45, BLUE)
        elif k == "vein":
            bar(.3, .39, .07, .028, 45, RED); bar(.37, .39, .07, .028, -45, RED)
            bar(.3, .32, .07, .028, -45, RED); bar(.37, .32, .07, .028, 45, RED)
        elif k == "gloom":
            for i, xx in enumerate((.1, .18, .26, .34)):
                bar(xx, .4 - (.03 if i % 2 == 1 else 0), .022, .16 if i % 2 == 1 else .1, 0, NAVY)
        elif k == "zzz":
            for X, Y, sz in ((.58, .3, .1), (.72, .46, .14)):
                bar(X, Y + sz / 2, sz, .03, 0, BLUE); bar(X, Y - sz / 2, sz, .03, 0, BLUE); bar(X, Y, sz * 1.25, .03, 45, BLUE)
        elif k == "joytears": bar(-.33, -.02, .05, .07, 0, BLUE); bar(.33, -.02, .05, .07, 0, BLUE)
        elif k == "sparkle":
            bar(.4, .33, .1, .03, 0, GOLD, 0, True); bar(.4, .33, .03, .1, 0, GOLD, 0, True)
            bar(-.42, .26, .07, .022, 0, GOLD, 0, True); bar(-.42, .26, .022, .07, 0, GOLD, 0, True)
    return out


ROT_DOT = (C3 := Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))) @ Matrix.Rotation(math.radians(90), 3, "Y") @ C3.transposed()


def _draw_face(info, head_M, head_size, name, blink):
    """머리의 최종 위치(head_M, 크기 없는 4x4)에 표정 조각들을 붙인다"""
    O = bpy.data.objects
    hw, hz, hh = head_size        # 블렌더 크기 (x=sx, y=sz, z=sy)
    fz = -hz / 2 - 0.02
    R = head_M.to_3x3()
    used = {}
    for kind, vx, vy, w, h, ang, col, layer, neon in _face_parts(name, blink):
        lst = info["pool"].get(kind, [])
        j = used.get(kind, 0)
        used[kind] = j + 1
        if j >= len(lst):
            continue
        ob = O[lst[j]]
        rx, ry, rz = -vx * hw, vy * hh, fz - layer * 0.012          # 로블록스 머리 기준 좌표
        loc = head_M.translation + R @ Vector((rx, -rz, ry))
        if kind == "B":
            rot = R @ (C3 @ Matrix.Rotation(math.radians(-ang), 3, "Z") @ C3.transposed())
            scale = (w * hw, 0.04, h * hh)
        else:
            rot = R @ ROT_DOT
            scale = (0.04, w * hw, w * hw)
        ob.matrix_world = Matrix.Translation(loc) @ rot.to_4x4() @ Matrix.Diagonal((*scale, 1))
        ob.color = (col[0], col[1], col[2], 1.0)
        ob["emit"] = 0.6 if neon else 0.0
        ob.material_slots[0].material = _mat("R_Neon_C" if neon else "R_SmoothPlastic_C")
        ob.hide_render = False
        ob.update_tag()
    for kind, lst in info["pool"].items():
        for j in range(used.get(kind, 0), len(lst)):
            O[lst[j]].hide_render = True


# ------------------------------------------------------------------ 연기 (걷기·팔·고개·깜빡임)
def _plan():
    if "plan" not in _S:
        path = os.path.join(os.path.dirname(bpy.data.filepath), "anim_plan.py")
        ns = {}
        with open(path, encoding="utf-8") as fh:
            exec(compile(fh.read(), path, "exec"), ns)
        _S["plan"] = ns
    return _S["plan"]


def _ease(u, u0, u1):
    if u1 <= u0:
        return 1.0 if u >= u0 else 0.0
    k = min(max((u - u0) / (u1 - u0), 0.0), 1.0)
    return k * k * (3 - 2 * k)


def _rot_about(p, axis, deg):
    if abs(deg) < 1e-4:
        return Matrix.Identity(4)
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-p)


def _seed(name):
    return (sum(ord(c) * (i + 3) for i, c in enumerate(name)) % 97) / 97.0


def _k(t, t0, t1):
    """t0~t1 사이 부드러운 0→1"""
    if t1 <= t0:
        return 1.0 if t >= t0 else 0.0
    x = min(max((t - t0) / (t1 - t0), 0.0), 1.0)
    return x * x * (3 - 2 * x)


def _bump(t, t0, dur):
    """t0 부터 dur 동안 0→1→0 한 번"""
    if t < t0 or t > t0 + dur or dur <= 0:
        return 0.0
    return math.sin(math.pi * (t - t0) / dur)


def _performance(name, shot_n, t, u, dur, gt, posed):
    """이 순간 배우의 연기 값들 (동작 시각은 컷 시작 기준 초)"""
    plan = _plan()
    acts = plan["PLAN"].get(shot_n, {}).get(name, [])
    sd = _seed(name)
    tau = 2 * math.pi
    P = {"walk": 0.0, "bob": 0.015 * math.sin(tau * 0.35 * gt + sd * 6), "pitch": 0.0, "yaw": 1.5 * math.sin(tau * 0.22 * gt + sd * 5),
         "roll": 0.0, "arm_up": 0.0,
         "LA": [3 * math.sin(tau * 0.4 * gt + sd * 4), -4.0], "RA": [3 * math.sin(tau * 0.4 * gt + sd * 4 + 1.3), 4.0],
         "LL": [0.0, 0.0], "RL": [0.0, 0.0], "expr": None, "head_back": 0.0, "run_v": 0.0}
    if posed:
        P["LA"] = [0.0, 0.0]
    for a in acts:            # 멈춤: 숨쉬기·흔들림을 줄였다가 끝난 뒤 천천히 되돌림
        if a[0] == "freeze":
            w = _k(t, a[2], a[2] + 0.25) if t >= a[1] else 1.0
            P["bob"] *= w
            P["yaw"] *= w
            P["LA"][0] *= w
            P["RA"][0] *= w
    cyc_speed, cyc_amp, cyc_dist = 0.0, 0.0, 0.0
    for a in acts:
        k = a[0]
        if k == "walk":
            t0 = a[2] if len(a) > 2 else 0.0
            tt = max(t - t0, 0.0)
            ramp = min(tt / 0.2, 1.0)
            P["walk"] = a[1] * max(tt - 0.1, 0.0) if tt > 0.2 else a[1] * tt * tt / 0.4
            cyc_speed, cyc_amp, cyc_dist = a[1], ramp, P["walk"]
        elif k == "cycle":
            cyc_speed, cyc_amp, cyc_dist = a[1], a[2], a[1] * t
        elif k == "wave":
            s = 1 if a[1] == "R" else -1
            t0, n = a[2], (a[3] if len(a) > 3 else 1)
            up = 0.2
            span = up + 0.4 * n
            e = _k(t, t0, t0 + up) * (1 - _k(t, t0 + span, t0 + span + 0.25))
            ph = max(t - t0 - up, 0.0)
            wv = 18 * math.sin(tau * 2.5 * ph) if ph < 0.4 * n else 0.0
            arm = P["RA" if s > 0 else "LA"]
            arm[0] = arm[0] * (1 - e) + 12 * e
            arm[1] = arm[1] * (1 - e) + s * (150 + wv) * e
        elif k == "point":
            s = 1 if a[1] == "R" else -1
            e = _k(t, a[4], a[4] + (a[5] if len(a) > 5 else 0.3))
            arm = P["RA" if s > 0 else "LA"]
            arm[0] = arm[0] * (1 - e) + a[2] * e
            arm[1] = arm[1] * (1 - e) + s * a[3] * e
        elif k == "arms_up":
            e = 1.0 if a[1] < 0 else _k(t, a[1], a[1] + 0.18)
            P["LA"] = [20 * e + P["LA"][0] * (1 - e), -140 * e + P["LA"][1] * (1 - e)]
            P["RA"] = [20 * e + P["RA"][0] * (1 - e), 140 * e + P["RA"][1] * (1 - e)]
            P["pitch"] += 8 * e
        elif k == "look":
            e = _k(t, a[3], a[4])
            P["pitch"] += a[1] * e
            P["yaw"] += a[2] * e
        elif k == "nod":
            P["pitch"] -= a[1] * _bump(t, a[2], a[3])
        elif k == "tilt":
            P["roll"] += a[1] * _k(t, a[2], a[3])
        elif k == "bounce":
            t0, n = a[2], (a[3] if len(a) > 3 else 1)
            for i in range(n):
                P["bob"] += a[1] * _bump(t, t0 + i * 0.32, 0.3)
            b = sum(_bump(t, t0 + i * 0.32, 0.3) for i in range(n))
            P["LA"][1] -= 12 * b
            P["RA"][1] += 12 * b
        elif k == "shrug":
            e = _k(t, a[1], a[1] + 0.15) * (1 - _k(t, a[1] + 0.4, a[1] + 0.6))
            P["arm_up"] = 0.22 * e
            P["LA"] = [P["LA"][0] + 20 * e, P["LA"][1] - 25 * e]
            P["RA"] = [P["RA"][0] + 20 * e, P["RA"][1] + 25 * e]
            P["pitch"] -= 4 * e
            P["roll"] += 5 * e
        elif k == "swing":
            s = 1 if a[1] == "R" else -1
            t0, d, big = a[2], (a[3] if len(a) > 3 else 0.45), (a[4] if len(a) > 4 else 1.0)
            wind = _k(t, t0 - 0.15, t0)                 # 뒤로 들어 올림
            hit = _k(t, t0, t0 + d)                     # 앞으로 휘두름
            back = _k(t, t0 + d + 0.1, t0 + d + 0.45)    # 내려놓음
            ang = (150 * big) * wind * (1 - hit) + (20 + 10 * big) * hit * (1 - back) + 0 * back
            arm = P["RA" if s > 0 else "LA"]
            act = max(wind, 1 - back) if t >= t0 - 0.15 else 0.0
            arm[0] = arm[0] * (1 - act) + ang * act
            arm[1] = arm[1] * (1 - act) + s * 15 * act
            P["yaw"] += s * 10 * big * (hit - 0.5) * act
        elif k == "jerk":
            dt = t - a[1]
            amp = a[2] if len(a) > 2 else 1.0
            if dt > 0:
                pulse = dt / 0.06 if dt < 0.06 else math.exp(-(dt - 0.06) * 9)
                P["pitch"] += 12 * amp * pulse
                P["bob"] += 0.08 * amp * pulse
        elif k == "jar_raise":
            e = _k(t, a[2], a[3])
            if P["LA"] is not None:
                P["LA"][0] += a[1] * e
        elif k == "jar_tilt":
            if P["LA"] is not None:
                P["LA"][1] += a[1] * _bump(t, a[2], a[3] - a[2])
        elif k == "chin":
            e = _k(t, a[3], a[4])
            P["head_back"] += a[1] * e
            P["pitch"] += a[2] * e
        elif k == "run":
            # 곧은 다리 달리기: 디딘 발은 몸 이동만큼 뒤로 밀려 땅에 고정, 든 발은 앞으로 휘둘러 다음 디딤
            # 상자 발은 뒤꿈치 모서리로 디뎠다가 발끝 모서리로 차고 나감 (그 모서리가 땅에 고정되게 각도·높이 계산)
            v, st, thm, L, hf = a[1], a[2], math.radians(a[3]), a[4], a[5]
            sg = a[6] if len(a) > 6 else 1.0
            hh = a[7] if len(a) > 7 else 0.0          # 발 길이의 절반
            R, phi = math.hypot(L, hh), math.atan2(hh, L)
            T = 2 * st
            x0 = L * math.sin(thm) - hh * math.cos(thm)   # 디딜 때 뒤꿈치 모서리 (엉덩이 기준 앞쪽 거리)
            t1 = (x0 + hh) / v                            # 뒤꿈치로 구르는 시간 (= 발끝으로 구르는 시간)
            tc = min(2 * t1, st * 0.9)

            def leg(ph):
                """(다리 각도, 디딘 중이면 몸 높이 보정)"""
                if ph < t1:
                    th = phi + math.asin(max(-1.0, min(1.0, (x0 - v * ph) / R)))
                    return th, R * math.cos(th - phi) - L
                if ph < tc:
                    th = math.asin(max(-1.0, min(1.0, (hh - v * (ph - t1)) / R))) - phi
                    return th, R * math.cos(th + phi) - L
                s = (ph - tc) / (T - tc)
                return -thm + 2 * thm * (0.5 - 0.5 * math.cos(math.pi * s)), None

            def lift(ph):         # 앞으로 휘두르는 다리는 반바지 안으로 살짝 올려 땅에 끌리지 않게
                if ph < tc:
                    return 0.0
                return 0.32 * math.sin(math.pi * (ph - tc) / (T - tc))
            P["lift"] = {"LL": lift(t % T), "RL": lift((t + st) % T)}
            (thL, bL), (thR, bR) = leg(t % T), leg((t + st) % T)
            if bL is not None:
                bob = bL
            elif bR is not None:
                bob = bR
            else:
                u = ((t % st) - tc) / (st - tc)
                bob = (R * math.cos(thm - phi) - L) + 4 * hf * u * (1 - u)
            P["LL"][0] = sg * math.degrees(thL)
            P["RL"][0] = sg * math.degrees(thR)
            if not posed:
                P["LA"][0] = -0.9 * P["LL"][0]
            P["RA"][0] = -0.9 * P["RL"][0]
            P["bob"] += bob
            P["pitch"] -= 4
            P["run_v"] = v
        elif k == "expr":
            cur = None
            for tt, nm in a[1]:
                if t >= tt:
                    cur = nm
            P["expr"] = cur
    if cyc_speed > 0:
        ph = tau * cyc_dist / (4.5 if cyc_speed < 8 else 7.0)
        leg = 28 * cyc_amp
        P["LL"][0] = leg * math.sin(ph)
        P["RL"][0] = -leg * math.sin(ph)
        if not posed:
            P["LA"][0] += -0.8 * leg * math.sin(ph)
        P["RA"][0] += 0.8 * leg * math.sin(ph)
        P["bob"] += 0.1 * cyc_amp * abs(math.sin(ph))
        P["pitch"] -= 4 * cyc_amp
    # 눈 깜빡임: 배우마다 다른 간격, 4프레임
    period = 2.4 + sd * 1.6
    P["blink"] = ((gt + sd * 3.1) % period) < 0.12
    return P
def _snap_base(sh, name, snap, info, rig):
    """기록 한 장 -> 조각별 (물체, 기본 행렬, 부위, 색, 숨김), 관절 위치들"""
    key = (sh["n"], snap[0])
    cache = _S.setdefault("base", {})
    if cache.get(name, (None,))[0] == key:
        return cache[name][1]
    O = bpy.data.objects
    _, nonface, face = snap
    parts, rigid = [], {}
    head = None
    for idx, k, size, loc, rq, col, rmat, tr in nonface:
        on = info["parts"].get(idx)
        if not on:
            continue
        ob = O[on]
        Rm = Matrix.Translation(loc) @ Quaternion(rq).to_matrix().to_4x4()
        rigid[idx] = Rm
        sc = ob["scale"]
        Mb = Rm @ Matrix.Diagonal((sc[0], sc[1], sc[2], 1))
        a = 1 - tr
        if tr >= 0.5:      # 안경알·유리병처럼 반투명한 조각은 더 투명하게
            a *= 0.4
        g = rig["g"].get(idx, "LA") if rig else "T"
        parts.append((ob, Mb, g, (col[0], col[1], col[2], a if a < 0.9 else 1.0), tr >= 0.99))
        if k == "H":
            head = (idx, size)
    joints = {}
    if rig:
        for key2 in ("LA", "RA", "LL", "RL", "HD"):
            idx, (x, y, z) = rig[key2]
            if idx in rigid:
                joints[key2] = rigid[idx] @ Vector((x, -z, y))
        T = rigid.get(rig["T"])
        joints["axes"] = T.to_3x3() if T else Matrix.Identity(3)
    base = {"parts": parts, "joints": joints, "head": head, "rigid": rigid, "nface": len(face)}
    cache[name] = (key, base)
    return base


def _chars(sh, f, a, data):
    O = bpy.data.objects
    plan = _plan()
    present = []
    _S["grp"] = {}
    t = (f + a) / 30.0
    dur = max(sh["count"] / 30.0, 1e-3)
    u = min(t / dur, 1.0)
    gt = (sh["start"] + f + a) / 30.0
    for name, snaps in sh["chars"].items():
        snap = None
        for s in snaps:
            if s[0] <= f:
                snap = s
            else:
                break
        if snap is None:
            continue
        present.append(name)
        info = data["chars"][name]
        rig = plan["RIG"].get(name)
        base = _snap_base(sh, name, snap, info, rig)
        P = _performance(name, sh["n"], t, u, dur, gt, (sh["n"], name) in plan["POSED"])
        J = base["joints"]
        ax = J.get("axes", Matrix.Identity(3))
        X, UPv, FWD = ax.col[0].normalized(), ax.col[2].normalized(), ax.col[1].normalized()
        flat = Vector((FWD.x, FWD.y, 0))
        flat = flat.normalized() if flat.length > 1e-4 else Vector((0, 0, 0))
        G = Matrix.Translation(flat * (P["walk"] + P["run_v"] * a / 30.0) + Vector((0, 0, P["bob"])))
        Xg = {"T": Matrix.Identity(4)}
        for side in ("LA", "RA", "LL", "RL"):
            ang = P[side]
            if ang is None or side not in J:
                Xg[side] = Matrix.Identity(4)
                continue
            p = J[side]
            M = _rot_about(p, FWD, -ang[1]) @ _rot_about(p, X, ang[0])
            if side in ("LA", "RA") and P["arm_up"]:
                M = Matrix.Translation(UPv * P["arm_up"]) @ M
            if side in P.get("lift", {}):
                M = Matrix.Translation(UPv * P["lift"][side]) @ M
            Xg[side] = M
        if "HD" in J:
            p = J["HD"]
            Xg["HD"] = _rot_about(p, UPv, P["yaw"]) @ _rot_about(p, X, P["pitch"]) @ _rot_about(p, FWD, P["roll"])
        else:
            Xg["HD"] = Matrix.Identity(4)
        if P["head_back"]:
            Xg["HD"] = Matrix.Translation(-FWD * P["head_back"]) @ Xg["HD"]
        if P["LA"] is None and P["arm_up"]:
            Xg["LA"] = Matrix.Identity(4)
        _S["grp"][name] = {g: G @ Xg.get(g, Xg["T"]) for g in ("T", "LA", "RA", "HD")}
        seen = set()
        for ob, Mb, g, col, hidden in base["parts"]:
            seen.add(ob.name)
            ob.matrix_world = G @ Xg.get(g, Xg["T"]) @ Mb
            if _S["char_key"].get(name) != (sh["n"], snap[0]):
                ob.hide_render = hidden
                ob.color = col
        if _S["char_key"].get(name) != (sh["n"], snap[0]):
            for on in info["parts"].values():
                if on not in seen:
                    O[on].hide_render = True
            _S["char_key"][name] = (sh["n"], snap[0])
        # 표정: 계획 > 로블록스 기록
        expr = P["expr"]
        if expr is None:
            for ff, nm in plan["EXPR"].get((sh["n"], name), []):
                if ff <= f:
                    expr = nm
        if base["head"] and expr:
            idx, size = base["head"]
            headM = G @ Xg["HD"] @ base["rigid"][idx]
            _draw_face(info, headM, size, expr, P["blink"])
        else:
            for lst in info["pool"].values():
                for n in lst:
                    O[n].hide_render = True
    for name, info in data["chars"].items():
        if name not in present and _S["char_key"].get(name) != "hidden":
            _S["char_key"][name] = "hidden"
            _hide_char(info)
    return present


def _stars(sh, f, a, data):
    O = bpy.data.objects
    decl, frames = sh["decl"], sh["stars"]
    n = len(decl) if frames else 0
    fr = frames[f] if f < len(frames) else None
    fr2 = frames[f + 1] if f + 1 < len(frames) else None
    frp = frames[f - 1] if 0 < f <= len(frames) else None
    spec = _plan().get("STARFX", {}).get(sh["n"], {})
    soft = spec.get("tail")
    att = spec.get("attach")
    popin = spec.get("popin", 0)
    glow_j = spec.get("glow")
    glow_pos = None
    tt = (f + a) / 30.0
    for j, (sn, tn) in enumerate(zip(data["stars"], data["tails"])):
        s, t = O[sn], O[tn]
        if j >= n or fr is None or fr[j] is None:
            if not s.hide_render:
                s.hide_render = True
            if not t.hide_render:
                t.hide_render = True
            continue
        p = Vector(fr[j])
        q = Vector(fr2[j]) if (fr2 and fr2[j]) else None
        pp = Vector(frp[j]) if (frp and frp[j]) else None
        pos = p.lerp(q, a) if q else p
        size, trail = decl[j]
        if att and j == att[0] and tt >= att[3]:           # 손·어깨에 닿은 뒤 그 부위를 따라감
            g = _S.get("grp", {}).get(att[1], {}).get(att[2])
            if g is not None:
                w = 1.0 if att[4] is None else 1.0 - _k(tt, att[3], att[3] + att[4])
                pos = pos.lerp(g @ pos, w)
        sc = size
        if popin:                                             # 새로 나타난 별은 몇 프레임에 걸쳐 커지며 켜짐
            k = 0
            while k < popin and f - k - 1 >= 0 and frames[f - k - 1][j] is not None:
                k += 1
            if k < popin and f - k > 0:
                sc = size * _ease(k + a, 0.0, float(popin))
        s.location = pos
        s.scale = (sc, sc, sc)
        s.hide_render = sc < 1e-3
        if j == glow_j:
            glow_pos = pos
        vel = (q - p) if q else ((p - pp) if pp else None)
        if trail and vel is not None and vel.length > 1e-4:
            speed = vel.length * 30.0
            if soft and soft[0] <= j < soft[1]:
                # 작은 꼬리: 속도에 비례해 줄고, 거의 멈추면 가늘어지며 사라짐
                length = min(speed * 0.3, size * 4.0)
                width = size * 0.5 * min(1.0, length / (size * 1.5))
                if length < size * 0.35:
                    t.hide_render = True
                    continue
            else:
                length = min(max(speed * 0.45, size * 1.5), size * 6.0, 12.0)
                width = size * 0.75
            d = -vel.normalized()
            rot = UP.rotation_difference(d).to_matrix().to_4x4()
            t.matrix_world = Matrix.Translation(pos + d * (length * 0.5)) @ rot @ Matrix.Diagonal((width, width, length, 1))
            t.hide_render = False
        else:
            t.hide_render = True
    gl = O.get("StarGlow")
    if gl:
        if glow_pos is not None:
            gl.location = glow_pos
            gl.data.energy = GLOW_W
        else:
            gl.data.energy = 0.0


def _camera(scene, sh, f, a):
    """카메라 위치·화각 + 기록된 초점 거리(fd, 없으면 -1)·조리개(fs, 0 = 자동) 반환"""
    cam = scene.camera
    cams = sh["cam"]
    c1 = cams[min(f, len(cams) - 1)]
    M1, fov1 = Matrix(c1[0]), c1[1]
    fd1 = c1[2] if len(c1) > 2 else -1.0
    fs = c1[3] if len(c1) > 3 else 0.0
    if a > 0 and f + 1 < len(cams):
        c2 = cams[f + 1]
        M2 = Matrix(c2[0])
        loc = M1.translation.lerp(M2.translation, a)
        q = M1.to_quaternion().slerp(M2.to_quaternion(), a)
        M = Matrix.Translation(loc) @ q.to_matrix().to_4x4()
        fov = fov1 + (c2[1] - fov1) * a
        fd2 = c2[2] if len(c2) > 2 else -1.0
        fd = fd1 + (fd2 - fd1) * a if (fd1 > 0 and fd2 > 0) else fd1
    else:
        M, fov, fd = M1, fov1, fd1
    cam.matrix_world = M
    cam.data.angle = math.radians(fov)
    return fd, fs


def _grade(scene, sh):
    """컷별 색온도·노출·블룸"""
    temp, exp_add, bloom = _plan()["GRADE"].get(sh["n"], (6500, 0.0, 0.55))
    vs = scene.view_settings
    vs.use_white_balance = True
    vs.white_balance_temperature = temp
    vs.white_balance_tint = 10.0
    vs.exposure = (-0.3 if sh["day"] else 0.4) + exp_add
    ng = scene.compositing_node_group
    if ng:
        for nd in ng.nodes:
            if nd.bl_idname == "CompositorNodeGlare":
                nd.inputs["Strength"].default_value = bloom


def _sky_ramp(scene, sh, t):
    r = _plan()["SKYRAMP"].get(sh["n"])
    if not r:
        return
    t0, t1, s0, s1 = r
    k = _k(t, t0, t1)
    v = STAR_THRESH[s0] + (STAR_THRESH[s1] - STAR_THRESH[s0]) * k
    scene.world.node_tree.nodes["STARS"].outputs[0].default_value = v


def _lid_pop(sh, f, a, data):
    """뚜껑 열기 인서트: 해당 병 뚜껑을 1~3프레임에 들어 올림"""
    O = bpy.data.objects
    pop = _plan()["LIDPOP"].get(sh["n"])
    if not pop:
        return
    x, y, z = pop
    target = Vector((x, -z, y))
    key = ("lid", sh["n"])
    if _S.get("lid_key") != key:
        best, bd = None, 1e9
        for n in data["dyn"]["RoomLid"]:
            d = (O[n].matrix_world.translation - target).length
            if d < bd:
                best, bd = n, d
        _S["lid_key"] = key
        _S["lid_obj"] = best
        _S["lid_M"] = O[best].matrix_world.copy() if best else None
    on = _S.get("lid_obj")
    if not on:
        return
    ob = O[on]
    tt = (f + a) / 30.0
    k = _k(tt, 0.0, 0.1)             # 3프레임에 들림
    k2 = _k(tt, 0.1, 0.4)            # 이후 천천히 옆으로 비켜남
    M0 = _S["lid_M"]
    lift = Matrix.Translation(Vector((0.25 * k2, 0, 0.55 * k + 0.25 * k2)))
    tilt = Matrix.Translation(M0.translation) @ Matrix.Rotation(math.radians(-28 * k), 4, "X") @ Matrix.Translation(-M0.translation)
    ob.matrix_world = lift @ tilt @ M0
    ob.hide_render = False


def _focus(scene, present, data, fd=-1.0, fs=0.0):
    cam = scene.camera
    if fd > 0:
        dof = cam.data.dof
        dof.focus_distance = fd
        dof.aperture_fstop = fs if fs > 0 else max(1.8, min(fd * 0.45, 8.0))
        return
    M = cam.matrix_world
    fwd = -(M.to_3x3().col[2]).normalized()
    pos = M.translation
    best = None
    for name in present:
        hn = data["chars"][name]["head"]
        if not hn:
            continue
        h = bpy.data.objects[hn]
        if h.hide_render:
            continue
        v = h.matrix_world.translation - pos
        dist = v.dot(fwd)
        if dist <= 0.5:
            continue
        if math.degrees(fwd.angle(v)) < 20 and (best is None or dist < best):
            best = dist
    dof = cam.data.dof
    if best is not None and best < 25:
        dof.focus_distance = best
        dof.aperture_fstop = max(1.8, min(best * 0.45, 8.0))
    else:
        dof.focus_distance = 60
        dof.aperture_fstop = 22


@persistent
def film_frame(scene, depsgraph=None):
    if _S["data"] is None:
        _load(scene)
    data = _S["data"]
    ff = scene.frame_current + scene.frame_subframe
    base = math.floor(ff)
    a = ff - base
    last = data["shots"][-1]
    total = last["start"] + last["count"]
    g = min(max(int(base) - 1, 0), total - 1)
    i = bisect.bisect_right(_S["starts"], g) - 1
    sh = data["shots"][i]
    f = g - sh["start"]
    if _S["last_shot"] != i:
        prev = _S.get("lid_obj")
        if prev and _S.get("lid_M") is not None:      # 앞 컷에서 움직인 뚜껑 제자리
            bpy.data.objects[prev].matrix_world = _S["lid_M"]
        _S["lid_key"] = _S["lid_obj"] = _S["lid_M"] = None
        _shot_state(scene, sh, data)
        _grade(scene, sh)
        _S["last_shot"] = i
    _sky_ramp(scene, sh, (f + a) / 30.0)
    _lid_pop(sh, f, a, data)
    present = _chars(sh, f, a, data)
    _stars(sh, f, a, data)
    fd, fs = _camera(scene, sh, f, a)
    _focus(scene, present, data, fd, fs)


@persistent
def film_load(_dummy=None):
    _S["data"] = None


GLOW_W = 8.0


def _ensure_glow():
    """별을 따라다니는 약한 금빛 점조명 (2.6 스터드 안의 표면에만 닿음)"""
    if "StarGlow" in bpy.data.objects:
        return
    ld = bpy.data.lights.new("StarGlow", "POINT")
    ld.energy = 0.0
    ld.color = (1.0, 0.72, 0.32)
    ld.shadow_soft_size = 0.12
    ld.use_custom_distance = True
    ld.cutoff_distance = 2.6
    ob = bpy.data.objects.new("StarGlow", ld)
    bpy.context.scene.collection.objects.link(ob)


def register():
    _ensure_glow()
    for lst in (bpy.app.handlers.frame_change_pre, bpy.app.handlers.load_post):
        for hnd in list(lst):
            if getattr(hnd, "__name__", "") in ("film_frame", "film_load"):
                lst.remove(hnd)
    bpy.app.handlers.frame_change_pre.append(film_frame)
    bpy.app.handlers.load_post.append(film_load)
    _S["data"] = None


register()
