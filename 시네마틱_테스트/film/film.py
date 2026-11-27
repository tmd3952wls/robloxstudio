"""불과 물의 마을 — 시네마틱 본편 (대사 1~94). 컷마다 별도 블렌더 프로세스.
blender -b --factory-startup --python film/film.py -- <컷이름> [still|frames|probe] [pct]
 still : 컷 가운데 프레임 1장 + 카메라 충돌 검사(out/film/probe/<컷>.json)
 frames: 전체 프레임 (이미 있는 프레임은 건너뜀)
 probe : 충돌 검사만
카메라는 프레임마다 키프레임(모션 블러 정확), 배우는 frame_change 핸들러(절대 시간 t 초).
"""
import os, sys, time, json, math, random
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
sys.path.insert(0, os.path.join(D, "..", "lib"))
sys.path.insert(0, os.path.join(D, "..", "emotion"))
import bpy
import numpy as np
from mathutils import Vector, Matrix
import look, world_valley, perf, fx, town as TW, pbr
import roblox_char as RC
import anim as AN
import story as ST
import shotlist as SL

OUT = os.path.join(D, "..", "out", "film")
a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["sky"]
shot = a[0]
mode = a[1] if len(a) > 1 else "frames"
pct = int(a[2]) if len(a) > 2 else 100
name, f0, f1, eng = [s for s in SL.shots() if s[0] == shot][0]
T0 = (f0 - 1) / 30.0                       # 컷 시작 시각 (초)
DUR = (f1 - f0 + 1) / 30.0

look.clear_scene()
mon = perf.Monitor()
info = world_valley.build("full")
V = info["V"]
xr = lambda y: float(V.river_x(y))
rw = V.river_w / 2
TZ = V.town_z
sc = bpy.context.scene
yb = info["bridge_y"]
xc = xr(yb)
HALF = TW.bridge_half(V)
DZ = lambda x: TW.deck_z(V, yb, x)
PF = Vector((info["plaza_fire"][0], info["plaza_fire"][1], 0))
PW = Vector((info["plaza_water"][0], info["plaza_water"][1], 0))
RIVER = bpy.data.objects.get("River")
rnd = random.Random(hash(shot) % 10000)


def G(x, y):
    """그 자리 서는 높이 (다리 위면 상판)"""
    z = DZ(x) if abs(y - yb) < 3.4 else None
    return z if z is not None else float(V.H(x, y)) + 0.07


FACE = 1.52                                  # R6 머리 가운데 높이 (발 기준, 크기 1)


def P3(x, y, dz=0.0):
    return Vector((x, y, G(x, y) + dz))


def ease_in(u, p=2.2):
    return u ** p


def ease_out(u, p=2.0):
    return 1 - (1 - u) ** p


def smooth(u):
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return Vector(a) + (Vector(b) - Vector(a)) * u


def mixf(a, b, u):
    return a + (b - a) * u


def yaw_to(d):
    """정면(-Y 로컬)이 방향 d 를 보게 하는 yaw"""
    return math.atan2(d[0], -d[1])


def fwd_of(yaw):
    return Vector((math.sin(yaw), -math.cos(yaw), 0))


# ------------------------------------------------------------------ 조명
def moon():
    m = pbr.flat_mat("MoonM", (0.9, 0.92, 1.0), 0.5, emit=(0.85, 0.9, 1.0), emit_str=6.0)
    import mesh as MS
    mb = MS.MB()
    mb.cyl("m", (0, 0, 0), 55, 4, 32)
    o = mb.build("Moon", {"m": m})
    d = Vector((math.cos(math.radians(120)), math.sin(math.radians(120)), math.tan(math.radians(28)))).normalized()
    o.location = Vector((xc, yb, 0)) + d * 3600
    o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()


def sun_disk(elev=52, azim=205):
    m = pbr.flat_mat("SunDiskM", (1, 0.95, 0.8), 0.5, emit=(1.0, 0.85, 0.6), emit_str=160.0)
    import mesh as MS
    mb = MS.MB()
    mb.cyl("m", (0, 0, 0), 520, 4, 48)
    o = mb.build("SunDisk", {"m": m})
    d = Vector((math.cos(math.radians(azim)) * math.cos(math.radians(elev)), math.sin(math.radians(azim)) * math.cos(math.radians(elev)),
                math.sin(math.radians(elev))))
    o.location = Vector((xc, yb, 0)) + d * 4200
    o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return d


def light(kind, along=None):
    air = lambda dens, col: look.fog((V.x0, V.y0, -20), (V.x1, V.y1, 900), density=dens, color=col, name="Air")
    if kind == "day":
        look.world("kloofendal_48d_partly_cloudy_puresky", 1.0, rot_deg=40)
        look.sun(32, 205, 4.5)
        air(0.00009, (0.78, 0.84, 0.95))
    elif kind == "dusk":
        look.world("belfast_sunset_puresky", 0.5, rot_deg=60)
        look.sun(27, (along or 0) + 197, 6.5, (1.0, 0.7, 0.45), 0.8)
        air(0.00009, (0.95, 0.8, 0.7))
    elif kind == "night":
        look.world("belfast_sunset_puresky", 0.13, rot_deg=60, sky_tint=(0.35, 0.45, 1.0))
        look.sun(35, 120, 0.75, (0.55, 0.65, 1.0), 2.0)
        air(0.00012, (0.4, 0.5, 0.8))
        moon()
    elif kind == "rain":
        look.world("kloofendal_48d_partly_cloudy_puresky", 0.45, rot_deg=40, sky_tint=(0.7, 0.78, 0.9))
        look.sun(40, 205, 0.9, (0.85, 0.9, 1.0), 12.0)
        air(0.00035, (0.7, 0.78, 0.88))
    elif kind == "nightrain":
        look.world("belfast_sunset_puresky", 0.17, rot_deg=60, sky_tint=(0.4, 0.5, 1.0))
        look.sun(35, 120, 0.85, (0.55, 0.65, 1.0), 6.0)
        air(0.0003, (0.45, 0.55, 0.8))
        moon()
    elif kind == "hot":                     # 비가 멈춘 여름: 강한 해, 누런 공기
        look.world("kloofendal_48d_partly_cloudy_puresky", 1.15, rot_deg=40, sky_tint=(1.0, 0.93, 0.8))
        look.sun(52, 205, 6.5, (1.0, 0.86, 0.66), 0.9)
        air(0.00018, (0.95, 0.84, 0.66))
    elif kind == "sunset":
        look.world("belfast_sunset_puresky", 0.85, rot_deg=60)
        look.sun(16, 200, 5.5, (1.0, 0.62, 0.36), 1.0)
        air(0.00012, (0.98, 0.76, 0.6))


def water(off, anim=None):
    """강 수위: off(m) 만큼 내림/올림. anim=(프레임a, off_a, 프레임b, off_b)"""
    if not RIVER:
        return
    if anim:
        fa, oa, fb, ob = anim
        for fr, o in ((fa, oa), (fb, ob)):
            RIVER.location.z = o
            RIVER.keyframe_insert("location", index=2, frame=fr)
    else:
        RIVER.location.z = off


def redline(state="on", anim=None):
    m = bpy.data.materials.get("RedLine")
    if not m:
        return
    bs = m.node_tree.nodes["Principled BSDF"]
    stone = (0.32, 0.3, 0.27, 1)
    if state == "off":
        bs.inputs["Base Color"].default_value = stone
        bs.inputs["Emission Strength"].default_value = 0.0
    if anim:                                  # (프레임a, 프레임b): 빨강 -> 돌색
        fa, fb = anim
        bs.inputs["Base Color"].keyframe_insert("default_value", frame=fa)
        bs.inputs["Emission Strength"].keyframe_insert("default_value", frame=fa)
        bs.inputs["Base Color"].default_value = stone
        bs.inputs["Emission Strength"].default_value = 0.0
        bs.inputs["Base Color"].keyframe_insert("default_value", frame=fb)
        bs.inputs["Emission Strength"].keyframe_insert("default_value", frame=fb)


SIGN_X = xc - 1.3
SIGN_Y = yb - 2.35


def bridge_sign():
    ST.sign((SIGN_X, SIGN_Y, DZ(SIGN_X)), -math.pi / 2)


def rain_at(center, size=(60, 60, 30), n=12000):
    rn = fx.rain(tuple(center), size, n=n)
    rn.cycles.use_motion_blur = False
    return rn


def burning(center, radius, n, big=1.0, calm=False, seed=0):
    """불 마을 지붕 화재: center 근처 집 n 채 지붕에 불 + 검은 연기"""
    T = info["towns"]["fire"]
    c = Vector(center[:2])
    hs = sorted(T.info, key=lambda i: (Vector(i["center"][:2]) - c).length)
    hs = [h for h in hs if (Vector(h["center"][:2]) - c).length < radius][:n]
    sm = bpy.data.materials.get("BurnSmoke") or fx.volume_mat("BurnSmoke", (0.09, 0.08, 0.075), density=0.35, scale=0.18, speed=1.6, up=1.4)
    out = []
    for k, h in enumerate(hs):
        top = Vector(h["center"]) + Vector((0, 0, h["height"] * 0.82))
        if calm:
            fx.flame(tuple(top), 0.9, 0.7, f"Burn{k}", n=3, seed=k + seed, light=True, energy=350)
            fx.plume(tuple(top), 0.6, 4.0, 18, bpy.data.materials.get("ChimneySmoke") or
                     fx.volume_mat("ChimneySmoke", (0.55, 0.53, 0.5), density=0.6, scale=0.25, speed=1.0), f"BurnSm{k}", 16)
        else:
            W_ = h.get("size", (6, 6))[0] if isinstance(h.get("size"), (tuple, list)) else 6
            for j in range(4):
                o = Vector((rnd.uniform(-0.35, 0.35) * W_, rnd.uniform(-0.3, 0.3) * W_, rnd.uniform(-0.6, 0.3)))
                fx.flame(tuple(top + o), rnd.uniform(1.6, 2.8) * big, rnd.uniform(0.7, 1.1) * big, f"Burn{k}_{j}", n=3, seed=k * 7 + j + seed,
                         light=(j == 0), energy=3500 * big, mat=fx.roof_fire_mat())
            fx.plume(tuple(top + Vector((0, 0, 2.5))), 1.4, 9.0, 40, sm, f"BurnSm{k}", 16, lean=(math.radians(rnd.uniform(5, 14)), 0))
        out.append(top)
    return out


def far_smoke():
    """다리 컷 배경: 불 마을 위로 솟는 검은 연기 기둥 몇 개 (화재 시기)"""
    sm = bpy.data.materials.get("BurnSmoke") or fx.volume_mat("BurnSmoke", (0.09, 0.08, 0.075), density=0.35, scale=0.18, speed=1.6, up=1.4)
    for k, (dx, dy) in enumerate(((-70, -60), (-95, 10), (-60, 70), (-120, -20), (-85, 120))):
        x, y = xc + dx, yb + dy
        fx.plume((x, y, float(V.H(x, y)) + 8), 2.0, 14, 60, sm, f"FarSmoke{k}", 16, lean=(math.radians(10), 0))
        fx.flame((x, y, float(V.H(x, y)) + 6), 4, 2.0, f"FarBurn{k}", n=4, seed=k, light=True, energy=5000, mat=fx.roof_fire_mat())


