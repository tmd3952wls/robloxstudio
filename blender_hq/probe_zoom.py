"""확대 전환 구간 중 길이 막혀 컷으로 바뀌는 프레임 찾기"""
import os, sys
import bpy
D = os.path.dirname(bpy.data.filepath); sys.path.insert(0, D)
import runtime as RT  # noqa
import hq_upgrade as HQ  # noqa
sc = bpy.context.scene
HQ.apply()
for sh in RT._S["shots"]:
    for z in sh.get("zoom") or []:
        for t0 in (z[1], z[2] - 0.45):
            if t0 <= 0 or t0 >= sh["dur"] - 1e-3:
                continue
            for k in range(0, 15):
                T = sh["start"] + t0 + k / 30
                f = int(round(T * 30)) + 1
                HQ.HQ["zblock"] = 0
                sc.frame_set(f)
                if HQ.HQ["zblock"]:
                    print("ZB", sh["lines"][0], z[0], f, round(T, 2), flush=True)
