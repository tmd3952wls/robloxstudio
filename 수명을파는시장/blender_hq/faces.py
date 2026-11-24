"""하루 표정 (HaruFaces 모듈을 블렌더로 옮김, 지난 영상 runtime 에서 그대로 가져옴)"""
import math

import bpy
from mathutils import Matrix, Vector


def _mat(name):
    return bpy.data.materials.get(name) or bpy.data.materials.get("R_SmoothPlastic_C")


def _lin(r, g, b):
    return tuple(((c / 255 + 0.055) / 1.055) ** 2.4 if c / 255 > 0.04045 else c / 255 / 12.92 for c in (r, g, b))


DARK, WHITE, BLUE, RED = _lin(40, 30, 26), _lin(255, 255, 255), _lin(90, 170, 255), _lin(230, 50, 70)
PINK, GOLD, NAVY = _lin(255, 120, 140), _lin(255, 205, 60), _lin(60, 80, 140)
FACES = {
    "기본 미소": ("open", (.27, -9), "smile", ()), "활짝 웃음": ("happy", (.3, -6), "grin", ()),
    "폭소": ("squint", (.3, -10), "laugh", ("joytears",)), "윙크": (("open", "happy"), (.27, -6), "smirk", ()),
    "메롱": (("happy", "open"), (.28, -6), "tongue", ()), "뿌듯": ("happy", (.31, 8), "smirk", ()),
    "감동": ("star", (.31, -12), "opensmile", ("sparkle",)), "사랑": ("heart", (.31, -10), "grin", ()),
    "신남": ("wide", (.33, -8), "laugh", ("sparkle",)), "놀람": ("wide", (.34, -4), "o", ()),
    "충격": ("dot", (.3, -14), "bigo", ("gloom",)), "비명": ("wide", (.33, -18), "bigo", ("sweat",)),
    "겁먹음": ("dot", (.24, -20), "wavy", ("gloom", "sweat")), "슬픔": ("open", (.27, -20), "frown", ()),
    "울먹": ("teary", (.27, -22), "wavy", ()), "엉엉": ("cry", (.24, -22), "bigo", ()),
    "실망": ("half", (.24, -14), "frown", ()), "절망": ("closed", (.2, -20), "bigfrown", ("gloom",)),
    "짜증": ("half", (.2, 14), "flat", ()), "화남": ("open", (.2, 22), "frown", ()),
    "분노": ("open", (.19, 28), "teeth", ("vein",)), "삐짐": ("closed", (.22, 16), "pout", ()),
    "의심": ("half", ((.2, 6), (.31, -4)), "smallflat", (), .05), "장난기": ("half", (.2, 16), "grin", ()),
    "당황": ("wide", (.33, -14), "wavy", ("sweat",)), "민망": ("open", (.27, -14), "smallflat", ("sweat",), -.06),
    "무표정": ("open", (.26, 0), "flat", ()), "졸림": ("half", (.26, -8), "o", ()),
    "잠": ("closed", (.24, -4), "o", ("zzz",)), "생각 중": ("open", ((.27, 0), (.33, -6)), "smallflat", (), .05, .04),
    "깨달음": ("wide", (.35, -4), "opensmile", ("sparkle",)), "결심": ("open", (.2, 18), "smile", ()),
    "어지러움": ("x", (.27, -12), "wavy", ()), "기절": ("x", (.27, 0), "tongue", ()),
    "메스꺼움": ("half", (.24, -16), "wavy", ("sweat",)), "딴청": ("open", (.3, -4), "o", (), -.06, .03),
}
BLINKABLE = {"open", "wide", "dot", "teary", "half", "heart", "star"}