# ------------------------------------------------------------------ 배우
actors = []          # (Char, timeline, [extra])


def person(nm, outfit, pos, face, emo=(("평온", 0.8),), scale=1.0, walk=None, extra=None, glow=False, deck=False):
    x, y = pos[0], pos[1]
    z = pos[2] if len(pos) > 2 else G(x, y)
    yaw = face if isinstance(face, (int, float)) else yaw_to(face)
    ch = RC.Char(nm, outfit, (x, y, z), yaw, scale=scale)
    tl = AN.Timeline(RC.OUTFITS[outfit]["style"], seed=abs(hash(nm)) % 997)
    for e in emo:
        if len(e) == 2:
            tl.key(0.0, e[0], e[1])
        else:
            tl.key(T0 + e[0], e[1], e[2])
    if walk:
        ch.walk = (walk[0], T0 + walk[1], rnd.uniform(0, 6))
    ex = [extra] if callable(extra) else list(extra or [])
    if deck:
        ex.append(on_deck)
    if glow:
        L = look.point(f"{nm}_glow", (0, 0, 0), 30, (1.0, 0.2, 0.04), 0.2)
        L.parent = ch.head
        L.location = (0, -0.4, 0.5)
    actors.append((ch, tl, ex))
    return ch, tl


def on_deck(ch, t):
    p = ch.root.location
    z = DZ(p.x) if abs(p.y - yb) < 3.4 else None
    p.z = z if z is not None else float(V.H(p.x, p.y)) + 0.07


def arm(ch, side, ax, az=0.0):
    """side -1/1, ax: - 앞으로 들기(도), az: 옆으로 벌리기(도)"""
    ch.arms[side].rotation_euler = (math.radians(ax), -side * math.radians(az), 0)


def handler(scene, *_):
    t = (scene.frame_current - 1 + scene.frame_subframe) / 30.0
    for ch, tl, ex in actors:
        f, b = tl.eval(t)
        ch.pose(b, t)
        for e in ex:
            e(ch, t)
        ch.set_face(f, t)


def crowd(outfits, pts, face, emo=(("평온", 0.8),), scale=1.0, glow=False, deck=False, prefix="C", extra=None, jitter=0.4):
    out = []
    for k, p in enumerate(pts):
        f = face(p) if callable(face) else face
        if not isinstance(f, (int, float)):
            f = yaw_to(f) + rnd.uniform(-jitter, jitter)
        out.append(person(f"{prefix}{k}", outfits[k % len(outfits)], p, f, emo, scale, glow=glow, deck=deck, extra=extra)[0])
    return out


def bank_pts(side, y0, y1, n, d0=4.5, d1=8.0, avoid_bridge=True):
    pts = []
    tries = 0
    while len(pts) < n and tries < 500:
        tries += 1
        y = rnd.uniform(y0, y1)
        if avoid_bridge and abs(y - yb) < 5.5:
            continue
        d = rnd.uniform(d0, d1)
        x = xr(y) + side * (rw + d)
        if all((Vector((x, y)) - Vector(q[:2])).length > 1.6 for q in pts):
            pts.append((x, y))
    return pts


def haru(pos, face, emo=(("평온", 0.8),), walk=None, extra=None, deck=False):
    return person("Haru", "하루", pos, face, emo, 1.0, walk, extra, deck=deck)


def wave(ch, t):
    arm(ch, 1, -10, 150 + 18 * math.sin(t * 9.0))


def look_hand(ch, t, side=1, k=1.0):
    arm(ch, side, -78 * k, 12 * k)
    ch.neck.rotation_euler = (math.radians(26 * k), 0, math.radians(-side * 10 * k))


def point_at(ch, t, side=1):
    arm(ch, side, -92, 4)


def bucket(ch, side=1):
    col = TW.load_model("wooden_bucket_01")
    b = TW.instance(col, (0, 0, 0), 0.0, 1.0, name=f"{ch.name}_bucket")
    b.parent = ch.arms[side]
    b.location = (0, 0, -0.85)


# ------------------------------------------------------------------ 카메라
def key_camera(cam, fn):
    for fr in range(f0, f1 + 1):
        u = (fr - f0) / max(1, f1 - f0)
        p, tgt, roll, ln = fn(u)
        cam.location = p
        look.aim(cam, tgt, roll)
        cam.data.lens = ln
        cam.keyframe_insert("location", frame=fr)
        cam.keyframe_insert("rotation_euler", frame=fr)
        cam.data.keyframe_insert("lens", frame=fr)
    act = cam.animation_data.action
    for fc in (act.fcurves if hasattr(act, "fcurves") else []):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def rush_to(target, face_dir, d0, d1, h0, h1, lens=(24, 40), p=2.6, side=0.0, tgt_dz=0.0):
    """target 정면(face_dir 방향) 멀리서 빨려 들어가는 카메라"""
    fd = Vector(face_dir).normalized()
    sd = Vector((fd.y, -fd.x, 0))

    def fn(u):
        e = ease_out(u, p)
        d = mixf(d0, d1, e)
        p_ = Vector(target) + fd * d + sd * side * (1 - e) + Vector((0, 0, mixf(h0, h1, e)))
        return p_, Vector(target) + Vector((0, 0, tgt_dz)), 0, mixf(lens[0], lens[1], e)
    return fn


def orbit(center, r0, r1, a0, a1, h0, h1, lens=30, tgt_dz=0.0, ease=smooth):
    def fn(u):
        e = ease(u)
        a = math.radians(mixf(a0, a1, e))
        r = mixf(r0, r1, e)
        p_ = Vector(center) + Vector((math.cos(a) * r, math.sin(a) * r, mixf(h0, h1, e)))
        return p_, Vector(center) + Vector((0, 0, tgt_dz)), 0, lens if not isinstance(lens, tuple) else mixf(lens[0], lens[1], e)
    return fn


def clampG(fn, m=0.45, ray=False):
    """카메라가 땅속으로 들어가지 않게 (지형 높이 + m 이상)"""
    def f(u):
        p_, t_, r_, l_ = fn(u)
        g = max(float(V.H(p_.x + dx, p_.y + dy)) for dx in (-0.5, 0, 0.5) for dy in (-0.5, 0, 0.5))
        if ray:                                   # 둑·부두 같은 물체 위도 (위에서 아래로 쏴서 표면 찾기)
            dg = bpy.context.evaluated_depsgraph_get()
            for dx in (-0.5, 0, 0.5):
                hit, loc, _n, _i, ob, _m = bpy.context.scene.ray_cast(dg, Vector((p_.x + dx, p_.y, p_.z + 6)), Vector((0, 0, -1)), distance=12)
                if hit and not ob.name.startswith(("Rain", "Smoke", "Fog", "Air", "Ks")):
                    g = max(g, loc.z)
        if p_.z < g + m:
            p_ = Vector((p_.x, p_.y, g + m))
        return p_, t_, r_, l_
    return f


def path(p0, p1, t0_, t1_, lens=(24, 24), ease=smooth, roll=(0, 0)):
    def fn(u):
        e = ease(u)
        return lerp(p0, p1, e), lerp(t0_, t1_, e), mixf(roll[0], roll[1], e), mixf(lens[0], lens[1], e)
    return fn


# ------------------------------------------------------------------ 시기별 공통 세팅
L = SL.timing()
line_of_shot = None
for nm_, st_, _ in SL.RAW:
    if nm_ == shot:
        line_of_shot = st_ if isinstance(st_, int) else (st_[1] if st_[0] == "mid" else None)
if line_of_shot is None:
    line_of_shot = {"sky": 1, "river": 2, "fireroofs": 3, "waterroofs": 4, "firestreet": 5, "night": 6, "waterfall": 7,
                    "rain": 8, "bridge": 9}[shot]
LN = line_of_shot
if shot in ("bridge", "sign", "moss"):          # 표지판: 글씨가 잘리거나 가려질 위험이 없는 컷에만 (규칙)
    bridge_sign()
if LN > 85:
    redline("off")
if 30 <= LN <= 39:
    water(-0.75)
elif 40 <= LN <= 52 or 62 <= LN <= 81:
    water(-2.2)
fire_burning_period = (34 <= LN <= 39) or (64 <= LN <= 80)
water_small = 0.72 if (31 <= LN <= 39 or 64 <= LN <= 81) else 1.0

cam = look.camera((0, 0, 10), (0, 1, 10), lens=24)
mblur = True
fn = None

# ================================================================== A. 오프닝 (1~14)
if shot == "sky":
    light("day")
    def fn(u):
        e = ease_in(u, 2.4)
        return lerp((xr(-260) - 30, -260, 560), (xr(-175), -175, 16), e), lerp((xr(80), 80, 0), (xr(-80), -80, 1), e), 0, 22
elif shot == "river":
    light("day")
    def fn(u):
        y = -165 + 75 * u
        return Vector((xr(y), y, V.water_z + 1.3 + 0.4 * math.sin(u * 3))), Vector((xr(y + 60), y + 60, TZ - 0.5)), 4 * math.sin(u * 2.5), 20
elif shot == "fireroofs":
    light("day")
    for inf in info["towns"]["fire"].info:
        if abs(inf["center"][1] + 80) < 70 and abs(inf["center"][0] - xr(inf["center"][1])) < 90:
            for cp in inf["world"]["chimneys"][:1]:
                fx.chimney_smoke(cp, len([o for o in bpy.data.objects if o.name.startswith("Smoke")]), h=16)
    def fn(u):
        y = -90 + 22 * u
        p = Vector((xr(y) - 2 - 8 * u, y, 7 + 11 * smooth(u)))
        return p, lerp((xr(y + 60), y + 60, 5), (xr(y + 18) - 70, y + 22, 9), smooth(min(1, u * 1.4))), -14 * math.sin(math.pi * u), 22
elif shot == "waterroofs":
    light("day")
    def fn(u):
        y = -66 + 26 * u
        p = Vector((xr(y) - 4 + 14 * u, y, 18 - 4 * smooth(u)))
        return p, lerp((xr(y + 18) - 60, y + 24, 8), (xr(y + 16) + 72, y + 22, 7), smooth(min(1, u * 1.3))), 16 * math.sin(math.pi * u), 22

