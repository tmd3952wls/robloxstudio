"""수정 구간 수치 점검: 달리기 발 미끄러짐(52), 병·팔 컷 경계(37→38), 별이 손·어깨를 따라가는지(8, 73), 별 경계 연결(1→4).

사용법: blender --background town_film.blend --python film_runtime.py --python verify_moves.py [-- 52run=부호]
"""
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view

fn = [h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "film_frame"][0]
RT = fn.__globals__
S = RT["_S"]
scene = bpy.context.scene
cam = scene.camera
O = bpy.data.objects
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
scene.frame_set(1)
data = S["data"]
shots = {s["n"]: s for s in data["shots"]}
plan = RT["_plan"]()
out = []


def frame(n, i):
    return shots[n]["start"] + 1 + i


def group_parts(name, g):
    base = S["base"][name][1]
    return [ob for ob, Mb, gg, col, hid in base["parts"] if gg == g and not hid]


def foot_slip(label):
    sh = shots[52]
    res = {}
    for side in ("LL", "RL"):
        prev = None
        slips = []
        for i in range(sh["count"]):
            scene.frame_set(frame(52, i))
            parts = group_parts("Haru", side)
            foot = min(parts, key=lambda o: o.matrix_world.translation.z)
            # 발바닥 = 발 조각의 가장 낮은 꼭짓점
            low = min((foot.matrix_world @ v.co).z for v in foot.data.vertices)
            p = foot.matrix_world.translation.copy()
            if prev is not None and low < 2.0 + 0.6:   # 땅(대략 z 2.5) 근처일 때만
                slips.append(((p - prev[0]).xy.length * 30.0, low))
            prev = (p, low)
        ground = min(l for _, l in slips) if slips else 0
        stance = [s for s, l in slips if l < ground + 0.06]
        res[side] = (sum(stance) / len(stance) if stance else -1, len(stance), ground)
    out.append(f"[52 달리기 {label}] 디딘 발 평균 미끄러짐 속도(스터드/초, 몸 속도 20): "
               + ", ".join(f"{k} {v[0]:.2f} ({v[1]}프레임, 발바닥 최저 {v[2]:.2f})" for k, v in res.items()))


# 1) 달리기
old = list(plan["PLAN"][52]["Haru"])
plan["PLAN"][52]["Haru"] = [("cycle", 20.0, 1.6)]
foot_slip("기존 cycle")
for sg in (1.0, -1.0):
    plan["PLAN"][52]["Haru"] = [old[0][:6] + (sg,)]
    foot_slip(f"새 run 부호 {sg:+.0f}")
plan["PLAN"][52]["Haru"] = old

# 2) 37 -> 38 병·왼팔 위치
def jar_state(n, i):
    scene.frame_set(frame(n, i))
    base = S["base"]["Haru"][1]
    la = group_parts("Haru", "LA")
    glass = [ob for ob in la if ob.color[3] < 0.9]
    hand = min(la, key=lambda o: o.matrix_world.translation.z)
    gp = glass[0].matrix_world.translation.copy() if glass else None
    return gp, hand.matrix_world.translation.copy(), world_to_camera_view(scene, cam, gp) if gp else None


g37, h37, v37 = jar_state(37, shots[37]["count"] - 1)
g38, h38, v38 = jar_state(38, 0)
out.append(f"[37→38] 병 위치 차이 {(g37 - g38).length:.3f} 스터드, 왼팔 끝 차이 {(h37 - h38).length:.3f} 스터드 "
           f"(화면 37끝 {v37.x:.2f},{1 - v37.y:.2f} / 38시작 {v38.x:.2f},{1 - v38.y:.2f})")

# 3) 별이 손·어깨를 따라가는지
for n, actor, g in ((8, "Kid2", "LA"), (73, "Haru", "T"), (74, "Haru", "T")):
    sh = shots[n]
    t_on = plan["STARFX"][n]["attach"][3]
    rel = []
    for i in range(sh["count"]):
        scene.frame_set(frame(n, i))
        if i / 30.0 < t_on:
            continue
        s = O[data["stars"][0]].location.copy()
        parts = group_parts(actor, g)
        anchor = min(parts, key=lambda o: (o.matrix_world.translation - s).length)
        rel.append((s - anchor.matrix_world.translation).length)
        if n == 74 and i / 30.0 > 0.3:
            break
    if rel:
        out.append(f"[{n}] 닿은 뒤 별-{actor} {g} 가장 가까운 조각 거리 변화 {max(rel) - min(rel):.3f} 스터드 ({len(rel)}프레임)")

# 4) 오프닝 별 컷 경계 (화면 위치)
for n in (1, 2, 3, 4):
    sh = shots[n]
    for tag, i in (("시작", 0), ("끝", sh["count"] - 1)):
        scene.frame_set(frame(n, i))
        s = O[data["stars"][0]]
        v = world_to_camera_view(scene, cam, s.location)
        out.append(f"[{n}컷 {tag}] 같은 별 화면 위치 x {v.x:.2f}, 위에서 {1 - v.y:.2f}, 거리 {v.z:.1f}, 크기 {s.scale.x:.2f}")

print("\n".join(out))
with open(bpy.path.abspath("//verify_report.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("VERIFY DONE")
