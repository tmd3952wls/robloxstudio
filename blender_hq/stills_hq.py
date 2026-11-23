"""업그레이드(B) 적용 후 컷마다 한 장씩 확인 렌더.
사용: blender -b market.blend --python stills_hq.py -- <out_dir> <pct> <samples> [shot n ...]
"""
import os, sys, time
import bpy
D = os.path.dirname(bpy.data.filepath); sys.path.insert(0, D)
import runtime as RT  # noqa
import hq_upgrade as HQ  # noqa
args = sys.argv[sys.argv.index("--") + 1:]
out, pct, smp = os.path.join(D, args[0]), int(args[1]), int(args[2])
sel = [int(a) for a in args[3:] if not a.startswith("f=")]
frames = [int(a[2:]) for a in args[3:] if a.startswith("f=")]
sc = bpy.context.scene
HQ.apply()
HQ.eevee_hq(smp)
sc.render.resolution_percentage = pct
sc.render.use_overwrite = True
sc.render.use_placeholder = False
os.makedirs(out, exist_ok=True)
print("CROWD", {k: len(v) for k, v in HQ.HQ["crowd_by_shot"].items()}, flush=True)
for f in frames:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(out, f"frame_{f:04d}.png")
    bpy.ops.render.render(write_still=True)
    print("FRAME", f, flush=True)
for s in ([] if frames and not sel else RT._S["shots"]):
    if sel and s["n"] not in sel:
        continue
    f = int(round((s["start"] + s["dur"] * float(os.environ.get("HQ_U", "0.5"))) * 30)) + 1
    sc.frame_set(f)
    sc.render.filepath = os.path.join(out, f"s{s['n']:02d}_L{s['lines'][0]:02d}_f{f:04d}.png")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print("STILL", s["n"], f, round(time.time() - t, 1), flush=True)