if shot in ("firestreet", "night"):
    night = shot == "night"
    T = info["towns"]["fire"]
    main = T.streets["main"]
    i0 = min(range(len(main)), key=lambda i: abs(main[i][1] + 120))
    P0 = Vector((main[i0][0], main[i0][1], float(V.H(main[i0][0], main[i0][1]))))
    P1 = Vector((main[i0 + 8][0], main[i0 + 8][1], 0))
    fwd = (P1 - Vector((P0.x, P0.y, 0))).normalized()
    side = Vector((fwd.y, -fwd.x, 0))
    zg = P0.z + 0.07
    lan = TW.load_model("wooden_lantern_01")
    props = [TW.load_model(k) for k in ("wooden_barrels_01", "wooden_crate_01", "barrel_03", "wooden_bucket_01", "wine_barrel_01")]
    r4 = random.Random(4)
    n_s = 0
    for inf in T.info:
        c = Vector(inf["center"])
        d = (c - P0).length
        if d > 140:
            continue
        for lp in inf["world"]["lanterns"]:
            TW.instance(lan, Vector(lp) + Vector((0, 0, -0.25)), inf["yaw"], 1.0)
            if not night and d < 90:
                look.point("Lan", Vector(lp) + Vector((0, 0, -0.05)), 35, (1.0, 0.55, 0.22), 0.06)
        for dp in inf["world"]["doors"]:
            if r4.random() < 0.6:
                off = Matrix.Rotation(inf["yaw"], 3, "Z") @ Vector((r4.choice((-1.3, 1.4)), -0.3, 0))
                TW.instance(r4.choice(props), Vector(dp) + off, r4.uniform(0, 6.28), 1.0)
        if d < 110 and not night:
            for cp in inf["world"]["chimneys"]:
                if r4.random() < 0.55 and n_s < 10:
                    fx.chimney_smoke(cp, n_s); n_s += 1
    if night:
        for m in bpy.data.materials:
            if m.name.startswith("fire_glass_lit"):
                m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0
    fx.embers(tuple(P0 + fwd * 25 + Vector((0, 0, 4))), n=500, spread=(14, 40, 8))
    yaw0 = math.atan2(fwd.y, fwd.x) - math.pi / 2
    spots = [(-1.6, 9, 0), (1.4, 14, math.pi), (-0.4, 21, 0), (2.8, 26, math.pi), (-2.9, 17, 0.6), (-2.2, 18.2, -2.5),
             (3.2, 33, math.pi * 0.9), (-0.9, 39, 0.2), (1.0, 46, math.pi), (-2.4, 55, 0), (2.4, 62, math.pi)]
    chars = []
    for k, (sx, sy, yw) in enumerate(spots):
        p = P0 + side * sx + fwd * sy
        ch, tl = person(f"V{k}", "불주민A" if k % 2 else "불주민B", (p.x, p.y, zg), yaw0 + yw,
                        (("기쁨" if k in (4, 5) else "평온", 0.8),), walk=None if k in (4, 5, 7) else (1.15 + 0.1 * (k % 3), -T0))
        if night:
            Lg = look.point(f"Glow{k}", (0, 0, 0), 70, (1.0, 0.2, 0.04), 0.25)
            Lg.parent = ch.head
            Lg.location = (0, -0.45, 0.5)
            Lg2 = look.point(f"Glow{k}b", (0, 0, 0), 25, (1.0, 0.12, 0.02), 0.3)
            Lg2.parent = ch.head
            Lg2.location = (0, 0.3, 0.6)
        chars.append(ch)
    if not night:
        light("dusk", math.degrees(math.atan2(fwd.y, fwd.x)))
        back = [Vector((main[i][0], main[i][1], 0)) for i in range(i0, -1, -1)]
        cum = [0.0]
        for a_, b_ in zip(back, back[1:]):
            cum.append(cum[-1] + (b_ - a_).length)

        def street_pt(d):
            if d >= cum[-1]:
                return back[-1] + (back[-1] - back[-2]).normalized() * (d - cum[-1])
            j = max(k for k in range(len(cum)) if cum[k] <= d)
            w = (d - cum[j]) / max(1e-6, cum[j + 1] - cum[j])
            return back[j].lerp(back[j + 1], w)

        def fn(u):
            e = ease_out(u, 2.4)
            d = 45.0 - 44.0 * e
            q = sum((street_pt(max(0.0, d + o)) for o in (-4, -2, 0, 2, 4)), Vector()) / 5 + side * (1.5 - 0.9 * e)
            p = Vector((q.x, q.y, P0.z + 16.0 - 14.1 * ease_out(u, 1.6)))
            return p, lerp(P0 + fwd * 15, P0 + fwd * 22 + Vector((0, 0, 1.6)), e), 0, 26
    else:
        light("night")
        walker = chars[2]

        def fn(u):
            t = T0 + u * DUR
            v, t0_, ph = walker.walk
            wpos = walker.base_loc + fwd_of(walker.yaw) * v * (t - t0_)
            p = wpos - fwd * 3.0 + side * (1.2 - 0.4 * u) + Vector((0, 0, 1.15))
            return p, wpos + Vector((0, 0, 1.45)) + fwd * 0.5, -3, 30

elif shot == "waterfall":
    light("day")
    y = -20.0
    gx = xr(y) + rw + 4.0
    gz = float(V.H(gx, y)) + 0.07
    fx.gate((gx, y, gz), 4.4, 5.2, 0.0, mat=bpy.data.materials.get("Quay_stone"), name="DockGate")
    fx.water_curtain((gx, y, gz), 4.4, 5.2, 0.0, name="DockCurtain")
    for k in range(5):
        person(f"W{k}", "물주민A" if k % 2 else "물주민B", (gx + 7.5 + rnd.uniform(-1, 1), y + (k - 2) * 1.7), -math.pi / 2)
    bpy.context.view_layer.update()
    dg0 = bpy.context.evaluated_depsgraph_get()

    def floor_z(x, yy):
        o = Vector((x, yy, 80.0))
        for _ in range(6):
            hit, loc, nor, idx, ob, _m = sc.ray_cast(dg0, o, Vector((0, 0, -1)))
            if not hit:
                return -5.0
            if ob.name.startswith(("Dock", "W", "Ember", "Rain", "Smoke", "Volcano", "Fog")):
                o = loc - Vector((0, 0, 0.01))
                continue
            return loc.z
        return -5.0
    zt = floor_z(gx + 12, y) + 1.3

    def fn(u):
        e = smooth(u)
        p = Vector(lerp((xr(y) - 4, y - 0.6, TZ + 3.4), (gx + 2.6, y + 0.3, gz + 2.0), e))
        p.z = max(p.z, max(floor_z(p.x + dx, p.y) for dx in (-0.6, 0, 0.6, 1.4)) + 1.9)
        return p, Vector((gx + 12, y, max(zt, p.z - 0.4))), 0, 24

elif shot in ("rain", "dance"):
    light("rain")
    pc = Vector((PW.x, PW.y, float(V.H(PW.x, PW.y))))
    for k in range(6):
        ang = 2 * math.pi * k / 6
        p = pc + Vector((math.cos(ang) * 6.2, math.sin(ang) * 6.2, 0))
        yaw = ang + math.pi / 2 + math.pi
        ph = k * 0.9

        def dance(ch, t, ph=ph, yaw=yaw):
            w = t * 5.0 + ph
            ch.root.rotation_euler = (0, 0, yaw + t * 4.2 + ph)
            ch.hip.location.z += abs(math.sin(w)) * 0.12
            arm(ch, -1, -150 + 30 * math.sin(w), 20)
            arm(ch, 1, -150 - 30 * math.sin(w), 20)
        person(f"W{k}", "물주민A" if k % 2 else "물주민B", (p.x, p.y), yaw, (("흥분", 0.9),), extra=dance)
    rain_at((pc.x, pc.y, pc.z), (46, 46, 24), 9000)
    if shot == "rain":
        def fn(u):
            a_ = math.radians(-120 + 70 * smooth(u))
            r = 9.0 - 1.2 * u
            return pc + Vector((math.cos(a_) * r, math.sin(a_) * r, 1.7 + 0.6 * u)), pc + Vector((0, 0, 1.3)), 0, 28
    else:                                      # 83: 다른 각도로 반대쪽에서 돌기, 조금 높게
        fn = orbit(pc, 11.0, 8.5, 60, 140, 3.4, 2.2, lens=26, tgt_dz=1.2)

elif shot == "bridge":
    light("day")

    def fn(u):
        e = smooth(min(1, u * 1.05)) * 0.82 + ease_in(u, 3.0) * 0.18
        p = lerp((xc - 75, yb - 30, 42), (xc - 9, yb - 0.4, DZ(xc - 9) + 1.9), e)
        t = lerp((xc, yb, DZ(xc)), (xc - 1.0, yb - 1.4, DZ(xc) + 1.0), e)
        return p, t, 0, mixf(24, 30, e)

elif shot == "sign":                            # 10: 표지판 글씨까지 빨려듦 (판 전체가 화면 안에)
    light("day")
    sgn = Vector((SIGN_X, SIGN_Y, DZ(SIGN_X) + 1.65))
    fn = rush_to(sgn, (-1, 0.12, 0), 16.0, 3.2, 2.6, 0.05, lens=(26, 30), p=2.4)   # 끝에서 판이 잘리지 않게 (3.2m, 30mm)

elif shot == "feet":                            # 11: 붉은 선 양쪽 불 발 / 물 발, 낮게 밀기
    light("day")
    fp = (xc - 0.55, yb + 0.2)
    wp = (xc + 0.55, yb + 0.1)
    person("F", "불주민A", fp, math.pi / 2, (("결심", 0.8),), deck=True)
    person("Wt", "물주민A", wp, -math.pi / 2, (("결심", 0.8),), deck=True)
    z0 = DZ(xc)
    fn = path((xc - 0.25, yb - 3.1, z0 + 0.4), (xc, yb - 1.7, z0 + 0.3), (xc, yb + 0.2, z0 + 0.3), (xc, yb + 0.2, z0 + 0.35), lens=(30, 36))   # 난간(y-3.4~-3.9) 안쪽에서 시작

elif shot == "legend_steam":                    # 12: 손 닿자 하얀 김 확 -> 위로 급후퇴 (옛이야기, 색 바램은 인코딩 때)
    light("day")
    z0 = DZ(xc)
    fr_hit = f0 + 8
    for k, (px, ff) in enumerate(((xc - 0.5, math.pi / 2), (xc + 0.5, -math.pi / 2))):
        def gone(ch, t, h=fr_hit, k=k):
            if (t * 30 + 1) > h + 9:
                ch.root.scale = (0.001,) * 3
            arm(ch, 1 if k == 0 else -1, -80, 0)
        person(f"L{k}", "불주민B" if k == 0 else "물주민B", (px, yb), ff, (("놀람", 1.0),), deck=True, extra=gone)
    ST.steam((xc, yb, z0 + 0.6), fr_hit, f1, r0=0.8, r1=7.0, h=16)
    fn = path((xc + 0.4, yb - 4.2, z0 + 1.6), (xc + 3, yb - 14, z0 + 16), (xc, yb, z0 + 1.2), (xc, yb, z0 + 4), lens=(30, 22), ease=lambda u: ease_out(u, 2.2))

elif shot == "moss":                            # 13: 상판 위 낙엽·이끼, 천천히 미끄러짐
    light("day")
    ST.leaves_moss(V, yb)
    fn = path((xc - 24, yb - 1.5, DZ(xc - 24) + 0.7), (xc - 12, yb - 0.6, DZ(xc - 12) + 0.9),
              (xc - 10, yb + 0.2, DZ(xc - 10) + 0.2), (xc, yb, DZ(xc) + 0.5), lens=(24, 24))

