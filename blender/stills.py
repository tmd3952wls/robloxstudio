"""컷마다 한 장씩 저해상도 확인 렌더.
사용: blender -b market.blend --python runtime.py --python stills.py -- <out_dir> <percent> <samples> [u=0.5] [shot번호들...]
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(bpy.data.filepath))
import shots as SH  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
out, pct, smp = os.path.abspath(os.path.join(os.path.dirname(bpy.data.filepath), args[0])), int(args[1]), int(args[2])
u = 0.5
sel = []
for a in args[3:]:
    if a.startswith("u="):
        u = float(a[2:])
    else:
        sel.append(int(a))
sc = bpy.context.scene
sc.render.resolution_percentage = pct
sc.eevee.taa_render_samples = smp
sc.render.use_overwrite = True
os.makedirs(out, exist_ok=True)
for s in SH.SHOTS:
    if sel and s["n"] not in sel:
        continue
    f = int(round((s["start"] + s["dur"] * u) * 30)) + 1
    sc.frame_set(f)
    sc.render.filepath = os.path.join(out, f"s{s['n']:02d}_f{f:04d}.png")
    bpy.ops.render.render(write_still=True)
    print("STILL", s["n"], f, flush=True)
