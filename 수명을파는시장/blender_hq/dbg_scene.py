import os, sys, bpy
from collections import Counter
D = os.path.dirname(bpy.data.filepath); sys.path.insert(0, D)
import runtime as RT
RT._init()
print("DYN", {k: len(v) for k, v in RT._S["dyn"].items()})
for n in RT._S["dyn"].get("Door", []):
    ob = bpy.data.objects[n]
    t = ob.matrix_world.translation
    print("DOOR", n, round(t.x, 2), round(t.z, 2), round(-t.y, 2), [round(v, 2) for v in ob.dimensions])
def rb(ob):
    t = ob.matrix_world.translation
    return t.x, t.z, -t.y
for reg, (x0, x1, z0, z1) in {"shop": (385, 420, -15, 15), "attic": (455, 485, -15, 15)}.items():
    c = Counter()
    for ob in bpy.data.objects:
        if ob.type != "MESH" or "#" in ob.name and ob.name.split("#")[0] in RT._S["chars"]:
            continue
        x, y, z = rb(ob)
        if x0 <= x <= x1 and z0 <= z <= z1:
            print("OBJ", reg, ob.name, round(x, 1), round(y, 1), round(z, 1), [round(v, 1) for v in ob.dimensions])