elif shot == "banks":                           # 14: 양쪽 기슭에서 서로 바라보기, 강 위로 솟음
    light("day")
    crowd(["불주민A", "불주민B"], bank_pts(-1, yb - 24, yb + 16, 16, d0=3.0, d1=6.5), (1, 0, 0), prefix="F")
    crowd(["물주민A", "물주민B"], bank_pts(1, yb - 24, yb + 16, 16, d0=3.0, d1=6.5), (-1, 0, 0), prefix="Wt")
    bx = lambda y: xr(y) - rw - 8.5
    fn = clampG(path(Vector((bx(yb - 16), yb - 16, TZ + 2.2)), Vector((bx(yb - 9) + 2.0, yb - 9, TZ + 2.5)),
                     Vector((xr(yb - 12) + rw + 5, yb - 12, TZ + 0.5)), Vector((xr(yb - 4) + rw + 5, yb - 4, TZ + 0.6)), lens=(26, 34)), m=1.6)

# ================================================================== B. 하루 (15~27)
elif shot == "haru_plaza":                      # 15: 광장 한가운데 혼자 선 하루(의심), 상공에서 얼굴로
    light("dusk", 0)
    hp = PF + Vector((8.0, -4.0, 0))
    fd = Vector((0.35, -1, 0)).normalized()
    h, _ = haru((hp.x, hp.y), fd, (("의심", 0.9),))
    for k in range(9):
        a_ = 2 * math.pi * k / 9 + 0.3
        p = PF + Vector((math.cos(a_) * 17, math.sin(a_) * 17, 0))
        person(f"F{k}", "불주민A" if k % 2 else "불주민B", (p.x, p.y), (hp - p).normalized(), glow=True,
               walk=(0.9, 0) if k % 3 == 0 else None)
    head = P3(hp.x, hp.y, FACE)
    fn = rush_to(head, fd, 34.0, 1.6, 40.0, 0.05, lens=(24, 38), p=2.8)

elif shot in ("haru_walk", "hand"):             # 16/17: 불 마을 강변길, 하루와 빛나는 주민들
    light("dusk", 90)
    y0 = -40.0
    sx = lambda y: xr(y) - rw - 7.0           # 강변길 중심
    if shot == "haru_walk":
        h, _ = haru((sx(y0), y0), (0, 1, 0), (("평온", 0.8),), walk=(1.25, 0))
    else:
        yy = y0 + 1.25 * 2.5
        h, _ = haru((sx(yy), yy), (0, 1, 0), ((0.0, "평온", 0.8), (0.25, "의심", 0.8)),
                    extra=lambda ch, t: look_hand(ch, t, 1, min(1.0, max(0.0, (t - T0) / 0.35))))
    for k in range(10):
        yy = y0 - 6 + k * 3.6 + rnd.uniform(-0.8, 0.8)
        xx = sx(yy) + rnd.choice((-2.4, 2.2)) + rnd.uniform(-0.4, 0.4)
        wk = k % 2 == 0
        person(f"F{k}", "불주민A" if k % 2 else "불주민B", (xx, yy), (0, -1, 0) if wk else (rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0),
               glow=True, walk=(1.1, 0) if wk else None)
    if shot == "haru_walk":
        def fn(u):
            t = T0 + u * DUR
            hy = y0 + 1.25 * (t - T0)
            hp = Vector((sx(hy), hy, G(sx(hy), hy)))
            return hp + Vector((2.7, 0.5 + 0.5 * u, 1.45)), hp + Vector((0, 0.25, 1.15)), 0, 26
    else:
        hp = P3(sx(y0 + 3.1), y0 + 3.1)
        hand_pt = hp + Vector((-0.5, 0.6, 1.2))
        fn = path(hp + Vector((-1.4, 3.6, 1.7)), hp + Vector((-0.7, 1.6, 1.45)), hp + Vector((0, 0, 1.3)), hand_pt, lens=(30, 42))

elif shot == "across":                          # 18: 강 건너 투명한 아이들 쪽으로 휙
    light("dusk", 0)
    y0 = -10.0
    haru((xr(y0) - rw - 4.5, y0), (1, 0, 0))
    for k in range(3):
        person(f"K{k}", "물아이", (xr(y0) + rw + 4.5 + rnd.uniform(-0.3, 0.6), y0 + (k - 1) * 1.6), (-1, 0, 0), (("평온", 0.8),), scale=0.72)
    hb = P3(xr(y0) - rw - 4.5, y0)
    kd = P3(xr(y0) + rw + 4.5, y0, 1.0)
    fn = path(hb + Vector((-1.6, -0.9, 1.9)), kd + Vector((-4.8, -0.8, 1.7)), kd + Vector((-10, 0, 0)), kd + Vector((0, 0, -0.3)), lens=(24, 32),
              ease=lambda u: smooth(ease_out(u, 1.4)))

elif shot == "reflect":                         # 19: 강물에 비친 하루, 수면으로 내려감
    light("dusk", 0)
    y0 = -10.0
    hx = xr(y0) - rw - 3.6
    haru((hx, y0), (1, 0, 0), (("슬픔", 0.5),), extra=lambda ch, t: setattr(ch.neck, "rotation_euler", (math.radians(28), 0, 0)))
    hp = P3(hx, y0)
    wz = V.water_z
    fn = path(Vector((hx + 6.0, y0 - 2.5, TZ + 3.6)), Vector((hx + 6.8, y0 - 1.6, TZ + 2.0)), hp + Vector((0, 0, 1.0)),
              hp + Vector((0.6, 0, 0.7)), lens=(26, 30))

elif shot in ("wave", "orbit21"):               # 20/21: 하루 정면 손 흔듦 / 반 바퀴
    light("day")
    y0 = -10.0
    hx = xr(y0) - rw - 4.5
    if shot == "wave":
        haru((hx, y0), (1, 0, 0), (("기쁨", 0.75),), extra=wave)
        fn = rush_to(P3(hx, y0, FACE - 0.45), (1, 0, 0), 46.0, 1.9, 9.0, 0.6, lens=(22, 28), p=2.6)
    else:
        haru((hx, y0), (1, 0, 0), (("기쁨", 0.6),))
        fn = orbit(P3(hx, y0), 3.4, 3.8, 0, -100, 1.6, 1.9, lens=26, tgt_dz=1.4)

elif shot in ("kids_point", "kids_blow"):       # 22/23: 불꽃 머리 아이들
    light("day")
    y0 = -30.0
    sx = xr(y0) - rw - 7.0
    hp = P3(sx, y0)
    haru((sx, y0), (0, -1, 0), (("당황", 0.7),))
    kids = []
    for k, (dx, dy) in enumerate(((-1.2, -2.4), (0.1, -2.9), (1.3, -2.3), (2.2, -1.4))):
        p = hp + Vector((dx, dy, 0))
        ex = (lambda ch, t: point_at(ch, t, 1)) if shot == "kids_point" else None
        kids.append(person(f"K{k}", "불아이", (p.x, p.y), (hp - p).normalized(), (("기쁨", 1.0),), scale=0.72, extra=ex)[0])
    if shot == "kids_point":
        fn = path(hp + Vector((0.2, -7.0, 1.3)), hp + Vector((0.4, -3.6, 1.15)), hp + Vector((0, 0, 1.3)), hp + Vector((0, 0, 1.5)), lens=(26, 32))
    else:
        bk = hp + Vector((0.6, 0.5, 0))               # 하루 오른쪽 뒤 상자 위에서 머리에 후 부는 아이
        def blow(ch, t):
            ch.hip.rotation_euler = (math.radians(-10), 0, 0)
            ch.neck.rotation_euler = (math.radians(-28), 0, 0)
        import mesh as MS
        cb = MS.MB()
        cb.box("w", (bk.x, bk.y, bk.z + 0.35), (0.75, 0.75, 0.7))
        cb.build("Crate", {"w": pbr.tex_mat("Crate_wood", "medieval_wood", 1.0, tint=pbr.srgb(150, 110, 80))}, bevel=0.02)
        person("Kb", "불아이", (bk.x, bk.y, bk.z + 0.7), (-0.6, -1, 0), ((0.0, "흥분", 0.8), (0.4, "기쁨", 1.2)), scale=0.72, extra=blow)
        kf = bk + Vector((0, 0, 0.7 + FACE * 0.72))
        fn = rush_to(kf, (0.35, -1, 0), 9.0, 1.15, 1.0, 0.0, lens=(26, 40), p=2.8)

elif shot == "water_kids":                      # 24: 강 건너 물 아이들 폭소 + 물방울
    light("day")
    y0 = -10.0
    kx = xr(y0) + rw + 4.8
    for k in range(4):
        def bounce(ch, t, ph=k):
            ch.hip.location.z += abs(math.sin(t * 7 + ph)) * 0.08
            arm(ch, -1, -20, 40 + 20 * math.sin(t * 9 + ph))
            arm(ch, 1, -20, 40 + 20 * math.sin(t * 9 + ph + 1))
        person(f"K{k}", "물아이", (kx + rnd.uniform(-0.3, 0.8), y0 + (k - 1.5) * 1.4), (-1, 0.1 * (k - 1.5), 0), (("기쁨", 1.25),), scale=0.72, extra=bounce)
    for k in range(18):                       # 튀는 물방울 (포물선)
        dp = ST.droplet(f"Spl{k}")
        bx, by = kx + rnd.uniform(-0.5, 0.5), y0 + rnd.uniform(-2.2, 2.2)
        bz = float(V.H(bx, by)) + 0.9
        vx, vy, vz = rnd.uniform(-1.6, 0.4), rnd.uniform(-1, 1), rnd.uniform(2.5, 4)
        ph = rnd.uniform(0, 0.6)
        for fr in range(f0, f1 + 1, 2):
            tt = ((fr - f0) / 30.0 + ph) % 0.9
            dp.location = (bx + vx * tt, by + vy * tt, bz + vz * tt - 4.9 * tt * tt)
            dp.keyframe_insert("location", frame=fr)
    kd = P3(kx, y0, 1.0)
    fn = path(Vector((xr(y0) - rw - 3, y0 - 2, TZ + 4)), kd + Vector((-4.2, -0.5, 0.4)), kd + Vector((-6, 0, 0)), kd, lens=(22, 30),
              ease=lambda u: ease_out(u, 1.8))

