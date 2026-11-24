"""연기 확인용: 지정한 컷의 몇 지점을 저화질로 렌더.

사용법: blender --background town_film.blend --python film_runtime.py --python test_anim.py -- 컷:위치,위치 ...
예: -- 22:0.2,0.7 52:0.5
"""
import os
import pickle
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
scene = bpy.context.scene
out_dir = os.path.join(os.path.dirname(bpy.data.filepath), "anim_test")
os.makedirs(out_dir, exist_ok=True)
with open(scene["film_data"], "rb") as f:
    shots = {s["n"]: s for s in pickle.load(f)["shots"]}
scene.render.resolution_percentage = 35
scene.eevee.taa_render_samples = 12
scene.render.use_motion_blur = False
for a in args:
    n, us = a.split(":")
    if us == "all":       # 컷 전체를 연속 프레임으로
        sh = shots[int(n)]
        scene.render.resolution_percentage = 20
        scene.eevee.taa_render_samples = 4
        for i in range(sh["count"]):
            scene.frame_set(sh["start"] + 1 + i)
            scene.render.filepath = os.path.join(out_dir, "seq", f"s{int(n):02d}_{i:03d}.png")
            bpy.ops.render.render(write_still=True)
        continue
    sh = shots[int(n)]
    for u in us.split(","):
        fr = sh["start"] + 1 + min(int(float(u) * sh["count"]), sh["count"] - 1)
        scene.frame_set(fr)
        scene.render.filepath = os.path.join(out_dir, f"p{int(n):02d}_{u}.png")
        bpy.ops.render.render(write_still=True)
print("TEST DONE")
