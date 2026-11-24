"""52컷 달리기 정밀 점검: 1/10 프레임 간격으로 발바닥 최저점을 따라가며 디딘 동안의 미끄러짐 속도를 잰다.

사용법: blender --background town_film.blend --python film_runtime.py --python verify_run.py
"""
import bpy

fn = [h for h in bpy.app.handlers.frame_change_pre if h.__name__ == "film_frame"][0]
RT = fn.__globals__
S = RT["_S"]
scene = bpy.context.scene
scene.render.use_motion_blur = False
scene.frame_set(1)
data = S["data"]
sh = [s for s in data["shots"] if s["n"] == 52][0]
plan = RT["_plan"]()
out = []


def parts(g):
    base = S["base"]["Haru"][1]
    return [ob for ob, Mb, gg, col, hid in base["parts"] if gg == g and not hid]


def low_point(g):
    best = None
    for ob in parts(g):
        for v in ob.data.vertices:
            w = ob.matrix_world @ v.co
            if best is None or w.z < best.z:
                best = w
    return best


def measure(label):
    samples = {"LL": [], "RL": []}
    n = sh["count"]
    for i in range(2, n - 2):
        for sub in range(10):
            scene.frame_set(sh["start"] + 1 + i, subframe=sub / 10)
            for g in samples:
                samples[g].append(low_point(g).copy())
    # 디딘 발 = 두 발 중 더 낮은 발. 같은 발이 연속으로 디딘 표본 사이의 수평 이동 속도
    L, R = samples["LL"], samples["RL"]
    floor = min(min(p.z for p in L), min(p.z for p in R))
    sl = []
    for k in range(len(L) - 1):
        a = "LL" if L[k].z <= R[k].z else "RL"
        b = "LL" if L[k + 1].z <= R[k + 1].z else "RL"
        if a == b and samples[a][k].z < floor + 0.05 and samples[a][k + 1].z < floor + 0.05:   # 땅에 닿아 있는 동안만
            p0, p1 = samples[a][k], samples[a][k + 1]
            sl.append((p1 - p0).xy.length * 300.0)
    sl.sort()
    med = sl[len(sl) // 2]
    mean = sum(sl) / len(sl)
    out.append(f"[{label}] 디딘 발 미끄러짐 스터드/초 (몸 속도 20): 중앙값 {med:.2f}, 평균 {mean:.2f}, 표본 {len(sl)}")


# 몸 방향 확인
scene.frame_set(sh["start"] + 5)
base = S["base"]["Haru"][1]
ax = base["joints"]["axes"]
fwd = ax.col[1].normalized()
r0 = base["rigid"][RT["_plan"]()["RIG"]["Haru"]["T"]].translation.copy()
scene.frame_set(sh["start"] + 15)
r1 = S["base"]["Haru"][1]["rigid"][RT["_plan"]()["RIG"]["Haru"]["T"]].translation.copy()
mv = (r1 - r0)
out.append(f"FWD 축 {tuple(round(x, 2) for x in fwd)} / 실제 이동 방향 {tuple(round(x, 2) for x in mv.normalized())} / 이동 속도 {mv.length * 3:.1f}")

old = list(plan["PLAN"][52]["Haru"])
plan["PLAN"][52]["Haru"] = [("cycle", 20.0, 1.6)]
measure("기존 cycle")
plan["PLAN"][52]["Haru"] = old
measure("새 run (뒤꿈치→발끝 구르기)")
print("\n".join(out))
print("RUN DONE")
