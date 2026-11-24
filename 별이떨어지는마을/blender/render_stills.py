"""지정한 프레임만 빠르게 렌더해 구도·조명 확인 (샘플 수를 낮춤).

사용법: blender --background town_film.blend --python film_runtime.py --python render_stills.py -- <출력폴더> <샘플> <프레임...>
"""
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out, samples, frames = argv[0], int(argv[1]), [int(x) for x in argv[2:]]
os.makedirs(out, exist_ok=True)
scene = bpy.context.scene
scene.eevee.taa_render_samples = samples
for fr in frames:
    scene.frame_set(fr)
    scene.render.filepath = os.path.join(out, f"s{fr:04d}.png")
    bpy.ops.render.render(write_still=True)
    print("STILL", fr)
