"""장면 A: 마을 전체 전경 (기존 미리보기 첫 컷 '구름 위에서 두 마을로' 와 같은 방향의 높은 항공 구도)
사용: blender -b --python tests/scene_a.py -- [EEVEE|CYCLES] [samples] [pct] [tag]
"""
import os, sys, time, json
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(D, "..", "lib"))
import bpy
import look, world_valley, perf

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
eng = argv[0] if argv else "EEVEE"
spp = int(argv[1]) if len(argv) > 1 else 64
pct = int(argv[2]) if len(argv) > 2 else 100
tag = argv[3] if len(argv) > 3 else ""
look.clear_scene()
mon = perf.Monitor()
info = world_valley.build("full")
V = info["V"]
look.world("kloofendal_48d_partly_cloudy_puresky", 1.0, rot_deg=40)
look.sun(32, 205, 4.5)
look.fog((V.x0, V.y0, -20), (V.x1, V.y1, 900), density=0.00009, color=(0.78, 0.84, 0.95))
yb = info["bridge_y"]
xr = float(V.river_x(-420))
cam = look.camera((xr + 60, -430, 150), (-260, 700, 120), lens=22)
look.preset(eng, "final", samples=spp, pct=pct)
bpy.context.scene.frame_set(1)
out = os.path.join(D, "..", "out", f"A_{eng.lower()}{tag}.png")
bpy.context.scene.render.filepath = out
t = time.time()
bpy.ops.render.render(write_still=True)
rt = time.time() - t
stats = mon.stop()
stats.update(scene="A", engine=eng, samples=spp, pct=pct, render_s=round(rt, 1), build_s=round(info["t_build"], 1))
print("STATS", json.dumps(stats))
perf.log(stats)
