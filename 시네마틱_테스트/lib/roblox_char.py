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


def plastic(name, rgb, rough=0.38):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = pbr.flat_mat(name, pbr.srgb(*rgb), rough=rough, coat=0.15)
    return m


OUTFITS = {
    # 하루: 대머리·하얀 피부·파란 정장(72,126,200, 깃·주머니 46,90,158)·검정 넥타이·흰 반바지·노란 신발 (고정)
    "하루": dict(skin=(245, 245, 242), suit=(72, 126, 200), trim=(46, 90, 158), tie=(20, 20, 24), shirt=(250, 250, 250),
               shorts=(248, 248, 248), shoes=(250, 205, 40), style="하루", hair=None),
    # 불 마을 주민: 붉은 갈색 옷, 머리 위 불꽃
    "불주민A": dict(skin=(236, 214, 190), suit=(150, 52, 38), trim=(90, 30, 24), tie=None, shirt=(60, 40, 32),
                 shorts=(70, 48, 38), shoes=(40, 30, 26), style="불마을", hair="flame"),
    "불주민B": dict(skin=(226, 200, 175), suit=(120, 70, 40), trim=(80, 45, 28), tie=None, shirt=(200, 120, 60),
                 shorts=(60, 42, 34), shoes=(35, 28, 24), style="불마을", hair="flame"),
}


class Char:
    def __init__(self, name, outfit="하루", loc=(0, 0, 0), yaw=0.0, collection=None):
        self.name, self.o = name, OUTFITS[outfit]
        s = STUD
        col = collection or bpy.context.scene.collection
        self.col = col
        m = lambda k: plastic(f"{outfit}_{k}", self.o[k]) if self.o.get(k) else None
        self.root = bpy.data.objects.new(f"{name}_root", None)
        col.objects.link(self.root)
        self.root.location, self.root.rotation_euler = loc, (0, 0, yaw)
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
        mats = {k: m(k) for k in ("suit", "shirt", "tie", "trim") if m(k)}
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
            fl = fx.flame((0, 0, 0), 0.5, 0.18, f"{name}_flamehair", n=3, light=False)
            fl.parent = self.head
            fl.location = (0, 0, hs * 0.95)
        # 팔 (어깨 축에서 회전)
        self.arms = {}
        for side in (-1, 1):
            p = bpy.data.objects.new(f"{name}_sh{side}", None)
            col.objects.link(p)
            p.parent = self.hip
            p.location = (side * 1.5 * s, 0, 1.75 * s)
            mb = MS.MB()
            mb.box("suit", (0, 0, -0.95 * s), (1 * s, 1 * s, 1.5 * s))
            mb.box("skin", (0, 0, -1.875 * s), (0.98 * s, 0.98 * s, 0.35 * s))                 # 손
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