elif shot in ("room_frames", "frame_in", "window"):
    light("day")
    ry = yb - 30.0
    rx = xr(ry) - rw - 34.0
    rz = TZ + 3.4
    dvec = Vector((xc - rx, yb - ry, 0)).normalized()
    yaw = yaw_to(dvec)
    ST.hide_near("house_fire", (rx, ry), 9.0)
    R = ST.room((rx, ry, rz), yaw)
    Pr = R["P"]
    if shot == "room_frames":
        mid = (R["frames"][0] + R["frames"][1]) / 2
        fn = path(Vector(Pr(1.2, 1.5, 1.6)), Vector(Pr(0.2, 0.0, 1.7)), mid, mid, lens=(22, 28))
    elif shot == "frame_in":
        fr_ = R["frames"][0]
        inn = Matrix.Rotation(yaw, 3, "Z") @ Vector((1, 0, 0))
        fn = path(fr_ + inn * 2.6 + Vector((0, 0, 0.05)), fr_ + inn * 0.62, fr_, fr_, lens=(24, 30), ease=lambda u: ease_out(u, 2.6))
    else:
        hpos = Vector(Pr(0.55, -1.45, 0))
        haru((hpos.x, hpos.y, rz), dvec, (("슬픔", 0.6),))
        win = R["window"]
        out_ = win + dvec * 11 + Vector((0, 0, 4.0))
        def fn(u):
            if u < 0.45:
                e = smooth(u / 0.45)
                p = lerp(Pr(-0.2, 1.5, 1.6), Pr(-0.15, -1.6, 1.68), e)
            else:
                e = smooth((u - 0.45) / 0.55)
                p = lerp(Pr(-0.15, -1.6, 1.68), out_, e)
            return p, lerp(win + dvec * 30, Vector((xc, yb, DZ(xc))), smooth(u)), 0, mixf(24, 22, u)

# ================================================================== C. 균형이 깨지다 (28~39)
elif shot == "sun":
    light("hot")
    d = sun_disk(52, 205)
    c0 = Vector((xc - 40, yb - 120, 140))
    fn = path(c0 + Vector((0, 0, -60)), c0 + Vector((-10, -20, -40)), Vector((xc - 30, yb, 0)), c0 + d * 1000, lens=(20, 30))

elif shot == "cracks":
    light("hot")
    cx, cy = PF.x - 6.0, PF.y - 12.0                 # 불 마을 광장 빈 땅 (집과 멀리)
    cz = float(V.H(cx, cy)) + 0.03
    ST.crack_ground((cx, cy, cz), (40, 40))
    fn = path(Vector((cx - 6, cy - 9, cz + 14)), Vector((cx + 0.3, cy - 0.5, cz + 0.45)), Vector((cx, cy, cz)), Vector((cx + 0.8, cy + 0.6, cz)),
              lens=(24, 32), ease=lambda u: ease_out(u, 2.5))

elif shot == "lowriver":
    light("hot")
    water(0, (f0, -0.2, f1, -0.75))
    def fn(u):
        y = -150 + 70 * u
        return Vector((xr(y) + 3, y, V.water_z - 0.2 + 1.2)), Vector((xr(y + 50), y + 50, V.water_z - 1)), -3 * math.sin(u * 2), 20

elif shot in ("dock_small", "shrink"):
    light("hot")
    y0 = -20.0
    gx = xr(y0) + rw + 4.5
    if shot == "dock_small":
        for k in range(6):
            person(f"W{k}", "물주민A" if k % 2 else "물주민B", (gx + rnd.uniform(-0.5, 2.5), y0 + (k - 2.5) * 1.6), (-1, 0, 0),
                   (("슬픔", 0.7),), scale=0.72)
        tgt = P3(gx, y0, 0.8)
        fn = rush_to(tgt, (-1, -0.15, 0), 30.0, 1.8, 6.0, 2.0, lens=(22, 24), p=2.4, tgt_dz=-0.45)
    else:
        kp = P3(gx, y0)
        def shrink(ch, t):
            s = 0.72 - 0.34 * smooth(min(1.0, max(0.0, (t - T0) / DUR)))
            ch.root.scale = (s, s, s)
        person("Ks", "물아이", (kp.x, kp.y), (-1, 0, 0), ((0.0, "놀람", 0.8), (0.3, "공포", 1.0)), scale=0.72, extra=shrink)
        fn = clampG(path(kp + Vector((-2.6, -1.5, 1.8)), kp + Vector((-1.3, -0.25, 0.75)), kp + Vector((0, 0, 0.9)), kp + Vector((0, 0, 0.6)),
                         lens=(28, 36)), ray=True)

elif shot == "to_fire":
    light("hot")
    burning((xr(-30) - 60, -30), 60, 6)
    y0 = -30.0
    fn = path(Vector((xr(y0) + 50, y0 - 6, 21)), Vector((xr(y0) - 45, y0 + 4, 19)), Vector((xr(y0) - 20, y0, 6)),
              Vector((xr(y0) - 110, y0 + 6, 2)), lens=(22, 22), ease=lambda u: smooth(ease_out(u, 1.3)))

elif shot == "fire_column":
    light("hot")
    T = info["towns"]["fire"]
    h0 = min(T.info, key=lambda i: (Vector(i["center"][:2]) - Vector((xr(-30) - 40, -30))).length)
    ch_ = h0["world"]["chimneys"][0] if h0["world"]["chimneys"] else tuple(Vector(h0["center"]) + Vector((0, 0, h0["height"])))
    fl = fx.flame(tuple(ch_), 2.0, 0.7, "Pillar", n=5, seed=3, light=True, energy=3000, mat=fx.roof_fire_mat())
    for fr, s in ((f0, 1.0), (f0 + int((f1 - f0) * 0.7), 5.5), (f1, 6.0)):
        fl.scale = (0.6 + s * 0.25, 0.6 + s * 0.25, s)
        fl.keyframe_insert("scale", frame=fr)
    burning(ch_, 40, 4, big=0.8, seed=5)
    c = Vector(ch_)
    fn = path(c + Vector((7, -9, -1)), c + Vector((10, -13, 13)), c + Vector((0, 0, 1)), c + Vector((0, 0, 11)), lens=(26, 24))

elif shot == "burning":
    light("hot")
    y0 = -50.0
    sx = xr(y0) - rw - 7.0
    tops = burning((sx - 8, y0 + 10), 45, 12)
    for k in range(6):
        yy = y0 + k * 4.0
        ch, _ = person(f"F{k}", "불주민A" if k % 2 else "불주민B", (sx + rnd.uniform(-1.8, 1.8), yy), (0, 1, 0), (("공포", 0.8),), walk=(2.6, 0))
        bucket(ch, 1)
    fn = path(Vector((sx - 2, y0 - 12, 20)), Vector((sx - 6, y0 + 22, 18)), Vector((sx - 6, y0 + 10, 4)), Vector((sx - 8, y0 + 50, 3)), lens=(22, 22))

elif shot == "pullback36":
    light("hot")
    y0 = -10.0
    tops = burning((xr(y0) - 40, y0), 30, 8)
    fx_ = xr(y0) - 46
    fn = path(Vector((fx_, y0 - 3, 9)), Vector((fx_ - 22, y0 - 8, 22)), Vector((xr(y0) + 30, y0, 3)), Vector((xr(y0) + 60, y0, 2)),
              lens=(26, 22), ease=lambda u: ease_out(u, 1.6))

elif shot in ("adults", "smith", "boatman"):
    light("hot")
    far_smoke()
    wx, ex_ = xc - HALF + 2.5, xc + HALF - 2.5
    shout = lambda nm: ((0.0, "분노", 1.0),)
    sm, tl1 = person("Smith", "대장장이", (wx, yb), (1, 0, 0), shout("s"), scale=1.08, deck=True, extra=lambda ch, t: point_at(ch, t, 1))
    bm, tl2 = person("Boat", "뱃사공", (ex_, yb), (-1, 0, 0), shout("b"), scale=1.05, deck=True, extra=lambda ch, t: point_at(ch, t, 1))
    for k in range(5):
        person(f"Fa{k}", "불주민A" if k % 2 else "불주민B", (wx - 1.5 - rnd.uniform(0, 3), yb + (k - 2) * 1.3), (1, 0, 0), (("분노", 0.8),), deck=True)
        person(f"Wa{k}", "물주민A" if k % 2 else "물주민B", (ex_ + 1.5 + rnd.uniform(0, 3), yb + (k - 2) * 1.3), (-1, 0, 0), (("분노", 0.8),),
               scale=water_small, deck=True)
    if shot == "adults":
        tl1.say(T0 + 0.1, T0 + DUR, "너희가")
        tl2.say(T0 + 0.3, T0 + DUR, "너희가")
        fn = orbit(Vector((xc, yb, DZ(xc))), 20, 17, -115, -65, 9, 7, lens=22)
    elif shot == "smith":
        tl1.say(T0 + 0.05, T0 + DUR - 0.1, "너희가비를훔쳤다고")
        fn = rush_to(P3(wx, yb, FACE * 1.08), (1, -0.1, 0), 14.0, 1.7, 1.0, 0.0, lens=(26, 38), p=2.8)
    else:
        tl2.say(T0 + 0.05, T0 + DUR - 0.1, "너희가불을키웠다고")
        fn = rush_to(P3(ex_, yb, FACE * water_small), (-1, -0.1, 0), 14.0, 1.5, 1.0, 0.0, lens=(26, 38), p=2.8)

