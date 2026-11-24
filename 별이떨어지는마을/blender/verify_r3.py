"""이번 수정(r3) 수치 검사 -> verify_r3.txt

1) 오프닝 f0~128: 컷 경계(f27·f60·f102)에서 카메라 위치·방향·속도 연속, 화각 58° 고정, 렌더 카메라 = 기록
2) 마지막 하루 전신이 세로 화면의 몇 %인지, 두 눈이 보이는 각도인지
3) 별 화면 위치(컷 경계), 별이 카메라와 얼굴 사이를 가리는지
4) 비행 중 가장 가까이 스친 지붕·가로등·처마 (거리)
5) 36~42·73~76: 인물 머리가 화면 안에 있고 가려지지 않는지

사용법: blender --background town_film.blend --python film_runtime.py --python verify_r3.py
"""
import math
import os

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

scene = bpy.context.scene
cam = scene.camera
O = bpy.data.objects
out = []
data = None
import pickle
with open(scene["film_data"], "rb") as fh:
    data = pickle.load(fh)
shots = {s["n"]: s for s in data["shots"]}


def cam_at(fr):
    scene.frame_set(fr)
    return cam.matrix_world.copy(), math.degrees(cam.data.angle)


# 1) 오프닝 연속성
out.append("[1] 오프닝 카메라 (f = 0부터 센 프레임)")
mats = []
for f in range(0, 129):
    M, fov = cam_at(f + 1)
    mats.append((M, fov))
rec = []
for n in (1, 2, 3, 4):
    for c in shots[n]["cam"]:
        rec.append(Matrix(c[0]))
maxdiff = max((mats[i][0].translation - rec[i].translation).length for i in range(129))
out.append(f"  렌더 카메라와 기록의 최대 차이 {maxdiff:.4f} 스터드 (0 이면 기록 그대로 적용)")
fovs = sorted(set(round(m[1], 2) for m in mats))
out.append(f"  수평 화각 {fovs}")
for b in (27, 60, 102):
    p = [mats[i][0].translation for i in (b - 2, b - 1, b, b + 1)]
    v0, v1, v2 = (p[1] - p[0]), (p[2] - p[1]), (p[3] - p[2])
    d = [(-mats[i][0].to_3x3().col[2]).normalized() for i in (b - 1, b)]
    out.append(f"  f{b} 경계: 프레임당 이동 {v0.length:.2f} → {v1.length:.2f} → {v2.length:.2f}, "
               f"진행 방향 변화 {math.degrees(v0.angle(v2)) if v0.length > 1e-4 and v2.length > 1e-4 else 0:.1f}°, 시선 변화 {math.degrees(d[0].angle(d[1])):.2f}°")
speeds = [(mats[i + 1][0].translation - mats[i][0].translation).length * 30 for i in range(128)]
imax = max(range(128), key=lambda i: speeds[i])
out.append(f"  최고 속도 {speeds[imax]:.0f} 스터드/초 (f{imax}), f0 {speeds[0]:.0f}, f120 {speeds[120]:.1f}, f127 {speeds[127]:.2f}")

# 2) 마지막 하루 크기·얼굴 각도
info = data["chars"]["Haru"]
for fr in (103, 121, 129):
    scene.frame_set(fr)
    zs = []
    for n in info["parts"].values():
        ob = O[n]
        if ob.hide_render:
            continue
        for corner in ob.bound_box:
            w = ob.matrix_world @ Vector(corner)
            v = world_to_camera_view(scene, cam, w)
            zs.append(v.y)
    head = O[info["head"]]
    fwd = -(head.matrix_world.to_3x3().col[1]).normalized()      # 머리 앞쪽(로블록스 -Z) = 블렌더 -Y 로컬
    to_cam = (cam.matrix_world.translation - head.matrix_world.translation).normalized()
    ang = math.degrees(math.acos(max(-1, min(1, Vector((fwd.x, fwd.y, 0)).normalized().dot(Vector((to_cam.x, to_cam.y, 0)).normalized())))))
    out.append(f"  f{fr - 1}: 하루 전신 세로 {100 * (max(zs) - min(zs)):.0f}% (화면 아래 {100 * min(zs):.0f}% ~ 위 {100 * max(zs):.0f}%), 얼굴과 카메라 수평 각도 {ang:.0f}°")

