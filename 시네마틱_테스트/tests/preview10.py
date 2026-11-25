"""불과 물의 마을 — 새 시스템 10초 미리보기 (대사 1~10). 컷마다 별도 프로세스로 렌더.
blender -b --python tests/preview10.py -- <컷이름> [still|frames] [pct]
엔진: 먼 전경(sky) = EEVEE 64, 나머지 가까운 컷 = Cycles 64 + OptiX 디노이즈 (실측 기반 추천 조합)
카메라는 프레임마다 키프레임 -> 모션 블러가 정확히 걸림. 배우(걷기·춤·표정)는 frame_change 핸들러.
"""
import os, sys, time, json, math, random
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(D, "..", "lib"))
sys.path.insert(0, os.path.join(D, "..", "emotion"))
import bpy
import numpy as np
from mathutils import Vector, Matrix
import look, world_valley, perf, fx, town as TW, pbr
import roblox_char as RC
import library as LB, anim as AN

# (이름, 시작 프레임, 끝 프레임, 엔진)
SHOTS = [("sky", 1, 21, "EEVEE"), ("river", 22, 62, "CYCLES"), ("fireroofs", 63, 84, "CYCLES"),
         ("waterroofs", 85, 114, "CYCLES"), ("firestreet", 115, 143, "CYCLES"), ("night", 144, 191, "CYCLES"),
         ("waterfall", 192, 221, "CYCLES"), ("rain", 222, 254, "CYCLES"), ("bridge", 255, 300, "CYCLES")]
OUT = os.path.join(D, "..", "out", "preview10")

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["sky"]
shot = a[0]
mode = a[1] if len(a) > 1 else "frames"
pct = int(a[2]) if len(a) > 2 else 100
name, f0, f1, eng = [s for s in SHOTS if s[0] == shot][0]

look.clear_scene()
mon = perf.Monitor()
info = world_valley.build("full")
V = info["V"]
xr = lambda y: float(V.river_x(y))
rw = V.river_w / 2
TZ = V.town_z
sc = bpy.context.scene


def ease_in(u, p=2.2):
    return u ** p


def ease_out(u, p=2.0):
    return 1 - (1 - u) ** p


def smooth(u):
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return Vector(a) + (Vector(b) - Vector(a)) * u


# ------------------------------------------------------------------ 조명 프리셋
def light(kind, along=None):
    if kind == "day":
        look.world("kloofendal_48d_partly_cloudy_puresky", 1.0, rot_deg=40)
        look.sun(32, 205, 4.5)
        look.fog((V.x0, V.y0, -20), (V.x1, V.y1, 900), density=0.00009, color=(0.78, 0.84, 0.95), name="Air")
    elif kind == "dusk":
        look.world("belfast_sunset_puresky", 0.5, rot_deg=60)
        look.sun(27, along + 197, 6.5, (1.0, 0.7, 0.45), 0.8)
        look.fog((V.x0, V.y0, -20), (V.x1, V.y1, 900), density=0.00009, color=(0.95, 0.8, 0.7), name="Air")
    elif kind == "night":
        look.world("belfast_sunset_puresky", 0.035, rot_deg=60, sky_tint=(0.35, 0.45, 1.0))
        look.sun(35, 120, 0.12, (0.55, 0.65, 1.0), 2.0)                       # 달빛
        look.fog((V.x0, V.y0, -20), (V.x1, V.y1, 900), density=0.00012, color=(0.4, 0.5, 0.8), name="Air")
    elif kind == "rain":
        look.world("kloofendal_48d_partly_cloudy_puresky", 0.45, rot_deg=40, sky_tint=(0.7, 0.78, 0.9))
        look.sun(40, 205, 0.9, (0.85, 0.9, 1.0), 12.0)
        look.fog((V.x0, V.y0, -20), (V.x1, V.y1, 900), density=0.00035, color=(0.7, 0.78, 0.88), name="Air")


