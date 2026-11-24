import os, sys, bpy, math
from mathutils import Vector
D = os.path.dirname(bpy.data.filepath); sys.path.insert(0, D)
import runtime as RT, hq_upgrade as HQ
HQ.apply()
for sh in RT._S["shots"]:
    if sh["lines"][0] in (10, 70):
        t = sh["dur"] * 0.3
        P, L, fov = HQ._cam_eval(sh["cam"], "lin", t)
        print("L", sh["lines"][0], "cam", tuple(round(c, 2) for c in P), "look", tuple(round(c, 2) for c in L), "fov", fov, "dist", round((P - L).length, 2))
        for n, a in sh["actors"].items():
            x, z = RT._path(a, t)[:2]
            print("   ", n, round(x, 2), round(z, 2), "d", round(math.hypot(P.x - x, P.z - z), 2))
