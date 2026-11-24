"""장면 B: 불 마을 거리 (돌바닥·벽·창·나무·랜턴·노을빛·굴뚝 연기·불티·주민)
장면 C: 하루가 같은 거리에 등장 (배경과 조명·그림자 통합, 얕은 심도)
blender -b --python tests/scene_street.py -- B|C [EEVEE|CYCLES] [samples] [pct] [tag]
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
import library as LB

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
which = a[0] if a else "B"
eng = a[1] if len(a) > 1 else "EEVEE"
spp = int(a[2]) if len(a) > 2 else 64
pct = int(a[3]) if len(a) > 3 else 100
tag = a[4] if len(a) > 4 else ""

look.clear_scene()
mon = perf.Monitor()
info = world_valley.build("full")
V = info["V"]
T = info["towns"]["fire"]
main = T.streets["main"]
# 거리 위 기준점: 큰길 y=-120 부근, 진행 방향 +y (화산 쪽)
i0 = min(range(len(main)), key=lambda i: abs(main[i][1] + 120))
P0 = Vector((main[i0][0], main[i0][1], float(V.H(main[i0][0], main[i0][1]))))
P1 = Vector((main[i0 + 8][0], main[i0 + 8][1], 0))
fwd = (P1 - Vector((P0.x, P0.y, 0))).normalized()
side = Vector((fwd.y, -fwd.x, 0))
zg = P0.z + 0.07

# 노을 (불 마을 분위기): 낮은 해, 따뜻한 하늘
look.world("belfast_sunset_puresky", 0.5, rot_deg=60)
sun = look.sun(27, math.degrees(math.atan2(fwd.y, fwd.x)) + 197, 6.5, (1.0, 0.7, 0.45), 0.8)   # 거리 끝 낮은 해 -> 역광·긴 그림자·빛줄기
look.fog((P0.x - 220, P0.y - 220, P0.z - 5), (P0.x + 220, P0.y + 600, P0.z + 60), density=0.0014, color=(1.0, 0.86, 0.72), anisotropy=0.6, name="StreetHaze")
look.fog((V.x0, V.y0, -20), (V.x1, V.y1, 900), density=0.00009, color=(0.95, 0.8, 0.7), name="Air")

# 근처 집에 랜턴·소품·굴뚝 연기
lan = TW.load_model("wooden_lantern_01")
props = [TW.load_model(k) for k in ("wooden_barrels_01", "wooden_crate_01", "barrel_03", "wooden_bucket_01", "wine_barrel_01")]
rnd = random.Random(4)
n_l = n_s = 0
for inf in T.info:
    c = Vector(inf["center"])
    d = (c - P0).length
    if d > 140:
        continue
    for lp in inf["world"]["lanterns"]:
        TW.instance(lan, Vector(lp) + Vector((0, 0, -0.25)), inf["yaw"], 1.0)
        L = look.point(f"Lan{n_l}", Vector(lp) + Vector((0, 0, -0.05)), 35, (1.0, 0.55, 0.22), 0.06)
        n_l += 1
    for dp in inf["world"]["doors"]:
        if rnd.random() < 0.6:
            k = rnd.choice(props)
            off = Matrix.Rotation(inf["yaw"], 3, "Z") @ Vector((rnd.choice((-1.3, 1.4)), -0.3, 0))
            TW.instance(k, Vector(dp) + off, rnd.uniform(0, 6.28), 1.0)
    if d < 110:
        for cp in inf["world"]["chimneys"]:
            if rnd.random() < 0.55 and n_s < 10:
                fx.chimney_smoke(cp, n_s)
                n_s += 1
fx.embers(tuple(P0 + fwd * 25 + Vector((0, 0, 4))), n=500, spread=(14, 40, 8))
# 거리 가운데 화로 (불 마을 상징)
br = P0 + fwd * 30 + side * 2.2
fx.flame((br.x, br.y, zg + 0.9), 1.0, 0.35, "Brazier", n=3, seed=5, energy=900)
TW.instance(TW.load_model("stone_fire_pit"), (br.x, br.y, zg), 0, 1.4)

# 주민 (걷기·대화·운반·구경) — 같은 동작 반복 없게 시작 시점·속도·자세 다르게
people = []
spots = [(-1.6, 9, 0, "walk"), (1.4, 14, math.pi, "walk"), (-0.4, 21, 0, "walk"), (2.8, 26, math.pi, "walk"),
         (-2.9, 17, 0.6, "talk"), (-2.2, 18.2, -2.5, "talk"), (3.2, 33, math.pi * 0.9, "carry"), (-0.9, 39, 0.2, "look"),
         (1.0, 46, math.pi, "walk"), (-2.4, 55, 0, "walk"), (2.4, 62, math.pi, "walk")]
if which == "C":
    spots = [s for s in spots if s[1] > 13]
yaw0 = math.atan2(fwd.y, fwd.x) - math.pi / 2       # 캐릭터 정면(-Y)이 진행방향 반대 = 카메라 쪽
for k, (sx, sy, yaw, act) in enumerate(spots):
    p = P0 + side * sx + fwd * sy
    p.z = zg
    ch = RC.Char(f"V{k}", "불주민A" if k % 2 else "불주민B", tuple(p), yaw0 + yaw)
    emo = {"walk": "평온", "talk": "기쁨", "carry": "결심", "look": "의심"}[act]
    f, b = LB.target(emo, 0.8, "불마을")
    if act == "talk":
        b["armR_x"], b["armR_z"] = -55, 10
    if act == "carry":
        b["armL_x"] = b["armR_x"] = -80
        TW.instance(props[1], tuple(p + Matrix.Rotation(yaw0 + yaw, 3, "Z") @ Vector((0, -0.55, 1.05))), yaw0 + yaw, 0.55)
    b["breath"] = 0
    ch.pose(b)
    if act == "walk":
        ch.walk = (1.25, 0.0, k * 1.7)
        ch._walk(0.45)
    ch.set_face(f, 0.0)
    people.append(ch)

if which == "B":
    # 기존 컷(대사 6 '불 마을 사람들은')과 같은 방향: 거리 앞쪽 낮은 높이에서 거리 안쪽으로
    cam = look.camera(tuple(P0 - fwd * 3 + side * 0.8 + Vector((0, 0, 2.4))), tuple(P0 + fwd * 40 + Vector((0, 0, 2.2))), lens=28)
else:
    haru_p = P0 + fwd * 6 + side * 0.3
    haru_p.z = zg
    haru = RC.Char("Haru", "하루", tuple(haru_p), yaw0 + 0.25)
    f, b = LB.target("의심", 0.8, "하루")
    fb, bb = LB.target("평온", 1.0, "하루")
    b = dict(bb, head_yaw=-12, head_roll=-5, head_pitch=2)          # 얼굴만 의심, 몸은 자연스럽게
    b["breath"] = 0
    haru.pose(b)
    haru.set_face(f, 0.0)
    hz = zg + 4.6 * RC.STUD
    cpos = haru_p - fwd * 3.3 - side * 0.7
    cpos.z = hz - 0.45
    cam = look.camera(tuple(cpos), tuple(haru_p + Vector((0, 0, 0)) + Vector((0, 0, hz - zg - 0.55)) + fwd * 0.3), lens=42,
                      dof=(haru_p - cpos).length, fstop=2.0)
    # 하루 얼굴용 은은한 반사광 (배경 노을과 같은 색온도, 세기 약하게 -> 다른 조명처럼 안 보이게)
    look.area("Bounce", tuple(haru_p - fwd * 2.5 + side * 1.6 + Vector((0, 0, 1.0))), tuple(haru_p + Vector((0, 0, 1.6))), 60, 2.5, (1.0, 0.82, 0.65))

for nm in os.environ.get("DBG_HIDE", "").split(","):
    for ob in bpy.data.objects:
        if nm and ob.name.startswith(nm):
            ob.hide_render = True
print("SUNDIR", tuple(round(v, 3) for v in (sun.matrix_world.to_3x3() @ Vector((0, 0, -1)))))
if os.environ.get("CAMTOP"):
    cam.location = P0 + fwd * 15 + Vector((0, 0, 90)); look.aim(cam, P0 + fwd * 15)
look.preset(eng, "final", samples=spp, pct=pct)
bpy.context.scene.frame_set(1)
out = os.path.join(D, "..", "out", f"{which}_{eng.lower()}{tag}.png")
bpy.context.scene.render.filepath = out
t = time.time()
if not os.environ.get("NORENDER"): bpy.ops.render.render(write_still=True)
rt = time.time() - t
st = mon.stop()
st.update(scene=which, engine=eng, samples=spp, pct=pct, render_s=round(rt, 1), build_s=round(info["t_build"], 1), lights=n_l)
print("STATS", json.dumps(st))
perf.log(st)
