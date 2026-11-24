"""컷마다 가운데 프레임을 저화질로 한 장씩 렌더해 구도를 확인한다.

사용법: blender --background town_film.blend --python film_runtime.py --python preview_shots.py
"""
import os
import pickle

import bpy

scene = bpy.context.scene
out_dir = os.path.join(os.path.dirname(bpy.data.filepath), "previews")
os.makedirs(out_dir, exist_ok=True)
with open(scene["film_data"], "rb") as f:
    shots = pickle.load(f)["shots"]
scene.render.resolution_percentage = 30
scene.eevee.taa_render_samples = 12
scene.render.use_motion_blur = False
for sh in shots:
    frame = sh["start"] + max(1, sh["count"] // 2)
    scene.frame_set(frame)
    scene.render.filepath = os.path.join(out_dir, f"p{sh['n']:02d}.png")
    bpy.ops.render.render(write_still=True)
print("PREVIEWS DONE", len(shots))