# ================================================================== D. 다리 아래 벽화 (40~52)
elif shot in ("night_bed", "haru_bed", "under", "mural_all", "mural_pan", "mural_hands", "mural_steam", "mural_cloud",
              "mural_rain", "mural_baby", "haru_eyes"):
    light("night")
    M = ST.mural(V, yb)
    at = M["at"]
    bed_z = lambda x, y: float(V.H(x, y)) + 0.05
    if shot == "night_bed":
        look.sun(30, 150, 0.9, (0.6, 0.7, 1.0), 3.0)          # 달빛 보강 (강바닥이 보이게)
        look.point("BedGlow", (xc + 2, yb - 8, float(V.H(xc + 2, yb - 8)) + 3), 900, (0.55, 0.65, 1.0), 6.0)
        fn = path(Vector((xc - 30, yb - 70, 40)), Vector((xc - 3, yb - 34, bed_z(xc, yb - 34) + 3.0)), Vector((xc, yb - 10, -2)),
                  Vector((xc + 2, yb, 0)), lens=(22, 24))
    elif shot == "haru_bed":
        hx = M["center"].x + 3.6
        ys = yb - 22

        def lant(ch, t):
            arm(ch, 1, -35, 5)
        h, _ = haru((hx, ys, bed_z(hx, ys)), (0, 1, 0), (("결심", 0.6),), walk=(1.1, 0), extra=[lant, on_bed := (lambda ch, t: setattr(ch.root.location, "z", bed_z(ch.root.location.x, ch.root.location.y)))])
        ST.lantern(h.arms[1], (0, -0.12, -0.75), 200)

        def fn(u):
            t = T0 + u * DUR
            hy = ys + 1.1 * (t - T0)
            hp = Vector((hx, hy, bed_z(hx, hy)))
            return hp + Vector((0.9, -3.0, 1.9)), hp + Vector((0, 3.0, 1.0)), 0, 28
    elif shot == "under":
        hx = M["center"].x + 3.6
        fn = path(Vector((hx + 0.5, yb - 20, -0.6)), Vector((hx - 0.3, yb - 2.5, -1.2)), Vector((hx, yb + 10, -1.4)), Vector((M["center"].x, yb, -1.0)),
                  lens=(24, 26), ease=lambda u: ease_out(u, 2.2))
        look.point("UnderLan", (hx, yb - 4, -1.6), 160, (1.0, 0.6, 0.3), 0.1)
    else:
        hp = M["center"] + Vector((1.8, 2.4, 0))
        hp.z = bed_z(hp.x, hp.y)
        emo = (("놀람", 0.9),) if shot == "haru_eyes" else (("놀람", 0.6),)
        h, _ = haru((hp.x, hp.y, hp.z), (-1, 0, 0), emo, extra=lambda ch, t: arm(ch, 1, -70, 10))
        ST.lantern(h.arms[1], (0, -0.12, -0.75), 260)
        look.point("MuralFill", M["center"] + Vector((3.0, 0, 0.8)), 90, (1.0, 0.7, 0.45), 1.0)
        n = M["normal"]
        def wall(u_, v_, dist):
            return at(u_, v_) + n * dist
        if shot == "mural_all":
            fn = path(wall(0.42, 0.42, 10.5) + Vector((0, 0, 0.3)), wall(0.5, 0.5, 8.0), wall(0.45, 0.46, 0), wall(0.5, 0.5, 0), lens=(22, 20))
        elif shot == "mural_pan":
            fn = path(wall(0.3, 0.32, 2.3), wall(0.7, 0.32, 2.3), wall(0.3, 0.32, 0), wall(0.7, 0.32, 0), lens=(26, 26))
        elif shot == "mural_hands":
            fn = path(wall(0.5, 0.31, 3.2), wall(0.5, 0.3, 0.75), wall(0.5, 0.31, 0), wall(0.5, 0.3, 0), lens=(24, 32), ease=lambda u: ease_out(u, 2.6))
        elif shot == "mural_steam":
            fn = path(wall(0.5, 0.26, 1.6), wall(0.5, 0.07, 1.9), wall(0.5, 0.26, 0), wall(0.5, 0.07, 0), lens=(26, 26))
        elif shot == "mural_cloud":
            fn = path(wall(0.52, 0.12, 2.0), wall(0.8, 0.13, 2.0), wall(0.52, 0.12, 0), wall(0.8, 0.13, 0), lens=(26, 26))
        elif shot == "mural_rain":
            fn = path(wall(0.8, 0.13, 2.0), wall(0.8, 0.58, 1.8), wall(0.8, 0.13, 0), wall(0.8, 0.58, 0), lens=(26, 26))
        elif shot == "mural_baby":
            def fn(u):
                if u < 0.42:
                    e = ease_out(u / 0.42, 2.6)
                    p = lerp(wall(0.5, 0.6, 3.0), wall(0.5, 0.86, 1.3), e)
                    t = lerp(at(0.5, 0.6), at(0.5, 0.86), e)
                else:
                    e = smooth((u - 0.42) / 0.58)
                    p = lerp(wall(0.5, 0.86, 1.3), wall(0.5, 0.875, 0.62), e)
                    t = at(0.5, 0.875)
                return p, t, 0, 30
        else:                                   # haru_eyes
            fn = rush_to(hp + Vector((0, 0, FACE + 0.04)), (-1, -0.25, 0), 1.7, 0.62, 0.15, -0.02, lens=(28, 45), p=2.8)

# ================================================================== E. 진실 — 회상 (53~61)
elif shot in ("fb_mom", "fb_dad", "fb_face", "fb_hands", "fb_steam"):
    light("day")
    z0 = DZ(xc)
    tmeet = T0 if shot != "fb_mom" else T0 + 99
    if shot in ("fb_mom", "fb_dad"):
        mom = person("Mom", "엄마", (xc + 14, yb + 0.4), (-1, 0, 0), (("평온", 0.8),), walk=(1.2, 0), deck=True)[0]
        dad = person("Dad", "아빠", (xc - 14, yb - 0.4), (1, 0, 0), (("결심", 0.8),), walk=(1.2, 0), deck=True)[0]
        if shot == "fb_mom":
            fn = path(Vector((xc + 40, yb - 30, 30)), Vector((xc + 16, yb - 8, z0 + 3.0)), Vector((xc + 14, yb, z0)),
                      Vector((xc + 11, yb, z0 + 1.0)), lens=(22, 28))
        else:
            dp = Vector((xc - 12.5, yb - 0.4, DZ(xc - 12.5)))
            fn = orbit(dp, 4.5, 4.0, -40, -140, 1.8, 1.6, lens=28, tgt_dz=1.3)
    else:
        hit = f0 + 6 if shot == "fb_steam" else 10 ** 6
        def gone(ch, t, h=hit):
            if (t * 30 + 1) > h + 10:
                ch.root.scale = (0.001,) * 3
        reach = 1 if shot in ("fb_hands", "fb_steam") else 0
        person("Mom", "엄마", (xc + 0.55, yb), (-1, 0, 0), (("기쁨", 0.6),), deck=True,
               extra=[gone, lambda ch, t: arm(ch, -1, -80 * reach, 0)])
        person("Dad", "아빠", (xc - 0.55, yb), (1, 0, 0), (("기쁨", 0.6),), deck=True,
               extra=[gone, lambda ch, t: arm(ch, 1, -80 * reach, 0)])
        if shot == "fb_face":
            fn = path(Vector((xc, yb - 6.5, z0 + 1.6)), Vector((xc, yb - 3.2, z0 + 1.4)), Vector((xc, yb, z0 + 1.2)), Vector((xc, yb, z0 + 1.3)), lens=(28, 32))
        elif shot == "fb_hands":
            hand = Vector((xc, yb + 0.45, z0 + 1.2))
            fn = rush_to(hand, (0, -1, 0.0), 6.0, 0.95, 0.6, 0.05, lens=(28, 40), p=2.8)
        else:
            ST.steam((xc, yb, z0 + 0.8), hit, f1, r0=0.8, r1=7.0, h=16)
            fn = path(Vector((xc + 0.3, yb - 3.8, z0 + 1.6)), Vector((xc + 3, yb - 15, z0 + 17)), Vector((xc, yb, z0 + 1.3)), Vector((xc, yb, z0 + 5)),
                      lens=(30, 22), ease=lambda u: ease_out(u, 2.0))

elif shot == "steam_rise":
    light("day")
    z0 = DZ(xc)
    s = ST.steam((xc, yb, z0 + 0.8), f0 - 30, f0, r0=1.2, r1=9.0, h=40)
    s.keyframe_insert("location", frame=f0)
    s.location.z += 25
    s.keyframe_insert("location", frame=f1)
    fn = path(Vector((xc + 14, yb - 22, z0 + 10)), Vector((xc + 18, yb - 30, z0 + 60)), Vector((xc, yb, z0 + 14)), Vector((xc, yb, z0 + 70)), lens=(22, 22))

elif shot in ("rain_fall", "rain_towns", "wet_line", "new_rain", "fire_calm", "line_wash"):
    light("rain")
    if shot == "rain_fall":
        ST.cloud((xc, yb, 140), (220, 220, 40), seed=1)
        rain_at((xc - 10, yb - 20, 60), (120, 120, 120), 22000)
        fn = path(Vector((xc - 30, yb - 70, 120)), Vector((xc - 20, yb - 40, 14)), Vector((xc, yb, 40)), Vector((xc - 30, yb + 20, 0)), lens=(22, 22))
    elif shot in ("rain_towns", "new_rain"):
        y0 = -60.0
        side_ = -1 if shot == "rain_towns" else 1
        rain_at((xr(y0) + side_ * 60, y0 + 30, 15), (80, 110, 40), 26000)
        hz = 22 if shot == "rain_towns" else 34
        fn = path(Vector((xr(y0) + side_ * 40, y0 - 20, hz)), Vector((xr(y0) + side_ * 70, y0 + 40, hz - 3)), Vector((xr(y0) + side_ * 70, y0 + 20, 2)),
                  Vector((xr(y0) + side_ * 95, y0 + 80, 2)), lens=(22, 22))
        if shot == "new_rain":
            water(-2.2)
    elif shot == "fire_calm":
        y0 = -50.0
        sx = xr(y0) - rw - 7.0
        burning((sx - 8, y0 + 10), 45, 12, calm=True)
        rain_at((sx - 8, y0 + 15, 15), (60, 70, 40), 20000)
        fn = path(Vector((sx + 10, y0 - 30, 58)), Vector((sx + 4, y0 - 12, 50)), Vector((sx - 8, y0 + 10, 4)), Vector((sx - 8, y0 + 12, 2)), lens=(22, 24))
    else:                                        # wet_line / line_wash : 비 젖은 다리, 붉은 선으로
        z0 = DZ(xc)
        rain_at((xc, yb, z0 + 6), (30, 30, 16), 9000)
        if shot == "line_wash":
            redline("on", anim=(f0 + 10, f1 - 15))
        fn = path(Vector((xc - 9, yb + 4.5, z0 + 3.5)), Vector((xc - 1.6, yb + 1.4, z0 + 0.9)), Vector((xc, yb, z0)), Vector((xc, yb + 0.2, z0)), lens=(24, 32),
                  ease=lambda u: ease_out(u, 2.2))

elif shot == "dry_sky":
    light("hot")
    bz = float(V.H(xc - 6, yb - 20)) + 0.4
    fn = path(Vector((xc - 6, yb - 20, bz + 0.6)), Vector((xc - 8, yb - 24, bz + 9)), Vector((xc - 2, yb - 8, bz + 3)), Vector((xc + 30, yb + 60, 260)), lens=(22, 20))

elif shot == "last_drop":
    light("hot")
    dx, dy = xc - 6.0, yb - 16.0
    bz = float(V.H(dx, dy)) + 0.02
    dp = ST.droplet("LastDrop")
    hit_f = f1 - 8
    for fr in range(f0, f1 + 1):
        u = min(1.0, (fr - f0) / max(1, hit_f - f0))
        z = mixf(bz + 9.0, bz + 0.08, ease_in(u, 1.7))
        dp.location = (dx, dy, z)
        dp.scale = (1, 1, 1) if fr < hit_f else (2.2, 2.2, 0.15)
        dp.keyframe_insert("location", frame=fr)
        dp.keyframe_insert("scale", frame=fr)

    def fn(u):
        uu = min(1.0, u * (f1 - f0) / max(1, hit_f - f0))
        z = mixf(bz + 9.0, bz + 0.08, ease_in(uu, 1.7))
        return Vector((dx + 1.4, dy - 1.1, z + 0.5)), Vector((dx, dy, z - 0.3)), 0, 40

