"""대표 장면 1프레임 비교 렌더.
사용: blender -b market.blend --python bench.py -- <mode: base|eevee|cycles> <samples> <out.png> <frame> [pct]
"""
import json
import os
import sys
import time

import bpy

D = os.path.dirname(bpy.data.filepath)
sys.path.insert(0, D)
args = sys.argv[sys.argv.index("--") + 1:]
mode, smp, out, frame = args[0], int(args[1]), os.path.join(D, args[2]), int(args[3])
pct = int(args[4]) if len(args) > 4 else 100
t0 = time.time()
import runtime as RT  # noqa: E402

sc = bpy.context.scene
sc.render.resolution_percentage = pct
sc.render.use_overwrite = True
sc.render.use_placeholder = False
info = {"mode": mode, "samples": smp, "frame": frame, "pct": pct}
if mode == "base":
    sc.eevee.taa_render_samples = smp
    sc.frame_set(frame)
else:
    import hq_upgrade as HQ  # noqa: E402
    HQ.apply()
    sc.frame_set(frame)
    info["crowd_lib_faces"] = HQ.HQ["lib_faces"]
    sc.frame_set(frame)
    if mode == "eevee":
        HQ.eevee_hq(smp)
    else:
        info["devices"] = HQ.cycles_hq(smp)
info["setup_s"] = round(time.time() - t0, 2)
sc.render.filepath = out
t1 = time.time()
bpy.ops.render.render(write_still=True)
info["render_s"] = round(time.time() - t1, 2)
print("BENCH " + json.dumps(info, ensure_ascii=False), flush=True)
