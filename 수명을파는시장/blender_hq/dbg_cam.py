import os, sys, bpy
D = os.path.dirname(bpy.data.filepath); sys.path.insert(0, D)
import runtime as RT, hq_upgrade as HQ
HQ.apply()
for sh in RT._S["shots"]:
    if sh["lines"][0] in (23, 55):
        print("L", sh["lines"], "start", sh["start"], "dur", sh["dur"])
        print("  cam0", sh.get("cam0", [])[:1], sh.get("cam0", [])[-1:])
        print("  new0", sh["cam"][0], "newEnd", sh["cam"][-1])
