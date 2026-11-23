import os, sys, bpy
from mathutils import Vector, Matrix
D = os.path.dirname(bpy.data.filepath); sys.path.insert(0, D)
import runtime as RT
import hq_upgrade as HQ
HQ.apply()
sc = bpy.context.scene
for f in (120, 491, 2560):
    sc.frame_set(f)
    for name, info in RT._S["chars"].items():
        num = bpy.data.objects[info["num"]]
        if num.hide_render: continue
        Mi = num.matrix_world.inverted()
        print("F", f, name, "body", repr(num.data.body), "align", num.data.align_x, num.data.align_y, "la", info["larm"]["size"], "scale", num.matrix_world.to_scale())
        dg = bpy.context.evaluated_depsgraph_get()
        ne = num.evaluated_get(dg)
        bb = [Vector(c) for c in ne.bound_box]
        print("  textbb x", min(v.x for v in bb), max(v.x for v in bb), "y", min(v.y for v in bb), max(v.y for v in bb))
        for pr in info["parts"]:
            if pr["name"] in ("LeftUpperArm", "LeftLowerArm", "LeftHand"):
                ob = bpy.data.objects[pr["ob"]]
                pts = [Mi @ (ob.matrix_world @ Vector(c)) for c in ob.bound_box]
                print("  ", pr["name"], "x", round(min(p.x for p in pts),3), round(max(p.x for p in pts),3), "y", round(min(p.y for p in pts),3), round(max(p.y for p in pts),3), "z", round(min(p.z for p in pts),3), round(max(p.z for p in pts),3))