# ================================================================== F. 다리를 건너다 (64~76)
elif shot in ("haru_run", "crowd", "shout_smith", "shout_boat", "step", "nothing", "look_hands", "decide", "arms_out",
              "kid_fire", "kid_water", "three", "flow", "mix"):
    light("hot")
    if shot in ("crowd", "arms_out", "shout_smith", "shout_boat"):
        far_smoke()
    z0 = DZ(xc)
    HX = xc + 0.35                          # 선을 넘은 뒤 하루 자리
    if shot in ("crowd", "shout_smith", "shout_boat"):
        fpts = [(xc - HALF - rnd.uniform(1, 6), yb + rnd.uniform(-5, 5)) for _ in range(10)] + bank_pts(-1, yb - 30, yb + 30, 8)
        wpts = [(xc + HALF + rnd.uniform(1, 6), yb + rnd.uniform(-5, 5)) for _ in range(10)] + bank_pts(1, yb - 30, yb + 30, 8)
        emo_c = (("놀람", 1.0),)
        if shot != "crowd":
            sx_ = xc - HALF - 1.0 if shot == "shout_smith" else xc + HALF + 1.0
            fpts = [p for p in fpts if (Vector(p[:2]) - Vector((sx_, yb + 0.6))).length > 2.2 and not (abs(p[1] - yb) < 2 and abs(p[0] - sx_) < 12 and (p[0] - sx_) * (xc - sx_) > 0)]
            wpts = [p for p in wpts if (Vector(p[:2]) - Vector((sx_, yb + 0.6))).length > 2.2 and not (abs(p[1] - yb) < 2 and abs(p[0] - sx_) < 12 and (p[0] - sx_) * (xc - sx_) > 0)]
        crowd(["불주민A", "불주민B"], fpts, lambda p: (Vector((xc, yb, 0)) - Vector((p[0], p[1], 0))).normalized(), emo_c, prefix="F", deck=True)
        crowd(["물주민A", "물주민B"], wpts, lambda p: (Vector((xc, yb, 0)) - Vector((p[0], p[1], 0))).normalized(), emo_c, scale=water_small, prefix="Wt", deck=True)
        haru((xc - 3.0, yb), (1, 0, 0), (("결심", 0.8),), deck=True, walk=(1.4, 0))
        if shot == "crowd":
            gz_ = float(V.H(xc - HALF - 6, yb - 10))
            fn = clampG(path(Vector((xc - HALF - 13, yb - 16, gz_ + 6.5)), Vector((xc - HALF - 3.0, yb - 8.5, gz_ + 2.4)),
                             Vector((xc - HALF - 2, yb, gz_ + 0.6)), Vector((xc - HALF + 2.5, yb, gz_ + 0.9)), lens=(22, 26)), m=1.8)
        else:
            wx = xc - HALF - 1.0 if shot == "shout_smith" else xc + HALF + 1.0
            dirx = 1 if shot == "shout_smith" else -1
            sc_ = 1.08 if shot == "shout_smith" else water_small
            oc = "대장장이" if shot == "shout_smith" else "뱃사공"
            ch, tl = person("Shout", oc, (wx, yb + 0.6), (dirx, 0, 0), ((0.0, "공포", 1.1),), scale=sc_, deck=True,
                            extra=lambda ch, t: (arm(ch, 1, -95, 0), arm(ch, -1, -60, 20)))
            tl.say(T0 + 0.05, T0 + DUR, "멈춰사라질거야")
            fn = rush_to(P3(wx, yb + 0.6, FACE * sc_), (dirx, -0.12, 0), 12.0, 1.6, 0.8, 0.0, lens=(26, 40), p=2.8)
    elif shot == "haru_run":
        xs = xc - 15.0
        haru((xs, yb - 0.3), (1, 0, 0), (("결심", 1.0),), walk=(5.2, 0), deck=True)

        def fn(u):
            t = T0 + u * DUR
            hx = xs + 5.2 * (t - T0)
            hp = Vector((hx, yb - 0.3, DZ(hx)))
            return hp + Vector((-3.4 + 0.8 * u, -0.9, 1.6)), hp + Vector((2.5, 0, 1.2)), 0, 28
    elif shot == "step":
        xs = xc - 1.25
        haru((xs, yb - 0.3), (1, 0, 0), (("결심", 0.9),), walk=(1.2, 0), deck=True)
        # 난간(y-3.4~-3.9) 안쪽에서 시작 (검은 프레임 방지)
        fn = path(Vector((xc - 0.2, yb - 3.1, z0 + 0.32)), Vector((xc + 0.05, yb - 1.5, z0 + 0.28)), Vector((xc, yb - 0.3, z0 + 0.15)),
                  Vector((xc + 0.2, yb - 0.3, z0 + 0.15)), lens=(30, 38))
    else:
        emo = {"nothing": (("평온", 0.6),), "look_hands": (("놀람", 0.9),), "decide": (("결심", 1.1),)}.get(shot, (("결심", 0.9),))
        ex = []
        if shot == "look_hands":
            ex.append(lambda ch, t: (arm(ch, 1, -70, 12), arm(ch, -1, -70, 12), setattr(ch.neck, "rotation_euler", (math.radians(36), 0, 0))))
        spread = {"arms_out": 1, "kid_fire": 2, "kid_water": 2, "three": 2, "flow": 2, "mix": 2}.get(shot, 0)
        if spread == 1:
            ex.append(lambda ch, t: (arm(ch, 1, 0, 85 * smooth(min(1, (t - T0) / 0.6))), arm(ch, -1, 0, 85 * smooth(min(1, (t - T0) / 0.6)))))
        elif spread == 2:
            ex.append(lambda ch, t: (arm(ch, 1, -8, 52), arm(ch, -1, -8, 52)))
        h, _ = haru((HX, yb), (0, -1, 0), emo, extra=ex, deck=True)
        hp = Vector((HX, yb, DZ(HX)))
        # 아이 둘: 화면 왼쪽(서쪽) 불 아이, 오른쪽(동쪽) 물 아이. 하루가 남쪽(카메라)을 봄
        if shot in ("kid_fire", "kid_water", "three", "flow", "mix"):
            hold = lambda ch, t, s=1: arm(ch, s, -8, 70)
            if shot == "kid_fire":
                kf = person("KF", "불아이", (HX - 3.2, yb), (0, -1, 0), ((0.0, "당황", 0.7), (0.6, "기쁨", 0.6)), scale=0.72, walk=(1.5, 0), deck=True)[0]
                kf.yaw = yaw_to((1, 0, 0))
                kf.root.rotation_euler = (0, 0, kf.yaw)
                stop_x = HX - 1.42
                def stopper(ch, t, sx=stop_x):
                    if ch.root.location.x > sx:
                        ch.root.location.x = sx
                        ch.root.rotation_euler = (0, 0, 0)
                        arm(ch, 1, -8, 70)
                kf_ex = actors[-1][2]
                kf_ex.insert(0, stopper)
                kf_ex.append(lambda ch, t: on_deck(ch, t))
            else:
                person("KF", "불아이", (HX - 1.42, yb), (0, -1, 0), (("기쁨", 0.6),), scale=0.72, deck=True, extra=[lambda ch, t: arm(ch, 1, -8, 70)])
            if shot == "kid_water":
                kw = person("KW", "물아이", (HX + 3.2, yb), (-1, 0, 0), ((0.0, "당황", 0.7), (0.6, "기쁨", 0.6)), scale=0.72, walk=(1.5, 0), deck=True)[0]
                stop_x = HX + 1.42
                def stopper2(ch, t, sx=stop_x):
                    if ch.root.location.x < sx:
                        ch.root.location.x = sx
                        ch.root.rotation_euler = (0, 0, 0)
                        arm(ch, -1, -8, 70)
                actors[-1][2].insert(0, stopper2)
                actors[-1][2].append(lambda ch, t: on_deck(ch, t))
            elif shot != "kid_fire":
                person("KW", "물아이", (HX + 1.42, yb), (0, -1, 0), (("기쁨", 0.6),), scale=0.72, deck=True, extra=[lambda ch, t: arm(ch, -1, -8, 70)])
        if shot == "nothing":
            fn = orbit(hp, 4.2, 4.0, -60, 30, 1.7, 1.9, lens=28, tgt_dz=1.3)
        elif shot == "look_hands":
            fn = path(hp + Vector((0.3, -3.4, 1.7)), hp + Vector((0.1, -1.35, 1.5)), hp + Vector((0, -0.4, 1.1)), hp + Vector((0, -0.55, 1.05)), lens=(30, 38))
        elif shot == "decide":
            fn = rush_to(hp + Vector((0, 0, FACE)), (0.1, -1, 0), 9.0, 1.4, 0.6, 0.0, lens=(28, 42), p=2.8)
        elif shot == "arms_out":
            fn = path(hp + Vector((0, -4.0, 1.7)), Vector((xc, yb - 34, z0 + 10)), hp + Vector((0, 0, 1.5)), Vector((xc, yb, z0 + 1)), lens=(26, 22),
                      ease=lambda u: ease_out(u, 1.8))
        elif shot == "kid_fire":
            fn = path(hp + Vector((-3.0, -3.1, 1.6)), hp + Vector((-1.2, -2.3, 1.15)), hp + Vector((-1.2, 0, 1.0)), hp + Vector((-0.9, 0, 0.9)), lens=(26, 32))
        elif shot == "kid_water":
            fn = path(hp + Vector((3.0, -3.1, 1.6)), hp + Vector((1.2, -2.3, 1.15)), hp + Vector((1.2, 0, 1.0)), hp + Vector((0.9, 0, 0.9)), lens=(26, 32))
        elif shot == "three":
            fn = orbit(hp, 5.2, 4.8, -120, -60, 1.5, 2.0, lens=26, tgt_dz=1.0)
        elif shot == "flow":
            chest = hp + Vector((0, -0.2, 1.2))
            for k, (sgn, col) in enumerate(((-1, (1.0, 0.35, 0.05)), (1, (0.2, 0.5, 1.0)))):
                g = ST.glow_ball(f"Flow{k}", col, 14)
                for fr in range(f0, f1 + 1):
                    u = (fr - f0) / max(1, f1 - f0)
                    hand = hp + Vector((sgn * 1.25, -0.25, 1.05))
                    g.location = lerp(hand, chest + Vector((sgn * 0.12, 0, 0)), smooth(u))
                    g.keyframe_insert("location", frame=fr)
            fn = rush_to(chest, (0, -1, 0), 6.0, 1.3, 0.4, 0.1, lens=(26, 36), p=2.4)
        elif shot == "mix":
            chest = hp + Vector((0, -0.2, 1.2))
            ST.glow_ball("MixW", (1.0, 0.95, 0.9), 18, r=0.12).location = chest + Vector((0, -0.1, 0))
            ST.steam(tuple(chest + Vector((0, -0.2, 0.2))), f0 + 10, f1 + 40, r0=0.25, r1=2.5, h=8)
            fn = path(hp + Vector((0.4, -2.2, 1.4)), hp + Vector((0.8, -3.6, 3.2)), chest, chest + Vector((0, 0, 1.4)), lens=(30, 26))

# ================================================================== G. 비 (77~85)
elif shot == "steam_col":
    light("hot")
    far_smoke()
    z0 = DZ(xc)
    for k, x in enumerate((xc - 1.07, xc + 0.35, xc + 1.77)):
        o = ("불아이", "하루", "물아이")[k]
        person(f"T{k}", o, (x, yb), (0, -1, 0), (("기쁨", 0.7),), scale=1.0 if k == 1 else 0.72, deck=True)
    ST.steam((xc + 0.35, yb - 0.1, z0 + 1.4), f0 - 20, f1, r0=0.4, r1=8.0, h=60)
    fn = path(Vector((xc + 6, yb - 10, z0 + 2)), Vector((xc + 16, yb - 30, z0 + 70)), Vector((xc, yb, z0 + 3)), Vector((xc, yb, z0 + 70)), lens=(24, 20))