def key_camera(cam, fn, lens=None):
    """fn(u) -> (위치, 바라볼 점, 롤도, 렌즈) . 프레임마다 키프레임"""
    for fr in range(f0, f1 + 1):
        u = (fr - f0) / max(1, f1 - f0)
        p, tgt, roll, ln = fn(u)
        cam.location = p
        look.aim(cam, tgt, roll)
        cam.data.lens = ln
        cam.keyframe_insert("location", frame=fr)
        cam.keyframe_insert("rotation_euler", frame=fr)
        cam.data.keyframe_insert("lens", frame=fr)
    for fc in (cam.animation_data.action.fcurves if hasattr(cam.animation_data.action, "fcurves") else []):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


actors = []          # (Char, timeline, extra_fn)


def handler(scene, *_):
    t = (scene.frame_current - 1 + scene.frame_subframe) / 30.0
    for ch, tl, extra in actors:
        f, b = tl.eval(t)
        ch.pose(b, t)
        if extra:
            extra(ch, t)
        ch.set_face(f, t)


def fire_street_setup(night=False):
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
    rnd = random.Random(4)
    n_s = 0
    for inf in T.info:
        c = Vector(inf["center"])
        d = (c - P0).length
        if d > 140:
            continue
        for lp in inf["world"]["lanterns"]:
            TW.instance(lan, Vector(lp) + Vector((0, 0, -0.25)), inf["yaw"], 1.0)
            if not night and d < 90:          # 밤에는 등불을 켤 필요가 없음 (대사)
                look.point("Lan", Vector(lp) + Vector((0, 0, -0.05)), 35, (1.0, 0.55, 0.22), 0.06)
        for dp in inf["world"]["doors"]:
            if rnd.random() < 0.6:
                off = Matrix.Rotation(inf["yaw"], 3, "Z") @ Vector((rnd.choice((-1.3, 1.4)), -0.3, 0))
                TW.instance(rnd.choice(props), Vector(dp) + off, rnd.uniform(0, 6.28), 1.0)
        if d < 110 and not night:
            for cp in inf["world"]["chimneys"]:
                if rnd.random() < 0.55 and n_s < 10:
                    fx.chimney_smoke(cp, n_s); n_s += 1
    if night:   # 밤엔 창문 불도 끔
        for m in bpy.data.materials:
            if m.name.startswith("fire_glass_lit"):
                m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0
    fx.embers(tuple(P0 + fwd * 25 + Vector((0, 0, 4))), n=500, spread=(14, 40, 8))
    yaw0 = math.atan2(fwd.y, fwd.x) - math.pi / 2
    spots = [(-1.6, 9, 0), (1.4, 14, math.pi), (-0.4, 21, 0), (2.8, 26, math.pi), (-2.9, 17, 0.6), (-2.2, 18.2, -2.5),
             (3.2, 33, math.pi * 0.9), (-0.9, 39, 0.2), (1.0, 46, math.pi), (-2.4, 55, 0), (2.4, 62, math.pi)]
    chars = []
    for k, (sx, sy, yaw) in enumerate(spots):
        p = P0 + side * sx + fwd * sy
        p.z = zg
        ch = RC.Char(f"V{k}", "불주민A" if k % 2 else "불주민B", tuple(p), yaw0 + yaw)
        tl = AN.Timeline("불마을", seed=k)
        tl.key(0.0, "기쁨" if k in (4, 5) else "평온", 0.8)
        if k not in (4, 5, 7):
            ch.walk = (1.15 + 0.1 * (k % 3), 0.0, k * 1.7)
        if night:   # 몸은 빛나지 않고, 머리 불꽃이 주변을 붉게 비춤
            L = look.point(f"Glow{k}", (0, 0, 0), 70, (1.0, 0.2, 0.04), 0.25)
            L.parent = ch.head
            L.location = (0, -0.45, 0.5)      # 불꽃 높이, 얼굴 앞쪽 -> 얼굴·몸·바닥이 붉게
            L2 = look.point(f"Glow{k}b", (0, 0, 0), 25, (1.0, 0.12, 0.02), 0.3)
            L2.parent = ch.head
            L2.location = (0, 0.3, 0.6)       # 뒤쪽 테두리 빛
        actors.append((ch, tl, None))
        chars.append(ch)
    return P0, fwd, side, zg, chars


