"""수정 카메라가 실제 렌더 카메라에 들어가는지 확인: 기존(film_data_r1.pkl) vs 새 기록, 그리고 frame_set 후 장면 카메라 위치.

사용법: blender --background town_film.blend --python film_runtime.py --python verify_cam.py
"""
import os
import pickle

import bpy
from mathutils import Matrix

scene = bpy.context.scene
d = os.path.dirname(bpy.data.filepath)
old = {s["n"]: s for s in pickle.load(open(os.path.join(d, "film_data_r1.pkl"), "rb"))["shots"]}
new = {s["n"]: s for s in pickle.load(open(os.path.join(d, "film_data.pkl"), "rb"))["shots"]}
out = []
for n in (1, 2, 3, 4, 7, 8, 37, 38, 52, 67, 68, 69, 73, 74):
    for i in (0, new[n]["count"] - 1):
        o = Matrix(old[n]["cam"][i][0]).translation
        w = Matrix(new[n]["cam"][i][0]).translation
        scene.frame_set(new[n]["start"] + 1 + i)
        c = scene.camera.matrix_world.translation
        out.append(f"컷{n:2d} f{i:2d}  기존 ({o.x:7.1f},{o.y:7.1f},{o.z:6.1f}) fov {old[n]['cam'][i][1]:4.1f}  →  새 기록 ({w.x:7.1f},{w.y:7.1f},{w.z:6.1f}) fov {new[n]['cam'][i][1]:4.1f}"
                   f"  | 렌더 카메라 ({c.x:7.1f},{c.y:7.1f},{c.z:6.1f}) fov {scene.camera.data.angle * 57.2958:4.1f}  일치 {(c - w).length < 0.01}")
print("\n".join(out))
open(os.path.join(d, "verify_cam.txt"), "w", encoding="utf-8").write("\n".join(out))