elif shot == "clouds":                          # 김 기둥 꼭대기에서 구름이 퍼짐 (아래·옆에서 올려다봄)
    light("day")
    for k in range(7):
        a_ = 2 * math.pi * k / 7
        ST.cloud((xc + math.cos(a_) * 70, yb + math.sin(a_) * 70, 140), (90, 90, 26), seed=k)
    ST.cloud((xc, yb, 135), (80, 80, 30), seed=11)
    fn = path(Vector((xc - 90, yb - 150, 70)), Vector((xc - 60, yb - 110, 105)), Vector((xc, yb, 140)), Vector((xc + 20, yb + 30, 150)), lens=(20, 20))

elif shot == "under_clouds":
    light("rain")
    fn = path(Vector((xc - 40, yb - 160, 95)), Vector((xc - 15, yb - 80, 28)), Vector((xc, yb, 0)), Vector((xc, yb + 40, 0)), lens=(22, 22),
              ease=lambda u: ease_in(u, 1.6))

elif shot == "river_rise":
    light("rain")
    water(0, (f0, -2.2, f1, 0.0))
    rain_at((xr(-60), -60, 15), (60, 120, 40), 20000)
    for k, p in enumerate(bank_pts(1, -110, -20, 8, 4.5, 6.0)):
        def grow(ch, t):
            s = 0.72 + 0.28 * smooth(min(1, max(0, (t - T0) / DUR)))
            ch.root.scale = (s, s, s)
        person(f"Wg{k}", "물주민A" if k % 2 else "물주민B", p, (-1, 0, 0), (("기쁨", 0.9),), scale=0.72, extra=grow)

    def fn(u):
        y = -120 + 50 * u
        return Vector((xr(y) + 4, y, 0.6 + 0.4 * u)), Vector((xr(y + 40) + 12, y + 40, 0)), 0, 22

elif shot == "fire_smile":
    light("rain")
    y0 = -40.0
    sx = xr(y0) - rw - 7.0
    rain_at((sx, y0, 10), (30, 30, 20), 9000)
    up = lambda ch, t: setattr(ch.neck, "rotation_euler", (math.radians(-24), 0, 0))
    for k in range(6):
        person(f"F{k}", "불주민A" if k % 2 else "불주민B", (sx + rnd.uniform(-2.5, 2.5), y0 + k * 1.8 - 4), (0, -1, 0), (("기쁨", 1.0),), extra=up)
    hero = P3(sx, y0 - 6)
    person("Fh", "불주민A", (hero.x, hero.y), (0, -1, 0), ((0.0, "놀람", 0.6), (0.5, "기쁨", 1.2)), extra=up)
    fn = rush_to(hero + Vector((0, 0, FACE)), (0, -1, 0), 10.0, 1.3, 2.0, -0.45, lens=(26, 38), p=2.6)

# ================================================================== H. 마무리 (86~94)
elif shot in ("sunset", "gather", "gap", "chain", "night_sky", "night_rain", "haru_moved", "haru_smile", "final"):
    night = shot in ("night_sky", "night_rain", "haru_moved", "haru_smile", "final")
    light("nightrain" if night else "sunset")
    z0 = DZ(xc)
    HX = xc + 0.35
    if shot in ("gather", "chain", "haru_moved", "haru_smile", "final", "sunset", "night_rain"):
        # 하루를 가운데 두고 손잡은 줄: 서쪽 불 사람들, 동쪽 물 사람들 (같은 마을끼리는 손 닿아도 됨)
        hold_l = lambda ch, t: (arm(ch, 1, -6, 62), arm(ch, -1, -6, 62))
        haru((HX, yb), (0, -1, 0), (("기쁨", 0.9),) if shot != "haru_moved" else (("울음", 0.5),), extra=[hold_l], deck=True)
        for k in range(7):
            person(f"F{k}", "불주민A" if k % 2 else "불주민B", (HX - 1.75 - k * 1.75, yb + 0.15 * math.sin(k)), (0, -1, 0), (("기쁨", 0.8),),
                   extra=[hold_l], deck=True, glow=night)
            person(f"Wt{k}", "물주민A" if k % 2 else "물주민B", (HX + 1.75 + k * 1.75, yb + 0.15 * math.cos(k)), (0, -1, 0), (("기쁨", 0.8),),
                   extra=[hold_l], deck=True)
    if night:
        look.point("BridgeWarm", (xc - 4, yb - 3, z0 + 3), 300, (1.0, 0.55, 0.3), 1.5)
        look.point("BridgeCool", (xc + 5, yb - 3, z0 + 3), 200, (0.5, 0.7, 1.0), 1.5)
        if shot in ("night_rain", "haru_moved", "haru_smile", "final"):
            rain_at((xc, yb, z0 + 8), (50, 50, 20), 9000 if shot != "night_rain" else 4000)
    hp = Vector((HX, yb, z0))
    if shot == "sunset":
        fn = path(Vector((xc - 50, yb - 60, 34)), Vector((xc - 5, yb - 11, z0 + 3.2)), Vector((xc, yb, z0)), Vector((xc, yb, z0 + 1.3)), lens=(22, 24))
    elif shot == "gather":
        fn = path(Vector((xc, yb - 26, z0 + 14)), Vector((xc, yb - 11, z0 + 3.0)), Vector((xc, yb, z0)), Vector((xc, yb, z0 + 1.2)), lens=(22, 24))
    elif shot == "gap":
        person("Gf", "불주민A", (xc - 0.42, yb - 2.0), (1, -0.2, 0), (("기쁨", 0.7),), extra=lambda ch, t: arm(ch, 1, -55, 0), deck=True)
        person("Gw", "물주민A", (xc + 0.42, yb - 2.0), (-1, -0.2, 0), (("기쁨", 0.7),), extra=lambda ch, t: arm(ch, -1, -55, 0), deck=True)
        mid = Vector((xc, yb - 2.3, DZ(xc) + 1.2))
        fn = path(mid + Vector((0.2, -4.0, 0.4)), mid + Vector((0.05, -1.2, 0.1)), mid, mid, lens=(30, 38))
    elif shot == "chain":
        fn = path(hp + Vector((0, -3.0, 1.5)), Vector((xc, yb - 26, z0 + 5)), hp + Vector((0, 0, 1.3)), Vector((xc, yb, z0 + 1)), lens=(26, 24),
                  ease=lambda u: ease_out(u, 1.6))
    elif shot == "night_sky":
        md = Vector((math.cos(math.radians(120)), math.sin(math.radians(120)), math.tan(math.radians(28)))).normalized()
        fn = path(Vector((xc + 8, yb - 24, z0 + 6)), Vector((xc + 14, yb - 34, z0 + 22)), Vector((xc, yb, z0 + 1)),
                  Vector((xc, yb, z0 + 22)) + md * 400, lens=(24, 22))
    elif shot == "night_rain":
        fn = path(Vector((xc - 26, yb - 34, z0 + 11)), Vector((xc - 9, yb - 17, z0 + 4.5)), Vector((xc, yb, z0 + 1)), Vector((xc, yb, z0 + 1.3)), lens=(22, 26))
    elif shot == "haru_moved":
        fn = rush_to(hp + Vector((0, 0, FACE)), (0, -1, 0), 14.0, 1.6, 2.5, 0.0, lens=(26, 38), p=2.6)
    elif shot == "haru_smile":
        fn = orbit(hp, 3.0, 2.8, -110, -70, 1.6, 1.7, lens=30, tgt_dz=FACE)
    else:                                       # final: 하루 위로 구름, 강·두 마을·하늘 전경으로 급후퇴
        ST.cloud((xc, yb, 70), (120, 80, 22), seed=9)
        fn = path(hp + Vector((0, -2.2, 1.8)), Vector((xc - 30, yb - 160, 130)), hp + Vector((0, 0, 1.6)), Vector((xc, yb + 40, 30)), lens=(30, 20),
                  ease=lambda u: ease_out(u, 2.2))

if fn is None:
    raise SystemExit(f"no camera for shot {shot}")

key_camera(cam, fn)
if actors:
    bpy.app.handlers.frame_change_pre.append(handler)


def probe():
    dirs = [Vector(d) for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
    skip = ("Ember", "Rain", "Smoke", "Volcano", "Fog", "Street_Haze", "Steam", "Cloud", "Burn", "FarSmoke", "Air", "Flame", "Pillar",
            "Spl", "LastDrop", "Plume")
    bad = []
    prev = None
    for fr in range(f0, f1 + 1):
        sc.frame_set(fr)
        dg = bpy.context.evaluated_depsgraph_get()
        c = cam.matrix_world.translation.copy()
        fwdv = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
        if prev is not None and (c - prev).length > 1e-4:
            hit, loc, nor, idx, ob, _ = sc.ray_cast(dg, prev, (c - prev).normalized(), distance=(c - prev).length + 0.3)
            if hit and not ob.name.startswith(skip):
                bad.append((fr, ob.name, "PASS"))
        prev = c
        for d in dirs + [fwdv]:
            lim = 0.8 if d is fwdv else 0.3
            hit, loc, nor, idx, ob, _ = sc.ray_cast(dg, c, d, distance=lim)
            if hit and not ob.name.startswith(skip):
                inside = nor.dot(d) > 0
                bad.append((fr, ob.name, "IN" if inside else ("front" if d is fwdv else "near"), round((loc - c).length, 2)))
                break
    os.makedirs(os.path.join(OUT, "probe"), exist_ok=True)
    json.dump(bad, open(os.path.join(OUT, "probe", f"{shot}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("PROBE_DONE", shot, len(bad), bad[:6])


look.preset(eng, "final", samples=64, pct=pct, motion_blur=mblur)
sc.render.motion_blur_shutter = 0.22
if eng == "CYCLES":
    sc.render.use_persistent_data = True
sc.frame_start, sc.frame_end = f0, f1
if mode in ("still", "probe"):
    probe()
    if mode == "probe":
        sys.exit(0)
os.makedirs(os.path.join(OUT, "frames"), exist_ok=True)
os.makedirs(os.path.join(OUT, "stills"), exist_ok=True)
times = []
frames = [int(os.environ.get("STILL_F", (f0 + f1) // 2))] if mode == "still" else range(f0, f1 + 1)   # STILL_F: 확인할 프레임 지정
for fr in frames:
    p = os.path.join(OUT, "stills" if mode == "still" else "frames", f"{name}.png" if mode == "still" else f"f{fr:04d}.png")
    if mode != "still" and os.path.exists(p):
        continue
    sc.frame_set(fr)
    sc.render.filepath = p
    t = time.time()
    bpy.ops.render.render(write_still=True)
    times.append(time.time() - t)
st = mon.stop()
st.update(test="film", shot=name, engine=eng, mode=mode, frames=len(times), avg_s=round(sum(times) / max(1, len(times)), 1),
          build_s=round(info["t_build"], 1))
perf.log(st)
print("STATS", json.dumps(st, ensure_ascii=False))