def _face_parts(name, blink):
    """표정 -> [(종류 B/C, vx, vy, w, h, 각도, 색, 겹, 네온)] (머리 크기 비율 좌표)"""
    closed = False
    gx = gy = 0.0
    if "|" in name:
        name, *mods = name.split("|")
        for mod in mods:
            if mod == "closed":
                closed = True
            elif mod.startswith("g:"):            # 시선: 눈을 (+왼쪽, +위) 로 옮김
                gx, gy = (float(v) for v in mod[2:].split(","))
    spec = FACES.get(name, FACES["기본 미소"])
    e, b, m, x = spec[0], spec[1], spec[2], spec[3]
    ex = (spec[4] if len(spec) > 4 else 0) + gx
    ey = (spec[5] if len(spec) > 5 else 0) + gy
    out = []

    def bar(vx, vy, w, h, ang=0, color=DARK, layer=0, neon=False):
        out.append(("B", vx, vy, w, h, ang, color, layer, neon))

    def dot(vx, vy, d, color=DARK, layer=0):
        out.append(("C", vx, vy, d, d, 0, color, layer, False))

    def eye(s, kind):
        if (blink or closed) and kind in BLINKABLE:
            kind = "closed"
        X, Y = s * 0.2 + ex, 0.03 + ey
        if kind == "open": dot(X, Y, .27); dot(X + .04, Y + .055, .08, WHITE, 1)
        elif kind == "wide": dot(X, Y, .34); dot(X + .05, Y + .07, .095, WHITE, 1)
        elif kind == "dot": dot(X, Y, .08)
        elif kind == "happy": bar(X - .045, Y + .02, .13, .042, 35); bar(X + .045, Y + .02, .13, .042, -35)
        elif kind == "sadclosed": bar(X - .045, Y - .02, .13, .042, -35); bar(X + .045, Y - .02, .13, .042, 35)
        elif kind == "closed": bar(X, Y - .02, .19, .042)
        elif kind == "half": dot(X, Y - .045, .21); dot(X + .035, Y - .06, .06, WHITE, 1); bar(X, Y + .035, .28, .06, 0, DARK, 2)
        elif kind == "x": bar(X, Y, .21, .045, 45); bar(X, Y, .21, .045, -45)
        elif kind == "squint": bar(X, Y + .04, .15, .042, s * 28); bar(X, Y - .04, .15, .042, -s * 28)
        elif kind == "heart": bar(X, Y - .02, .15, .15, 45, RED); dot(X - .055, Y + .045, .125, RED); dot(X + .055, Y + .045, .125, RED)
        elif kind == "star": bar(X, Y, .17, .17, 0, GOLD, 0, True); bar(X, Y, .17, .17, 45, GOLD, 0, True); bar(X + .02, Y + .02, .05, .05, 0, WHITE, 1, True)
        elif kind == "teary": dot(X, Y, .28); dot(X + .04, Y + .06, .09, WHITE, 1); dot(X - .045, Y - .04, .055, WHITE, 1); bar(X, Y - .15, .26, .06, 0, BLUE, 2)
        elif kind == "cry": bar(X - .045, Y - .02, .13, .042, -35); bar(X + .045, Y - .02, .13, .042, 35); bar(X, Y - .25, .1, .4, 0, BLUE, 0)

    eL, eR = (e if isinstance(e, tuple) else (e, e))
    eye(-1, eL)
    eye(1, eR)
    bL, bR = (b if isinstance(b[0], tuple) else (b, b))
    bar(-.2, bL[0], .19, .042, -bL[1])
    bar(.2, bR[0], .19, .042, bR[1])
    y = -0.24
    if m in ("smile", "tongue"):
        bar(0, y, .13, .035); bar(.085, y + .018, .065, .035, 32); bar(-.085, y + .018, .065, .035, -32)
        if m == "tongue": bar(.02, y - .055, .09, .085, 0, PINK, 1)
    elif m == "frown": bar(0, y, .13, .035); bar(.085, y - .018, .065, .035, -32); bar(-.085, y - .018, .065, .035, 32)
    elif m == "bigfrown": bar(0, y, .2, .04); bar(.13, y - .03, .09, .04, -40); bar(-.13, y - .03, .09, .04, 40)
    elif m == "flat": bar(0, y, .2, .035)
    elif m == "smallflat": bar(0, y, .09, .035)
    elif m == "pout": bar(0, y, .08, .035); bar(.05, y - .015, .045, .035, -35); bar(-.05, y - .015, .045, .035, 35)
    elif m == "grin": bar(0, y - .01, .3, .13); bar(0, y + .03, .26, .04, 0, WHITE, 1); bar(0, y - .045, .15, .05, 0, PINK, 1)
    elif m == "laugh": bar(0, y - .03, .32, .19); bar(0, y + .04, .28, .045, 0, WHITE, 1); bar(0, y - .085, .18, .07, 0, PINK, 1)
    elif m == "opensmile": bar(0, y - .01, .2, .1); bar(0, y - .035, .11, .045, 0, PINK, 1)
    elif m == "o": dot(0, y - .01, .11)
    elif m == "bigo": bar(0, y - .04, .19, .23); bar(0, y - .115, .12, .06, 0, PINK, 1)
    elif m == "wavy":
        for i, xx in enumerate((-.105, -.035, .035, .105)):
            bar(xx, y, .085, .035, 28 if i % 2 == 0 else -28)
    elif m == "teeth":
        bar(0, y, .31, .13); bar(0, y, .27, .09, 0, WHITE, 1)
        for xx in (-.07, 0, .07):
            bar(xx, y, .014, .09, 0, DARK, 2)
        bar(0, y, .27, .014, 0, DARK, 2)
    elif m == "smirk": bar(-.01, y, .16, .035, 6); bar(.1, y + .035, .07, .035, 40)
    for k in x:
        if k == "sweat": bar(.4, .2, .07, .11, 0, BLUE); bar(.4, .255, .05, .05, 45, BLUE)
        elif k == "vein":
            bar(.3, .39, .07, .028, 45, RED); bar(.37, .39, .07, .028, -45, RED)
            bar(.3, .32, .07, .028, -45, RED); bar(.37, .32, .07, .028, 45, RED)
        elif k == "gloom":
            for i, xx in enumerate((.1, .18, .26, .34)):
                bar(xx, .4 - (.03 if i % 2 == 1 else 0), .022, .16 if i % 2 == 1 else .1, 0, NAVY)
        elif k == "zzz":
            for X, Y, sz in ((.58, .3, .1), (.72, .46, .14)):
                bar(X, Y + sz / 2, sz, .03, 0, BLUE); bar(X, Y - sz / 2, sz, .03, 0, BLUE); bar(X, Y, sz * 1.25, .03, 45, BLUE)
        elif k == "joytears": bar(-.33, -.02, .05, .07, 0, BLUE); bar(.33, -.02, .05, .07, 0, BLUE)
        elif k == "sparkle":
            bar(.4, .33, .1, .03, 0, GOLD, 0, True); bar(.4, .33, .03, .1, 0, GOLD, 0, True)
            bar(-.42, .26, .07, .022, 0, GOLD, 0, True); bar(-.42, .26, .022, .07, 0, GOLD, 0, True)
    return out


