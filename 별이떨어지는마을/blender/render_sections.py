"""정해진 구간만 최종 화질로 렌더 (파일 번호 = 전체 영화 프레임 번호).

사용법: blender --background town_film.blend --python film_runtime.py --python render_sections.py [-- <출력폴더> <시작-끝> ...]
인자가 없으면 frames_r2 폴더에 지난 수정 구간을 렌더.
"""
import os
import sys

import bpy

SECTIONS = [(1, 129), (187, 267), (1276, 1332), (1795, 1827), (2281, 2388), (2494, 2568)]
folder = "frames_r2"
if "--" in sys.argv:
    args = sys.argv[sys.argv.index("--") + 1:]
    if args:
        folder = args[0]
        SECTIONS = [tuple(int(v) for v in a.split("-")) for a in args[1:]] or SECTIONS
scene = bpy.context.scene
out = os.path.join(os.path.dirname(bpy.data.filepath), folder)
os.makedirs(out, exist_ok=True)
scene.render.filepath = os.path.join(out, "f")
scene.render.use_overwrite = True
for a, b in SECTIONS:
    scene.frame_start, scene.frame_end = a, b
    bpy.ops.render.render(animation=True)
    print("SECTION DONE", a, b)
print("ALL SECTIONS DONE")
