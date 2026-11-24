"""76컷 자동 점검: 타임라인 일치, 프레임 누락, 인물 가림, 화면 가장자리·쇼츠 버튼 영역, 위치 튐, 별 방향.

사용법: blender --background town_film.blend --python film_runtime.py --python check_film.py
결과: check_report.txt
"""
import math
import os
import pickle

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

# 고정 타임라인 (컷, 시작초, 길이초)
TL = [(1, 0.0, 0.9), (2, 0.9, 1.1), (3, 2.0, 1.4), (4, 3.4, 0.9), (5, 4.3, 1.0), (6, 5.3, 0.9), (7, 6.2, 1.5), (8, 7.7, 1.2),
      (9, 8.9, 1.3), (10, 10.2, 1.5), (11, 11.7, 1.6), (12, 13.3, 1.0), (13, 14.3, 1.0), (14, 15.3, 1.2), (15, 16.5, 1.5),
      (16, 18.0, 1.4), (17, 19.4, 1.2), (18, 20.6, 1.2), (19, 21.8, 1.6), (20, 23.4, 0.6), (21, 24.0, 1.3), (22, 25.3, 1.1),
      (23, 26.4, 1.3), (24, 27.7, 0.7), (25, 28.4, 0.8), (26, 29.2, 1.2), (27, 30.4, 1.9), (28, 32.3, 1.6), (29, 33.9, 0.9),
      (30, 34.8, 1.3), (31, 36.1, 1.2), (32, 37.3, 1.3), (33, 38.6, 1.1), (34, 39.7, 0.9), (35, 40.6, 1.0), (36, 41.6, 0.9),
      (37, 42.5, 0.8), (38, 43.3, 1.1), (39, 44.4, 0.7), (40, 45.1, 0.7), (41, 45.8, 0.9), (42, 46.7, 1.8), (43, 48.5, 1.2),
      (44, 49.7, 1.3), (45, 51.0, 0.9), (46, 51.9, 1.4), (47, 53.3, 1.2), (48, 54.5, 1.7), (49, 56.2, 1.7), (50, 57.9, 0.8),
      (51, 58.7, 1.1), (52, 59.8, 1.1), (53, 60.9, 1.2), (54, 62.1, 0.4), (55, 62.5, 0.4), (56, 62.9, 0.4), (57, 63.3, 1.6),
      (58, 64.9, 0.6), (59, 65.5, 1.3), (60, 66.8, 1.7), (61, 68.5, 1.2), (62, 69.7, 1.8), (63, 71.5, 0.8), (64, 72.3, 1.1),
      (65, 73.4, 1.0), (66, 74.4, 1.6), (67, 76.0, 0.8), (68, 76.8, 1.3), (69, 78.1, 1.5), (70, 79.6, 1.0), (71, 80.6, 1.3),
      (72, 81.9, 1.2), (73, 83.1, 1.5), (74, 84.6, 1.0), (75, 85.6, 1.2), (76, 86.8, 2.2)]
# 지시서상 별이 내려가야 하는 컷 / 올라가야 하는 컷
DOWN = {1, 2, 3, 4, 6, 7, 8, 32, 33, 34, 35, 43, 72, 73}
UP = {16, 46, 54, 55, 56, 57, 58, 59, 60, 62, 63, 64, 65, 66, 67, 74, 76}

scene = bpy.context.scene
cam = scene.camera
with open(scene["film_data"], "rb") as f:
    data = pickle.load(f)
shots = data["shots"]
O = bpy.data.objects
lines = []
issues = 0


def report(s):
    global issues
    issues += 1
    lines.append("  ! " + s)


def visible_hit(origin, target, own_prefix):
    """카메라→머리 사이를 가리는 (렌더에 보이는) 물체 이름, 없으면 None"""
    dg = bpy.context.evaluated_depsgraph_get()
    d = target - origin
    dist = d.length
    dirn = d.normalized()
    o = origin.copy()
    for _ in range(12):
        hit, loc, nrm, idx, ob, mtx = scene.ray_cast(dg, o, dirn, distance=dist - (o - origin).length - 0.4)
        if not hit:
            return None
        if ob.hide_render or ob.name.startswith(own_prefix) or ob.name.startswith("FX") or "Star" in ob.name:
            o = loc + dirn * 0.02
            continue
        return ob.name
    return None


