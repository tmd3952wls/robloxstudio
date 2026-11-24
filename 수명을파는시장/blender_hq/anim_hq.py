"""구간 미리보기: blender -b market.blend --python anim_hq.py -- <out_dir> <pct> <samples> <f0> <f1>"""
import os, sys
import bpy
D = os.path.dirname(bpy.data.filepath); sys.path.insert(0, D)
import runtime as RT  # noqa
import hq_upgrade as HQ  # noqa
a = sys.argv[sys.argv.index("--") + 1:]
out, pct, smp, f0, f1 = os.path.join(D, a[0]), int(a[1]), int(a[2]), int(a[3]), int(a[4])
sc = bpy.context.scene
HQ.apply(); HQ.eevee_hq(smp)
sc.render.resolution_percentage = pct
sc.render.use_overwrite = True; sc.render.use_placeholder = False
os.makedirs(out, exist_ok=True)
skip = os.environ.get("HQ_SKIP_EXISTING") == "1"
for f in range(f0, f1 + 1):
    fp = os.path.join(out, f"f{f:04d}.png")
    if skip and os.path.exists(fp) and os.path.getsize(fp) > 100000:
        continue
    sc.frame_set(f)
    sc.render.filepath = fp
    bpy.ops.render.render(write_still=True)
    print("F", f, flush=True)