def water_people(center, n, radius, face_dir=None, dance=False, seed=0):
    rnd = random.Random(seed)
    out = []
    for k in range(n):
        if dance:
            a = 2 * math.pi * k / n
            p = Vector(center) + Vector((math.cos(a) * radius, math.sin(a) * radius, 0))
            yaw = a + math.pi / 2 + math.pi       # 원 바깥(카메라 쪽)을 보며 춤
        else:
            p = Vector(center) + Vector((rnd.uniform(-1, 1) * radius * 0.5, (k - (n - 1) / 2) * 1.7, 0))
            yaw = face_dir
        p.z = float(V.H(p.x, p.y)) + 0.07
        ch = RC.Char(f"W{k}", "물주민A" if k % 2 else "물주민B", tuple(p), yaw)
        tl = AN.Timeline("물마을", seed=10 + k)
        tl.key(0.0, "흥분" if dance else "평온", 0.9 if dance else 0.8)
        extra = None
        if dance:
            ph = k * 0.9
            def extra(ch, t, ph=ph, yaw=yaw):
                w = t * 5.0 + ph                    # 빙글빙글 + 통통 + 팔 번갈아
                ch.root.rotation_euler = (0, 0, yaw + t * 4.2 + ph)
                ch.hip.location.z += abs(math.sin(w)) * 0.12
                ch.arms[-1].rotation_euler = (math.radians(-150 + 30 * math.sin(w)), math.radians(20), 0)
                ch.arms[1].rotation_euler = (math.radians(-150 - 30 * math.sin(w)), math.radians(-20), 0)
        actors.append((ch, tl, extra))
        out.append(ch)
    return out


# ------------------------------------------------------------------ 컷별
cam = look.camera((0, 0, 10), (0, 1, 10), lens=24)
mblur = True
if shot == "sky":
    light("day")
    def fn(u):
        e = ease_in(u, 2.4)
        p = lerp((xr(-260) - 30, -260, 560), (xr(-175), -175, 16), e)
        t = lerp((xr(80), 80, 0), (xr(-80), -80, 1), e)
        return p, t, 0, 22
elif shot == "river":
    light("day")
    def fn(u):
        y = -165 + 75 * u
        p = Vector((xr(y), y, V.water_z + 1.3 + 0.4 * math.sin(u * 3)))
        return p, Vector((xr(y + 60), y + 60, TZ - 0.5)), 4 * math.sin(u * 2.5), 20
elif shot == "fireroofs":
    light("day")
    for inf in info["towns"]["fire"].info:
        if abs(inf["center"][1] + 80) < 70 and abs(inf["center"][0] - xr(inf["center"][1])) < 90:
            for i, cp in enumerate(inf["world"]["chimneys"][:1]):
                fx.chimney_smoke(cp, len([o for o in bpy.data.objects if o.name.startswith("Smoke")]), h=16)
    def fn(u):
        y = -90 + 22 * u
        p = Vector((xr(y) - 2 - 8 * u, y, 7 + 11 * smooth(u)))
        tf = Vector((xr(y + 60), y + 60, 5))
        tl = Vector((xr(y + 18) - 70, y + 22, 9))
        return p, lerp(tf, tl, smooth(min(1, u * 1.4))), -14 * math.sin(math.pi * u), 22
elif shot == "waterroofs":
    light("day")
    def fn(u):
        y = -66 + 26 * u
        p = Vector((xr(y) - 4 + 14 * u, y, 18 - 4 * smooth(u)))
        tl = Vector((xr(y + 18) - 60, y + 24, 8))
        tr = Vector((xr(y + 16) + 72, y + 22, 7))
        return p, lerp(tl, tr, smooth(min(1, u * 1.3))), 16 * math.sin(math.pi * u), 22
