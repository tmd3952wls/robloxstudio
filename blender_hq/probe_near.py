import os, sys
import bpy
D = os.path.dirname(bpy.data.filepath); sys.path.insert(0, D)
import runtime as RT  # noqa
import hq_upgrade as HQ  # noqa
sc = bpy.context.scene
HQ.apply()
for f in (500, 503, 505, 507):
    sc.frame_set(f)
    c = sc.camera.matrix_world.translation
    print("CAM", f, round(c.x, 1), round(-c.y, 1), round(c.z, 1))
    seen = {}
    for ob in sc.objects:
        if ob.type == "MESH" and "#" in ob.name and not ob.hide_render:
            d = (ob.matrix_world.translation - c).length
            k = ob.name.split("#")[0]
            if d < 4 and (k not in seen or d < seen[k]):
                seen[k] = d
    print("NEAR", f, {k: round(v, 2) for k, v in seen.items()})