# 1) 타임라인
lines.append("[타임라인]")
total = shots[-1]["start"] + shots[-1]["count"]
if len(shots) != 76:
    report(f"컷 수 {len(shots)} (76 이어야 함)")
for (n, st, ln), sh in zip(TL, shots):
    es, ec = round(st * 30), round(ln * 30)
    if sh["n"] != n or sh["start"] != es or sh["count"] != ec:
        report(f"컷 {n}: 시작 {sh['start']}/{es}, 길이 {sh['count']}/{ec}")
    if len(sh["cam"]) != sh["count"]:
        report(f"컷 {n}: 카메라 프레임 {len(sh['cam'])} / {sh['count']}")
lines.append(f"  총 {total} 프레임 (지시 2670), 마지막 컷 끝 {total / 30:.2f}초")

# 2) 컷별 점검
lines.append("[컷별]")
for sh in shots:
    n = sh["n"]
    out = []
    heads = {}
    star_dy, star_cnt = 0.0, 0
    for i in range(sh["count"]):
        scene.frame_set(sh["start"] + 1 + i)
        bpy.context.view_layer.update()
        # 별 방향
        for sn in data["stars"]:
            s = O[sn]
            if not s.hide_render:
                key = sn
                if key in heads.get("_stars", {}):
                    dy = s.location.z - heads["_stars"][key]
                    if abs(dy) < 5:
                        star_dy += dy
                        star_cnt += 1
                heads.setdefault("_stars", {})[key] = s.location.z
        # 인물
        for name, info in data["chars"].items():
            hn = info["head"]
            if not hn or O[hn].hide_render:
                continue
            p = O[hn].matrix_world.translation.copy()
            heads.setdefault(name, []).append((i, p))
            v = world_to_camera_view(scene, cam, p)
            dist = (p - cam.matrix_world.translation).length
            if v.z <= 0 or not (0 <= v.x <= 1 and 0 <= v.y <= 1) or dist > 25:
                continue
            check = i in (0, sh["count"] // 2, sh["count"] - 1)
            if check:
                top = 1 - v.y
                if top < 0.06 or top > 0.94:
                    out.append(f"{name} 머리가 화면 {'위' if top < 0.06 else '아래'} 가장자리 (f{i})")
                if v.x > 0.85 and 0.35 < top < 0.92:
                    out.append(f"{name} 머리가 쇼츠 버튼 영역 (f{i})")
                hit = visible_hit(cam.matrix_world.translation, p, name + "#")
                if hit:
                    out.append(f"{name} 머리를 {hit} 가 가림 (f{i})")
    for name, seq in heads.items():
        if name == "_stars":
            continue
        for (i0, p0), (i1, p1) in zip(seq, seq[1:]):
            lim = 1.2 if n != 52 else 1.6
            if i1 == i0 + 1 and (p1 - p0).length > lim:
                out.append(f"{name} 위치 튐 f{i0}->f{i1} {(p1 - p0).length:.2f}")
    if star_cnt:
        avg = star_dy / star_cnt
        dirn = "아래" if avg < -0.02 else ("위" if avg > 0.02 else "정지")
        if n in DOWN and dirn != "아래":
            out.append(f"별 방향 {dirn} (지시: 아래)")
        if n in UP and dirn != "위":
            out.append(f"별 방향 {dirn} (지시: 위)")
        tag = f"별 {dirn}"
    else:
        tag = "별 없음"
        if n in DOWN or n in UP:
            out.append("지시에 별이 있는데 별 없음")
    seen = sorted(k for k in heads if k != "_stars")
    lines.append(f"컷 {n:2d} ({sh['count']}f) {tag} / 인물 {', '.join(seen) if seen else '-'}")
    for o in dict.fromkeys(out):
        report(o)

lines.insert(0, f"점검 결과: 문제 {issues}건\n")
path = os.path.join(os.path.dirname(bpy.data.filepath), "check_report.txt")
with open(path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print("CHECK DONE", issues, path)