ROT_DOT = (C3 := Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))) @ Matrix.Rotation(math.radians(90), 3, "Y") @ C3.transposed()


def _draw_face(info, head_M, head_size, name, blink):
    """머리의 최종 위치(head_M, 크기 없는 4x4)에 표정 조각들을 붙인다"""
    O = bpy.data.objects
    hw, hz, hh = head_size        # 블렌더 크기 (x=sx, y=sz, z=sy)
    fz = -hz / 2 - 0.02
    R = head_M.to_3x3()
    used = {}
    for kind, vx, vy, w, h, ang, col, layer, neon in _face_parts(name, blink):
        lst = info["pool"].get(kind, [])
        j = used.get(kind, 0)
        used[kind] = j + 1
        if j >= len(lst):
            continue
        ob = O[lst[j]]
        rx, ry, rz = -vx * hw, vy * hh, fz - layer * 0.012          # 로블록스 머리 기준 좌표
        loc = head_M.translation + R @ Vector((rx, -rz, ry))
        if kind == "B":
            rot = R @ (C3 @ Matrix.Rotation(math.radians(-ang), 3, "Z") @ C3.transposed())
            scale = (w * hw, 0.04, h * hh)
        else:
            rot = R @ ROT_DOT
            scale = (0.04, w * hw, w * hw)
        ob.matrix_world = Matrix.Translation(loc) @ rot.to_4x4() @ Matrix.Diagonal((*scale, 1))
        ob.color = (col[0], col[1], col[2], 1.0)
        ob["emit"] = 0.6 if neon else 0.0
        ob.material_slots[0].material = _mat("R_Neon_C" if neon else "R_SmoothPlastic_C")
        ob.hide_render = False
        ob.update_tag()
    for kind, lst in info["pool"].items():
        for j in range(used.get(kind, 0), len(lst)):
            O[lst[j]].hide_render = True

