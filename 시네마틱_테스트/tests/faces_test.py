"""표정 테스트: 하루 클로즈업 감정별 스틸 + (옵션) 전환 애니메이션 프레임.
blender -b --python tests/faces_test.py -- stills [EEVEE] [samples]
blender -b --python tests/faces_test.py -- anim  [EEVEE] [samples] [start] [end]
배경: 실사형 골목 벽 (건물 생성기) + 노을빛 조명 -> 배경과 캐릭터 조명 통합 확인.
"""
import os, sys, time, json, math
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(D, "..", "lib"))
sys.path.insert(0, os.path.join(D, "..", "emotion"))
import bpy
from mathutils import Vector
import look, buildings, pbr, mesh as MS, perf
import roblox_char as RC
import library as LB, anim as AN

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
mode = a[0] if a else "stills"
eng = a[1] if len(a) > 1 else "EEVEE"
spp = int(a[2]) if len(a) > 2 else 64
OUT = os.path.join(D, "..", "out", "faces")
os.makedirs(OUT, exist_ok=True)

look.clear_scene()
mon = perf.Monitor()
look.world("belfast_sunset_puresky", 0.8, rot_deg=120)
look.sun(14, 250, 3.5, (1.0, 0.8, 0.6))
# 배경: 골목 (집 두 채 + 자갈길)
g = pbr.tex_mat("ground", "cobblestone_floor_04", 2.0, var=0.2, bump=0.8, detile=True, tint=pbr.srgb(170, 160, 150))
mb = MS.MB(); mb.box("g", (0, 0, -0.05), (40, 40, 0.1)); mb.build("ground", {"g": g})
for i, (x, y, yaw) in enumerate(((-4.5, 7, 0.15), (4.0, 9, -0.1), (0, 15, 0))):
    ob, info = buildings.house(50 + i * 3, "fire", floors=2, gable_front=i != 1, lit_p=0.6)
    ob.location, ob.rotation_euler = (x, y, 0), (0, 0, yaw)
haru = RC.Char("Haru", "하루", (0, 0, 0), 0.0)
look.area("Key", (-1.6, -2.4, 2.6), (0, 0, 1.6), 140, 1.5, (1.0, 0.9, 0.8))     # 부드러운 키라이트 (노을 방향과 같은 쪽)
look.area("Rim", (1.8, 2.0, 2.4), (0, 0, 1.7), 220, 1.0, (1.0, 0.7, 0.45))     # 노을 림
head_z = 2 * RC.STUD + 2 * RC.STUD + 0.6 * RC.STUD
cam = look.camera((0.0, -1.55, head_z + 0.02), (0, 0, head_z - 0.06), lens=55, dof=1.6, fstop=2.2)
look.preset(eng, "final", samples=spp)
sc = bpy.context.scene

if mode == "stills":
    names = sys.argv[sys.argv.index("--") + 3 + 1:] if False else ["평온", "기쁨", "놀람", "슬픔", "분노", "공포", "당황", "울음", "결심", "흥분", "의심", "안도"]
    times = {}
    for nm in names:
        f, b = LB.target(nm, 1.0, "하루")
        if nm in ("슬픔",):
            f["flow"] = 0.5
        b["breath"] = 0
        haru.pose(b)
        haru.set_face(f, 0.4)
        bpy.context.view_layer.update()
        hp = haru.head.matrix_world @ Vector((0, 0, 0.6 * RC.STUD))      # 머리 가운데 따라가기
        cam.location = hp + Vector((0, -1.75, 0.05))
        look.aim(cam, hp + Vector((0, 0, -0.08)))
        cam.data.dof.focus_distance = (cam.location - hp).length - 0.15
        sc.render.filepath = os.path.join(OUT, f"still_{nm}.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        times[nm] = round(time.time() - t, 1)
    st = mon.stop(); st.update(test="face_stills", engine=eng, samples=spp, per_frame=times)
    perf.log(st); print("STATS", json.dumps(st, ensure_ascii=False))
else:
    # 전환 애니메이션 9초: 평온 -> 기쁨 -> 놀람 -> 공포 -> 슬픔(울먹) -> 분노 -> 평온
    tl = AN.Timeline("하루")
    tl.key(0.0, "평온").key(0.9, "기쁨").key(2.3, "놀람").key(3.6, "공포").key(5.0, "슬픔").key(6.8, "분노").key(8.3, "평온", dur=0.7)
    tl.say(1.0, 2.0, "와 좋다").look(3.7, -0.6, 0.0).look(4.3, 0.6, 0.1)
    s0 = int(a[3]) if len(a) > 3 else 1
    s1 = int(a[4]) if len(a) > 4 else 270
    sc.frame_start, sc.frame_end = s0, s1

    def upd(scene, *_):
        t = (scene.frame_current - 1) / 30.0
        f, b = tl.eval(t)
        haru.pose(b, t)
        haru.set_face(f, t)
        # 카메라 천천히 밀기 + 살짝 흔들림 (핸드헬드 느낌)
        bpy.context.view_layer.update()
        hp = haru.head.matrix_world @ Vector((0, 0, 0.6 * RC.STUD))
        # 머리를 부드럽게 따라가며 천천히 밀기 + 핸드헬드 흔들림
        cam.location = Vector((0.05 * math.sin(t * 0.7), hp.y - 1.95 + 0.2 * min(t / 9, 1), hp.z * 0.5 + head_z * 0.5 - 0.12 + 0.008 * math.sin(t * 1.3)))
        look.aim(cam, Vector((0, hp.y, hp.z * 0.6 + head_z * 0.4 - 0.27)))
        cam.data.dof.focus_distance = (cam.location - hp).length - 0.15
    bpy.app.handlers.frame_change_pre.append(upd)
    sc.render.filepath = os.path.join(OUT, "anim", "f")
    os.makedirs(os.path.join(OUT, "anim"), exist_ok=True)
    t = time.time()
    for fr in range(s0, s1 + 1):
        p = os.path.join(OUT, "anim", f"f{fr:04d}.png")
        if os.path.exists(p):
            continue
        sc.frame_set(fr)
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
    st = mon.stop(); st.update(test="face_anim", engine=eng, samples=spp, frames=s1 - s0 + 1, total_s=round(time.time() - t, 1))
    perf.log(st); print("STATS", json.dumps(st, ensure_ascii=False))