# 3) 별 위치
out.append("[3] 오프닝 별 (화면 가로, 위에서부터 세로)")
star = O[data["stars"][0]]
for fr in (1, 27, 28, 60, 61, 102, 103, 111, 129):
    scene.frame_set(fr)
    v = world_to_camera_view(scene, cam, star.location)
    head = O[info["head"]].matrix_world.translation
    c = cam.matrix_world.translation
    seg = head - c
    t = max(0.0, min(1.0, (star.location - c).dot(seg) / seg.length_squared))
    gap = (c + seg * t - star.location).length
    vis = "화면 안" if (v.z > 0 and 0 <= v.x <= 1 and 0 <= v.y <= 1) else "화면 밖"
    out.append(f"  f{fr - 1}: ({v.x:.2f}, {1 - v.y:.2f}) {vis}, 크기 {star.scale.x:.2f}, 카메라-얼굴 선에서 {gap:.1f} 떨어짐")

# 4) 스쳐 지나간 가까운 물체
out.append("[4] 비행 중 카메라에서 가장 가까웠던 세트 물체 (프레임별 최소)")
cands = [o for o in scene.objects if o.type == "MESH" and not o.hide_render and (o.name.startswith(("Dressing", "Houses", "Props")))]
centers = [(o, o.matrix_world.translation.copy(), max(o.dimensions) * 0.5) for o in cands]
KIND = {"Dressing": "새 소품(별등·깃발·처마)", "Houses": "집", "Props": "광장·가로등 소품"}
for f in range(56, 104, 4):
    c = mats[f][0].translation
    best, bd = None, 1e9
    for o, ctr, rad in centers:
        if (ctr - c).length - rad > 20:
            continue
        Mi = o.matrix_world.inverted()
        ok, p, n, idx = o.closest_point_on_mesh(Mi @ c)
        if ok:
            dd = (o.matrix_world @ p - c).length
            if dd < bd:
                best, bd = o, dd
    if best:
        out.append(f"  f{f}: {KIND.get(best.name.split('_')[0], best.name)} {best.name} {bd:.1f} 스터드")
    else:
        out.append(f"  f{f}: 20스터드 안에 없음")


# 5) 인물 컷
def visible_hit(origin, target, own_prefix):
    dg = bpy.context.evaluated_depsgraph_get()
    d = target - origin
    dist = d.length
    dirn = d.normalized()
    o = origin.copy()
    for _ in range(12):
        hit, loc, nrm, idx, ob, mtx = scene.ray_cast(dg, o, dirn, distance=dist - (o - origin).length - 0.4)
        if not hit:
            return None
        if ob.hide_render or ob.name.startswith(own_prefix) or "star" in ob.name.lower() or "tail" in ob.name.lower():
            o = loc + dirn * 0.02
            continue
        return ob.name
    return None


out.append("[5] 인물 컷 머리 위치 (가로, 위에서부터) / 가림")
for n in (36, 37, 38, 39, 40, 41, 50, 52, 73, 74, 75, 76):
    sh = shots[n]
    for i in (0, sh["count"] // 2, sh["count"] - 1):
        scene.frame_set(sh["start"] + 1 + i)
        row = []
        for name in sh["chars"]:
            hn = data["chars"][name]["head"]
            h = O[hn]
            if h.hide_render:
                continue
            p = h.matrix_world.translation
            v = world_to_camera_view(scene, cam, p)
            hit = visible_hit(cam.matrix_world.translation, p, name + "#")
            row.append(f"{name}({v.x:.2f},{1 - v.y:.2f}{' 가림:' + hit if hit else ''})")
        out.append(f"  컷{n} f{i}: " + " ".join(row))

txt = "\n".join(out)
print(txt)
open(os.path.join(os.path.dirname(bpy.data.filepath), "verify_r3.txt"), "w", encoding="utf-8").write(txt)
