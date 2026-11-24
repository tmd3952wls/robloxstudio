"""구도 점검: 컷마다 첫·가운데·끝 프레임을 저화질로 렌더해 시트로 묶는다.

사용법: blender --background town_film.blend --python film_runtime.py --python check_stills.py -- <첫컷> <끝컷> [출력폴더 이름]
"""
import os
import pickle
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if args[0].startswith("list:"):          # -- list:8,9,24 <출력폴더>
    todo = [int(x) for x in args[0][5:].split(",")]
    name = args[1] if len(args) > 1 else "check"
else:
    todo = list(range(int(args[0]), int(args[1]) + 1))
    name = args[2] if len(args) > 2 else "check"
scene = bpy.context.scene
out_dir = os.path.join(os.path.dirname(bpy.data.filepath), name)
os.makedirs(out_dir, exist_ok=True)
with open(scene["film_data"], "rb") as f:
    shots = {s["n"]: s for s in pickle.load(f)["shots"]}
scene.render.resolution_percentage = 22
scene.eevee.taa_render_samples = 6
scene.render.use_motion_blur = False
for n in todo:
    sh = shots[n]
    for tag, i in (("a", 0), ("b", sh["count"] // 2), ("c", sh["count"] - 1)):
        scene.frame_set(sh["start"] + 1 + i)
        scene.render.filepath = os.path.join(out_dir, f"c{n:02d}{tag}.png")
        bpy.ops.render.render(write_still=True)
print("STILLS DONE")
