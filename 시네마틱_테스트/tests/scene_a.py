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
SEQ = int(os.environ.get("SEQ", "0"))
if SEQ:
    sc = bpy.context.scene
    if eng.upper() == "CYCLES":
        sc.render.use_persistent_data = True
    c0 = cam.location.copy()
    from mathutils import Vector
    def upd(scene, *_):
        t = (scene.frame_current - 1) / 30.0
        cam.location = c0 + Vector((0, 9.0, -2.0)) * t           # 드론 접근
    bpy.app.handlers.frame_change_pre.append(upd)
    odir = os.path.join(D, "..", "out", f"seq_A_{eng.lower()}_{spp}")
    os.makedirs(odir, exist_ok=True)
    times, t_all = [], time.time()
    for fr in range(1, SEQ + 1):
        sc.frame_set(fr)
        sc.render.filepath = os.path.join(odir, f"f{fr:04d}.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        times.append(round(time.time() - t, 2))
    st = mon.stop()
    st.update(scene="A", engine=eng, samples=spp, mode="sequence", frames=SEQ, first_s=times[0],
              avg_rest_s=round(sum(times[1:]) / max(len(times) - 1, 1), 2), total_s=round(time.time() - t_all, 1), per_frame=times)
    print("STATS", json.dumps(st))
    perf.log(st)
    sys.exit(0)
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
