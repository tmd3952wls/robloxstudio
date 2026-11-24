"""카메라가 물체 속/코앞에 있는 프레임 찾기: blender -b market.blend --python probe_cam.py -- f0 f1 step"""
import os, sys
import bpy
from mathutils import Vector
D = os.path.dirname(bpy.data.filepath); sys.path.insert(0, D)
import runtime as RT  # noqa
import hq_upgrade as HQ  # noqa
a = sys.argv[sys.argv.index("--") + 1:]
f0, f1, step = int(a[0]), int(a[1]), int(a[2])
sc = bpy.context.scene
HQ.apply()
R = 0.9
for f in range(f0, f1 + 1, step):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    cam = sc.camera
    p = cam.matrix_world.translation.copy()
    fwd = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    best = (99.0, "")
    for ob in sc.objects:
        if ob.type != "MESH" or ob.hide_render or ob.name.startswith("HQ_"):
            continue
        mw = ob.matrix_world
        bb = [mw @ Vector(c) for c in ob.bound_box]
        lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
        hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
        if any(p[i] < lo[i] - R or p[i] > hi[i] + R for i in range(3)):
            continue
        inside = all(lo[i] <= p[i] <= hi[i] for i in range(3))
        try:
            ok, cp, n, _ = ob.evaluated_get(dg).closest_point_on_mesh(mw.inverted() @ p)
        except Exception:
            ok = False
        d = ((mw @ cp) - p).length if ok else (0.0 if inside else 99)
        if d < best[0]:
            best = (d, ob.name)
    hit, loc, _, _, hob, _ = sc.ray_cast(dg, p, fwd, distance=1.2)
    flag = "BAD" if best[0] < 0.35 or (hit and not hob.name.startswith("HQ_")) else ""
    print(f"P {f} t={(f - 1) / 30:.2f} near={best[0]:.2f} {best[1]} front={'%s' % hob.name if hit else '-'} {flag}", flush=True)