elif shot == "firestreet":
    P0, fwd, side, zg, chars = fire_street_setup(False)
    light("dusk", math.degrees(math.atan2(fwd.y, fwd.x)))
    # 골목이 휘어 있으니 직선 대신 골목 중심선을 따라 내려옴 (집 뚫기 방지)
    main = info["towns"]["fire"].streets["main"]
    i0 = min(range(len(main)), key=lambda i: abs(main[i][1] + 120))
    back = [Vector((main[i][0], main[i][1], 0)) for i in range(i0, -1, -1)]
    cum = [0.0]
    for a_, b_ in zip(back, back[1:]):
        cum.append(cum[-1] + (b_ - a_).length)
    def street_pt(d):                       # P0 에서 골목을 따라 d m 뒤 지점
        if d >= cum[-1]:
            return back[-1] + (back[-1] - back[-2]).normalized() * (d - cum[-1])
        j = max(k for k in range(len(cum)) if cum[k] <= d)
        w = (d - cum[j]) / max(1e-6, cum[j + 1] - cum[j])
        return back[j].lerp(back[j + 1], w)
    def street_smooth(d):
        acc = Vector()
        for o in (-4, -2, 0, 2, 4):
            acc += street_pt(max(0.0, d + o))
        return acc / 5
    def fn(u):
        e = ease_out(u, 2.4)
        d = 45.0 + (1.0 - 45.0) * e
        q = street_smooth(d) + side * (1.5 - 0.9 * e)
        z = P0.z + 16.0 + (1.9 - 16.0) * ease_out(u, 1.6)
        p = Vector((q.x, q.y, z))
        t = lerp(P0 + fwd * 15 + Vector((0, 0, 0)), P0 + fwd * 22 + Vector((0, 0, 1.6)), e)
        return p, t, 0, 26
elif shot == "night":
    P0, fwd, side, zg, chars = fire_street_setup(True)
    light("night")
    walker = chars[2]                                 # (-0.4, 21) 걷는 주민을 따라감
    def fn(u):
        t = (f0 - 1 + u * (f1 - f0)) / 30.0
        v, t0, ph = walker.walk
        wpos = walker.base_loc + (Matrix.Rotation(walker.yaw, 3, "Z") @ Vector((0, -1, 0))) * v * t
        p = wpos - fwd * 3.0 + side * (1.2 - 0.4 * u) + Vector((0, 0, 1.15))
        return p, wpos + Vector((0, 0, 1.45)) + fwd * 0.5, -3, 30
elif shot == "waterfall":
    light("day")
    y = -20.0
    gx = xr(y) + rw + 4.0
    gz = float(V.H(gx, y)) + 0.07
    fx.gate((gx, y, gz), 4.4, 5.2, 0.0, mat=bpy.data.materials.get("Quay_stone"), name="DockGate")
    fx.water_curtain((gx, y, gz), 4.4, 5.2, 0.0, name="DockCurtain")
    water_people((gx + 7.5, y, 0), 5, 4.0, face_dir=-math.pi / 2, seed=3)
    bpy.context.view_layer.update()
    dg0 = bpy.context.evaluated_depsgraph_get()
    def floor_z(x, yy):                     # 그 자리 땅·석축 윗면 높이 (문·물막·사람 제외)
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
        p = lerp((xr(y) - 4, y - 0.6, TZ + 3.4), (gx + 2.6, y + 0.3, gz + 2.0), e)
        p = Vector(p)
        p.z = max(p.z, max(floor_z(p.x + dx, p.y) for dx in (-0.6, 0, 0.6, 1.4)) + 1.9)   # 석축·오르막 위로 띄움
        return p, Vector((gx + 12, y, max(zt, p.z - 0.4))), 0, 24
elif shot == "rain":
    light("rain")
    pc = Vector(info["plaza_water"] + (0,))
    pc.z = float(V.H(pc.x, pc.y))
    water_people((pc.x, pc.y, 0), 6, 6.2, dance=True, seed=5)
    rn = fx.rain((pc.x, pc.y, pc.z), (46, 46, 24), n=9000)
    rn.cycles.use_motion_blur = False          # 빗줄기가 판처럼 번지지 않게
    for m in bpy.data.materials:            # 젖은 돌: 덜 거칠게
        if m.name.startswith("Street"):
            pass
    def fn(u):
        a = math.radians(-120 + 70 * smooth(u))
        r = 9.0 - 1.2 * u
        p = pc + Vector((math.cos(a) * r, math.sin(a) * r, 1.7 + 0.6 * u))
        return p, pc + Vector((0, 0, 1.3)), 0, 28
