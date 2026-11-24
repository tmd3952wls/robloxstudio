import os, sys
import bpy
from mathutils import Vector
D = os.path.dirname(bpy.data.filepath); sys.path.insert(0, D)
import runtime as RT  # noqa
import hq_upgrade as HQ  # noqa
sc = bpy.context.scene
HQ.apply()
def rb(v):
    return (round(v.x, 2), round(v.z, 2), round(-v.y, 2))
for n in ["Houses.Part.1173", "Houses.Part.1146", "Stalls.Part.286", "Stalls.PriceTag.008", "Lamps.Part.202"]:
    ob = bpy.data.objects[n]
    bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]; ys = [v.z for v in bb]; zs = [-v.y for v in bb]
    print("O", n, "x", round(min(xs), 1), round(max(xs), 1), "y", round(min(ys), 1), round(max(ys), 1), "z", round(min(zs), 1), round(max(zs), 1))
for f in [1, 10, 16, 17, 18, 19, 20, 25, 30, 34, 38, 41, 43, 50, 60]:
    sc.frame_set(f)
    print("C", f, rb(sc.camera.matrix_world.translation))
