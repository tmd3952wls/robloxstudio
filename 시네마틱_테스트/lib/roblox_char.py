"""로블록스 R6 캐릭터 (블록형 몸·둥근 사각 머리 유지) + 표정 얼굴 + 자세 적용.

비율은 R6 그대로 (스터드): 머리 1.2, 몸통 2x2x1, 팔·다리 1x2x1. 1 스터드 = STUD m (실사 배경에서 키 약 1.7m).
관절: 목, 어깨 2, 엉덩이 2 (로블록스처럼 팔꿈치·무릎 없음).
OUTFITS 에 캐릭터 의상 정의 (하루 고정 디자인 포함). 새 캐릭터는 OUTFITS 에 추가.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(D, "..", "emotion"))
import face as FACE  # noqa: E402
import mesh as MS  # noqa: E402
import pbr  # noqa: E402

STUD = 0.33
SHOULDER_Z = 1.75      # 어깨 회전축 (몸통 바닥에서, 스터드) — 로블록스 R6 와 같음
ARM_TOP = 2.0 - SHOULDER_Z   # 팔 윗면을 몸통 윗면(어깨선)과 같은 높이로: 축 위 +0.25 스터드 (고정 규칙)


def plastic(name, rgb, rough=0.38, glass=False):
    m = bpy.data.materials.get(name)
    if m:
        return m
    if glass:                                 # 물 사람: 반투명 하늘색 유리 (Cycles 굴절, EEVEE 는 레이트레이싱 굴절)
        m = pbr.flat_mat(name, pbr.srgb(*rgb), rough=0.04, emit=pbr.srgb(*rgb), emit_str=0.25)
        bs = m.node_tree.nodes["Principled BSDF"]
        bs.inputs["Transmission Weight"].default_value = 0.92
        bs.inputs["IOR"].default_value = 1.33
        try:
            m.surface_render_method = "DITHERED"
            m.use_raytrace_refraction = True
        except Exception:
            pass
        return m
    m = pbr.flat_mat(name, pbr.srgb(*rgb), rough=rough, coat=0.15)
    return m


def set_glow(outfit, color=(1.0, 0.45, 0.12), strength=0.0, keys=("suit", "trim", "shirt", "shorts", "skin")):
    """불 사람 몸빛 (밤 장면): 해당 의상 재질에 발광"""
    for k in keys:
        m = bpy.data.materials.get(f"{outfit}_{k}")
        if m:
            bs = m.node_tree.nodes["Principled BSDF"]
            bs.inputs["Emission Color"].default_value = tuple(color) + (1,)
            bs.inputs["Emission Strength"].default_value = strength


OUTFITS = {
    # 하루: 대머리·하얀 피부·파란 정장(72,126,200, 깃·주머니 46,90,158)·검정 넥타이·흰 반바지·노란 신발 (고정)
    "하루": dict(skin=(245, 245, 242), suit=(72, 126, 200), trim=(46, 90, 158), tie=(20, 20, 24), shirt=(250, 250, 250),
               shorts=(248, 248, 248), shoes=(250, 205, 40), style="하루", hair=None),
    # 불 마을 주민: 진한 불빨강 옷, 머리 위 빨간 불꽃 (몸 발광 X — 2026-11-25 "타는 듯해서 빨간 불색만 강조")
    "불주민A": dict(skin=(236, 214, 190), suit=(178, 28, 20), trim=(105, 14, 10), tie=None, shirt=(60, 22, 18),
                 shorts=(72, 26, 20), shoes=(36, 22, 20), style="불마을", hair="flame"),
    # 물 마을 주민: 몸 전체가 반투명 하늘색 유리, 머리 위 물방울
    "물주민A": dict(skin=(170, 220, 250), suit=(120, 190, 240), trim=(90, 160, 220), tie=None, shirt=(190, 230, 255),
                 shorts=(110, 175, 230), shoes=(80, 140, 200), style="물마을", hair="drop", glass=True),
    "물주민B": dict(skin=(180, 228, 252), suit=(140, 205, 245), trim=(100, 170, 225), tie=None, shirt=(200, 235, 255),
                 shorts=(120, 185, 235), shoes=(90, 150, 210), style="물마을", hair="drop", glass=True),
    "불주민B": dict(skin=(226, 200, 175), suit=(138, 18, 14), trim=(80, 10, 8), tie=None, shirt=(205, 64, 24),
                 shorts=(58, 22, 18), shoes=(32, 20, 18), style="불마을", hair="flame"),
    # 조연 (2026-11-25 본편): 아이는 scale 0.72 로 만듦
    "불아이": dict(skin=(238, 216, 192), suit=(196, 40, 24), trim=(120, 20, 12), tie=None, shirt=(235, 120, 40),
                shorts=(80, 28, 20), shoes=(40, 24, 20), style="불마을", hair="flame"),
    "물아이": dict(skin=(176, 224, 252), suit=(130, 198, 244), trim=(96, 166, 224), tie=None, shirt=(200, 236, 255),
                shorts=(112, 180, 232), shoes=(84, 146, 206), style="물마을", hair="drop", glass=True),
    "대장장이": dict(skin=(214, 180, 150), suit=(92, 26, 18), trim=(40, 22, 18), tie=None, shirt=(150, 30, 20),
                 shorts=(46, 30, 24), shoes=(30, 22, 20), style="불마을", hair="flame", apron=(58, 40, 30)),
    "뱃사공": dict(skin=(190, 214, 230), suit=(118, 160, 196), trim=(84, 124, 164), tie=None, shirt=(196, 220, 236),
                shorts=(96, 136, 176), shoes=(70, 100, 140), style="물마을", hair="drop", glass=True, hat=(200, 170, 110)),
    "엄마": dict(skin=(184, 226, 250), suit=(150, 204, 240), trim=(110, 176, 228), tie=None, shirt=(214, 238, 255),
               shorts=(130, 190, 236), shoes=(96, 156, 214), style="물마을", hair="drop", glass=True),
    "아빠": dict(skin=(232, 206, 180), suit=(170, 32, 22), trim=(96, 16, 12), tie=None, shirt=(70, 24, 20),
               shorts=(68, 26, 20), shoes=(34, 22, 20), style="불마을", hair="flame"),
}


class Char:
    def __init__(self, name, outfit="하루", loc=(0, 0, 0), yaw=0.0, collection=None, scale=1.0):
        self.name, self.o = name, OUTFITS[outfit]
        s = STUD
        col = collection or bpy.context.scene.collection
        self.col = col
        gl = self.o.get("glass", False)
        m = lambda k: plastic(f"{outfit}_{k}", self.o[k], glass=gl and k not in ("tie",)) if self.o.get(k) else None
        self.root = bpy.data.objects.new(f"{name}_root", None)
        col.objects.link(self.root)
        self.root.location, self.root.rotation_euler = loc, (0, 0, yaw)
        self.root.scale = (scale, scale, scale)
        self.scale = scale
        # 엉덩이 높이 = 다리 길이 2 스터드
        self.hip = bpy.data.objects.new(f"{name}_hip", None)
        col.objects.link(self.hip)
        self.hip.parent = self.root
        self.hip.location = (0, 0, 2 * s)
        # 몸통
        mb = MS.MB()
        mb.box("suit", (0, 0, s), (2 * s, 1 * s, 2 * s))
        mb.box("shirt", (0, -0.5 * s - 0.004, 1.55 * s), (0.62 * s, 0.01, 0.9 * s))              # 셔츠 V
        if self.o.get("tie"):
            mb.box("tie", (0, -0.5 * s - 0.012, 1.45 * s), (0.2 * s, 0.012, 1.0 * s))
            mb.box("tie", (0, -0.5 * s - 0.014, 1.93 * s), (0.28 * s, 0.014, 0.14 * s))
        for sx in (-1, 1):
            mb.box("trim", (sx * 0.42 * s, -0.5 * s - 0.006, 1.6 * s), (0.22 * s, 0.012, 0.8 * s), MS.roty(sx * 0.35))   # 옷깃
            mb.box("trim", (sx * 0.62 * s, -0.5 * s - 0.005, 0.55 * s), (0.42 * s, 0.01, 0.18 * s))                   # 주머니
        if self.o.get("apron"):                                   # 대장장이 앞치마
            mb.box("apron", (0, -0.5 * s - 0.02, 0.85 * s), (1.6 * s, 0.03, 1.5 * s))
        mats = {k: m(k) for k in ("suit", "shirt", "tie", "trim", "apron") if m(k)}
        mb.parts = {k: v for k, v in mb.parts.items() if k in mats}
        self.torso = mb.build(f"{name}_torso", mats, col, bevel=0.012)
        self.torso.parent = self.hip
        # 목 -> 머리
        self.neck = bpy.data.objects.new(f"{name}_neck", None)
        col.objects.link(self.neck)
        self.neck.parent = self.hip
        self.neck.location = (0, 0, 2 * s)
        hs = 1.2 * s
        mb = MS.MB()
        mb.box("skin", (0, 0, hs / 2), (hs * 1.0, hs * 0.98, hs))
        self.head = mb.build(f"{name}_head", {"skin": m("skin")}, col)
        bv = self.head.modifiers.new("Round", "BEVEL")
        bv.width, bv.segments, bv.limit_method = hs * 0.24, 6, "NONE"
        self.head.modifiers.new("Smooth", "WEIGHTED_NORMAL")
        self.head.parent = self.neck
        self.head.data.polygons.foreach_set("use_smooth", [True] * len(self.head.data.polygons))
        self.face = FACE.FaceRig(self.head, hs, hs * 0.49, hs * 0.24, z_center=hs / 2, prefix="Face_" + outfit)
        if self.o.get("hair") == "flame":
            import fx
            fl = fx.flame((0, 0, 0), 0.5, 0.18, f"{name}_flamehair", n=3, light=False, mat=fx.flame_hair_mat())
            fl.parent = self.head
            fl.location = (0, 0, hs * 0.95)
        if self.o.get("hat"):                                    # 뱃사공 삿갓
            hm = MS.MB()
            hm.cyl("hat", (0, 0, hs * 1.08), hs * 0.95, hs * 0.32, 24, r2=hs * 0.08)
            ho = hm.build(f"{name}_hat", {"hat": plastic(f"{outfit}_hat", self.o["hat"], rough=0.8)}, col)
            ho.parent = self.head
        if self.o.get("hair") == "drop" and not self.o.get("hat"):   # 머리 위 물방울
            import bmesh
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=hs * 0.22)
            for v in bm.verts:
                if v.co.z > 0:
                    v.co.z *= 1.0 + 1.6 * (v.co.z / (hs * 0.22))
                    v.co.x *= 1 - 0.75 * (v.co.z / (hs * 0.6))
                    v.co.y *= 1 - 0.75 * (v.co.z / (hs * 0.6))
            me = bpy.data.meshes.new(f"{name}_drop")
            bm.to_mesh(me); bm.free()
            me.materials.append(plastic(f"{outfit}_suit", self.o["suit"], glass=True))
            dr = bpy.data.objects.new(f"{name}_drop", me)
            col.objects.link(dr)
            dr.parent = self.head
            dr.location = (0, 0, hs * 1.12)
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        # 팔 (어깨 축에서 회전)
        self.arms = {}
        for side in (-1, 1):
            p = bpy.data.objects.new(f"{name}_sh{side}", None)
            col.objects.link(p)
            p.parent = self.hip
            p.location = (side * 1.5 * s, 0, SHOULDER_Z * s)
            mb = MS.MB()
            # 팔 윗면 = 몸통 윗면(어깨선) 높이에 고정: 어깨 축(1.75) 기준 +0.25 ~ -1.75 (길이 2 스터드, 끝 = 엉덩이선)
            mb.box("suit", (0, 0, (ARM_TOP - 0.825) * s), (1 * s, 1 * s, 1.65 * s))       # 소매: 윗면 ARM_TOP ~ 손목
            mb.box("skin", (0, 0, (ARM_TOP - 2.0 + 0.175) * s), (0.98 * s, 0.98 * s, 0.35 * s))   # 손
            a = mb.build(f"{name}_arm{side}", {"suit": m("suit"), "skin": m("skin")}, col, bevel=0.012)
            a.parent = p
            self.arms[side] = p
        # 다리
        self.legs = {}
        for side in (-1, 1):
            p = bpy.data.objects.new(f"{name}_hp{side}", None)
            col.objects.link(p)
            p.parent = self.hip
            p.location = (side * 0.5 * s, 0, 0)
            mb = MS.MB()
            mb.box("shorts", (0, 0, -0.55 * s), (1 * s, 1 * s, 1.1 * s))
            mb.box("skin", (0, 0, -1.32 * s), (0.97 * s, 0.97 * s, 0.45 * s))
            mb.box("shoes", (0, -0.03 * s, -1.78 * s), (1.02 * s, 1.08 * s, 0.44 * s))
            l = mb.build(f"{name}_leg{side}", {"shorts": m("shorts"), "skin": m("skin"), "shoes": m("shoes")}, col, bevel=0.012)
            l.parent = p
            self.legs[side] = p
        self.base_loc = Vector(loc)
        self.yaw = yaw
        self.walk = None             # (속도 m/s, 시작 t)

    def pose(self, b, t=0.0):
        """몸 매개변수 적용 (각도는 도)"""
        r = math.radians
        s = STUD
        breath = b.get("breath", 0.0)
        crouch = b.get("crouch", 0.0)
        self.hip.location = (0, 0, 2 * s - crouch * s * 1.2 + breath * 0.004)
        self.hip.rotation_euler = (r(b["lean"]), 0, 0)                       # + 앞으로 숙임
        self.neck.rotation_euler = (r(b["head_pitch"]), r(b["head_roll"]), r(b["head_yaw"]))   # + 고개 숙임
        # 팔: x(-) = 앞으로 들기, z = 옆으로 벌리기
        for side, k in ((-1, "L"), (1, "R")):
            ax, az = b[f"arm{k}_x"], b[f"arm{k}_z"]
            self.arms[side].rotation_euler = (r(ax), -side * r(az), 0)
        spread = b.get("legspread", 0.0)
        for side in (-1, 1):
            self.legs[side].rotation_euler = (0, side * r(spread), 0)
        # 뒤로 물러남 (캐릭터 앞 = -Y 로컬)
        back = b.get("back", 0.0)
        off = Matrix.Rotation(self.yaw, 3, "Z") @ Vector((0, back, 0))
        self.root.location = self.base_loc + off
        if self.walk:
            self._walk(t)

    def _walk(self, t):
        v, t0, phase = self.walk
        tt = max(0.0, t - t0)
        fwd = Matrix.Rotation(self.yaw, 3, "Z") @ Vector((0, -1, 0))
        self.root.location = self.base_loc + fwd * v * tt
        w = 2 * math.pi * v / 1.25 * tt + phase
        a = math.radians(32) * math.sin(w)
        for side in (-1, 1):
            self.legs[side].rotation_euler = (side * a, 0, 0)
            self.arms[side].rotation_euler = (-side * a * 0.9, 0, 0)
        self.hip.location.z += abs(math.sin(w)) * 0.025

    def set_face(self, f, t=0.0):
        if self.o.get("style") == "하루":
            f = dict(f)
            f["blush"] = 0.0          # 하루는 볼터치 없음 (고정 디자인)
        self.face.update(f, t)