elif shot == "bridge":
    light("day")
    yb = info["bridge_y"]
    xc = xr(yb)
    dz = TZ + 1.4
    def fn(u):
        e = smooth(min(1, u * 1.05)) * 0.82 + ease_in(u, 3.0) * 0.18
        p = lerp((xc - 75, yb - 30, 42), (xc - 7, yb - 0.4, dz + 1.7), e)
        t = lerp((xc, yb, dz), (xc + 1.0, yb, dz + 0.4), e)
        return p, t, 0, lerp((0, 0, 24), (0, 0, 32), e).z

key_camera(cam, fn)
if actors:
    bpy.app.handlers.frame_change_pre.append(handler)
if os.environ.get("PROBE"):      # 카메라가 물체를 뚫거나 0.35m 안으로 붙는 프레임 검사
    dirs = [Vector(d) for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
    bad = []
    prev = None
    for fr in range(f0, f1 + 1):
        sc.frame_set(fr)
        dg = bpy.context.evaluated_depsgraph_get()
        c = cam.matrix_world.translation.copy()
        if prev is not None and (c - prev).length > 1e-4:
            hit, loc, nor, idx, ob, _ = sc.ray_cast(dg, prev, (c - prev).normalized(), distance=(c - prev).length + 0.35)
            if hit and not ob.name.startswith(("Ember", "Rain", "Smoke", "Volcano", "Fog", "Street_Haze")):
                print("PROBE", fr, (ob.name, "PASS-THROUGH"))
                bad.append((fr, ob.name))
        prev = c
        fwdv = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
        worst = None
        for d in dirs + [fwdv]:
            lim = 1.2 if d is fwdv else 0.35
            hit, loc, nor, idx, ob, _ = sc.ray_cast(dg, c, d, distance=lim)
            if hit and not ob.name.startswith(("Ember", "Rain", "Smoke", "Volcano", "Fog", "Street_Haze")):
                dist = (loc - c).length
                inside = nor.dot(d) > 0          # 뒷면에 맞음 = 물체 안
                if worst is None or inside or dist < worst[1]:
                    worst = (ob.name, round(dist, 2), "IN" if inside else ("front" if d is fwdv else "near"))
                if inside:
                    break
        if worst:
            bad.append((fr, worst))
            print("PROBE", fr, worst)
    print("PROBE_DONE", shot, len(bad))
    sys.exit(0)
look.preset(eng, "final", samples=64, pct=pct, motion_blur=mblur)
sc.render.motion_blur_shutter = 0.22
if eng == "CYCLES":
    sc.render.use_persistent_data = True
sc.frame_start, sc.frame_end = f0, f1
os.makedirs(os.path.join(OUT, "frames"), exist_ok=True)
os.makedirs(os.path.join(OUT, "stills"), exist_ok=True)
times = []
frames = [ (f0 + f1) // 2 ] if mode == "still" else range(f0, f1 + 1)
for fr in frames:
    p = os.path.join(OUT, "stills" if mode == "still" else "frames", f"{name}.png" if mode == "still" else f"f{fr:04d}.png")
    if mode != "still" and os.path.exists(p):
        continue
    sc.frame_set(fr)
    sc.render.filepath = p
    t = time.time()
    bpy.ops.render.render(write_still=True)
    times.append(round(time.time() - t, 1))
st = mon.stop()
st.update(test="preview10", shot=name, engine=eng, mode=mode, frames=len(times), avg_s=round(sum(times) / max(1, len(times)), 1),
          build_s=round(info["t_build"], 1))
perf.log(st)
print("STATS", json.dumps(st, ensure_ascii=False))
