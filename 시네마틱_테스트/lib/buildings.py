"""절차적 중세 건물 (돌 1층 + 반목조(half-timber) 위층 + 돌출층(jetty) + 박공지붕 + 굴뚝 + 창·문·덧문·창턱).

house(seed, style, ...) -> (오브젝트, info{lanterns, chimneys, doors, size})
스타일(STYLES)은 재질 이름 묶음: 새 마을 분위기가 필요하면 STYLES 에 추가.
치수는 미터. 집 로컬 좌표: 정면이 -Y, 바닥 가운데가 원점.
"""
import math
import random

import bpy
from mathutils import Matrix, Vector

import mesh as MS
import pbr

STYLES = {
    # 불 마을: 어두운 돌, 따뜻한 회벽, 진한 목재, 붉은 기와
    "fire": dict(stone=("castle_wall_varriation", 2.4, pbr.srgb(150, 128, 112)),
                 plaster=("clay_plaster", 2.0, [pbr.srgb(*c) for c in ((226, 196, 160), (214, 170, 130), (232, 214, 186), (205, 150, 118), (190, 120, 95))]),
                 wood=("medieval_wood", 1.6, pbr.srgb(92, 66, 50)),
                 roof=("clay_roof_tiles_02", 2.2, [pbr.srgb(*c) for c in ((200, 120, 100), (176, 92, 72), (215, 140, 110), (150, 78, 64))]),
                 plank=("brown_planks_05", 1.2, pbr.srgb(150, 105, 80))),
    # 물 마을: 밝은 회색 돌, 흰·하늘색 회벽, 중간 목재, 청회색 슬레이트
    "water": dict(stone=("rustic_stone_wall", 2.4, pbr.srgb(200, 205, 210)),
                  plaster=("damaged_plaster", 2.0, [pbr.srgb(*c) for c in ((236, 240, 244), (200, 222, 236), (176, 205, 226), (226, 232, 226), (210, 226, 230))]),
                  wood=("medieval_wood", 1.6, pbr.srgb(120, 96, 78)),
                  roof=("roof_slates_02", 2.0, [pbr.srgb(*c) for c in ((130, 160, 190), (110, 140, 170), (150, 175, 200), (95, 120, 150))]),
                  plank=("brown_planks_05", 1.2, pbr.srgb(120, 140, 160))),
}
_MATS = {}


def mats(style):
    """스타일별 재질 (색 변형마다 하나씩 캐시)"""
    if style in _MATS:
        return _MATS[style]
    S = STYLES[style]
    out = {}
    aid, tile, tint = S["stone"]
    out["stone"] = pbr.tex_mat(f"{style}_stone", aid, tile, tint=tint, var=0.12, bump=0.6, bump_dist=0.06, grime_z=0.0, grime_h=1.0)
    aid, tile, tints = S["plaster"]
    out["plaster"] = [pbr.tex_mat(f"{style}_plaster{i}", aid, tile, tint=t, var=0.1, bump=0.35, normal_str=0.8, sat=0.35, gain=1.55)
                      for i, t in enumerate(tints)]
    aid, tile, tint = S["wood"]
    out["wood"] = pbr.tex_mat(f"{style}_wood", aid, tile, tint=tint, var=0.12, bump=0.3, sat=0.8)
    aid, tile, tints = S["roof"]
    out["roof"] = [pbr.tex_mat(f"{style}_roof{i}", aid, tile, tint=t, var=0.2, bump=0.5, bump_dist=0.05, detile=True, sat=0.85)
                   for i, t in enumerate(tints)]
    aid, tile, tint = S["plank"]
    out["plank"] = pbr.tex_mat(f"{style}_plank", aid, tile, tint=tint, var=0.1, bump=0.3)
    out["glass"] = pbr.flat_mat(f"{style}_glass", (0.02, 0.025, 0.03), rough=0.05, coat=0.0)
    out["glass_lit"] = pbr.flat_mat(f"{style}_glass_lit", (0.05, 0.03, 0.02), rough=0.08, emit=(1.0, 0.55, 0.22), emit_str=4.0)
    out["iron"] = pbr.flat_mat(f"{style}_iron", (0.03, 0.03, 0.03), rough=0.45, metal=1.0)
    _MATS[style] = out
    return out


# ------------------------------------------------------------------ 정면(facade) 좌표계
FRAMES = {
    # 이름: (u 방향, 바깥 법선)
    "front": (Vector((1, 0, 0)), Vector((0, -1, 0))),
    "back": (Vector((-1, 0, 0)), Vector((0, 1, 0))),
    "right": (Vector((0, 1, 0)), Vector((1, 0, 0))),
    "left": (Vector((0, -1, 0)), Vector((-1, 0, 0))),
}


class Facade:
    def __init__(self, mb, side, plane):
        self.mb = mb
        self.u, self.n = FRAMES[side]
        self.plane = plane          # 바깥면까지 거리 (원점에서 법선 방향)
        self.B = Matrix((self.u, self.n, Vector((0, 0, 1)))).transposed()

    def P(self, u, n, z):
        """u: 가로, n: 바깥면 기준 +바깥/-안쪽, z: 높이"""
        return self.u * u + self.n * (self.plane + n) + Vector((0, 0, z))

    def box(self, mat, u, n, z, su, sn, sz, ang=0.0, uvoff=(0, 0)):
        M = self.B @ MS.roty(ang)
        self.mb.box(mat, self.P(u, n, z), (su, sn, sz), M, uvoff)


def wall(fc, mat, u0, u1, z0, z1, t, openings, uvoff):
    """구멍(openings: [(ua,ub,za,zb)]) 뚫린 벽: 조각 상자들로 조립 (불리언 없이)"""
    ops = sorted(openings)
    cur = u0
    for ua, ub, za, zb in ops:
        if ua > cur + 1e-4:
            fc.box(mat, (cur + ua) / 2, -t / 2, (z0 + z1) / 2, ua - cur, t, z1 - z0, uvoff=uvoff)
        if za > z0 + 1e-4:
            fc.box(mat, (ua + ub) / 2, -t / 2, (z0 + za) / 2, ub - ua, t, za - z0, uvoff=uvoff)
        if zb < z1 - 1e-4:
            fc.box(mat, (ua + ub) / 2, -t / 2, (zb + z1) / 2, ub - ua, t, z1 - zb, uvoff=uvoff)
        cur = ub
    if u1 > cur + 1e-4:
        fc.box(mat, (cur + u1) / 2, -t / 2, (z0 + z1) / 2, u1 - cur, t, z1 - z0, uvoff=uvoff)


def window(fc, M, ua, ub, za, zb, t, rnd, lit, shutters=True, stone_frame=False):
    w, h = ub - ua, zb - za
    uc = (ua + ub) / 2
    glass = M["glass_lit"] if lit else M["glass"]
    fc.box(glass, uc, -t * 0.55, (za + zb) / 2, w, 0.03, h)                     # 유리 (안쪽으로 들어감)
    fr = M["stone"] if stone_frame else M["wood"]
    k = 0.09
    for (u, z, su, sz) in ((uc, zb + k / 2, w + 2 * k, k), (ua - k / 2, (za + zb) / 2, k, h), (ub + k / 2, (za + zb) / 2, k, h)):
        fc.box(fr, u, 0.025, z, su, 0.12, sz)                                   # 바깥 틀 (벽보다 살짝 튀어나옴)
    fc.box(M["wood"], uc, -t * 0.5, (za + zb) / 2, 0.05, 0.06, h)               # 세로 창살
    fc.box(M["wood"], uc, -t * 0.5, za + h * 0.55, w, 0.06, 0.05)               # 가로 창살
    for z in (za + 0.03, zb - 0.03):
        fc.box(M["wood"], uc, -t * 0.5, z, w, 0.08, 0.06)
    fc.box(M["stone"], uc, 0.07, za - 0.06, w + 0.3, 0.22, 0.12)                # 창턱
    if shutters and rnd.random() < 0.7:
        op = rnd.uniform(0.0, 1.0)
        for s in (-1, 1):
            hinge = ua if s < 0 else ub
            a = op * math.radians(100)
            sw = w / 2
            cu = hinge + s * (-sw / 2 * math.cos(a) * -1) if False else None
            # 덧문: 경첩에서 바깥으로 a 만큼 열림
            du = s * sw / 2 * math.cos(a)
            dn = sw / 2 * math.sin(a)
            uu = hinge + s * 0.05 + du
            M3 = fc.B @ MS.rotz(-s * a)
            fc.mb.box(M["plank"], fc.P(uu, 0.06 + dn, (za + zb) / 2), (sw, 0.04, h + 0.05), M3, (rnd.random(), 0))
    if rnd.random() < 0.25:                                                     # 화분 상자
        fc.box(M["plank"], uc, 0.2, za - 0.05, w * 0.9, 0.22, 0.2)


def door(fc, M, uc, w, h, t, rnd, z0=0.0, arch=True):
    fc.box(M["plank"], uc, -t * 0.6, z0 + h / 2, w, 0.08, h, uvoff=(rnd.random(), 0))   # 판자문
    for z in (z0 + 0.35, z0 + h - 0.45):                                        # 철 띠
        fc.box(M["iron"], uc, -t * 0.6 + 0.05, z, w * 0.85, 0.02, 0.06)
    fc.box(M["iron"], uc + w * 0.32, -t * 0.6 + 0.06, z0 + h * 0.5, 0.06, 0.04, 0.12)  # 손잡이
    k = 0.16
    for (u, z, su, sz) in ((uc - w / 2 - k / 2, z0 + h / 2, k, h), (uc + w / 2 + k / 2, z0 + h / 2, k, h)):
        fc.box(M["stone"], u, 0.03, z, su, t * 0.3 + 0.06, sz)
    fc.box(M["stone"], uc, 0.04, z0 + h + 0.12, w + 2 * k + 0.1, t * 0.3 + 0.08, 0.26)    # 상인방(돌)
    fc.box(M["stone"], uc, 0.25, z0 + 0.06, w + 0.5, 0.5, 0.12)                # 문턱 계단


def timber(fc, M, u0, u1, z0, z1, wins, rnd):
    """반목조 뼈대: 모서리 기둥, 창 옆 기둥, 위아래 보, 빈 칸 대각 버팀목"""
    W = M["wood"]
    e, k = 0.035, 0.17          # 회벽보다 e 튀어나옴, 굵기 k
    posts = {u0 + k / 2, u1 - k / 2}
    for ua, ub, za, zb in wins:
        posts |= {ua - k / 2 - 0.09, ub + k / 2 + 0.09}
    span = u1 - u0
    n_extra = max(0, int(span / 1.4))
    for i in range(1, n_extra + 1):
        u = u0 + span * i / (n_extra + 1)
        if all(abs(u - p) > 0.55 for p in posts) and all(not (ua - 0.3 < u < ub + 0.3) for ua, ub, _, _ in wins):
            posts.add(u)
    posts = sorted(posts)
    for u in posts:
        fc.box(W, u, e, (z0 + z1) / 2, k, 0.12, z1 - z0, uvoff=(rnd.random(), 0))
    fc.box(W, (u0 + u1) / 2, e, z0 + k / 2, u1 - u0, 0.12, k)
    fc.box(W, (u0 + u1) / 2, e, z1 - k / 2, u1 - u0, 0.12, k)
    for ua, ub, za, zb in wins:
        fc.box(W, (ua + ub) / 2, e, za - 0.2, ub - ua + 0.36, 0.12, k * 0.8)
    # 빈 칸 버팀목
    for a, b in zip(posts, posts[1:]):
        if b - a < 0.6:
            continue
        if any(ua < b and ub > a for ua, ub, _, _ in wins):
            continue
        L = math.hypot(b - a, z1 - z0 - 2 * k)
        ang = math.atan2(z1 - z0 - 2 * k, b - a)
        s = 1 if rnd.random() < 0.5 else -1
        fc.box(W, (a + b) / 2, e * 0.9, (z0 + z1) / 2, L, 0.11, k * 0.85, ang=-s * ang)
        if b - a > 1.3 and rnd.random() < 0.6:
            fc.box(W, (a + b) / 2, e * 0.9, (z0 + z1) / 2, L, 0.11, k * 0.85, ang=s * ang)


def house(seed, style="fire", W=None, D=None, floors=None, gable_front=None, collection=None, lit_p=0.35):
    rnd = random.Random(seed)
    M = mats(style)
    plaster = rnd.choice(M["plaster"])
    roof_m = rnd.choice(M["roof"])
    W = W or rnd.uniform(5.0, 7.5)
    D = D or rnd.uniform(5.5, 8.0)
    floors = floors if floors is not None else rnd.choice((1, 1, 2, 2, 2, 3))
    gable_front = rnd.random() < 0.5 if gable_front is None else gable_front
    uvo = (rnd.random() * 3, rnd.random() * 3)
    H0, HF, T0, TF, J = 3.0, 2.65, 0.5, 0.28, rnd.uniform(0.25, 0.45)
    info = {"lanterns": [], "chimneys": [], "doors": [], "size": (W, D), "style": style}
    mb = MS.MB()
    smat = {"stone": M["stone"], "plaster": plaster, "wood": M["wood"], "roof": roof_m, "plank": M["plank"],
            "glass": M["glass"], "glass_lit": M["glass_lit"], "iron": M["iron"]}
    MM = dict(smat)
    MM["stone"] = M["stone"]

    # 기단
    mb.box(M["stone"], (0, 0, 0.12), (W + 0.25, D + 0.25, 0.36), uvoff=uvo)
    # ---- 1층 (돌)
    hw, hd = W / 2, D / 2
    door_u = rnd.uniform(-hw + 1.2, hw - 1.2)
    dw, dh = rnd.uniform(1.0, 1.25), rnd.uniform(2.1, 2.35)
    front_ops = [(door_u - dw / 2, door_u + dw / 2, 0.0, dh)]
    nwin = int((W - 2.2) / 1.9)
    for i in range(nwin):
        u = -hw + (i + 0.5) * W / max(nwin, 1)
        if abs(u - door_u) > dw / 2 + 0.9:
            front_ops.append((u - 0.45, u + 0.45, 1.0, 2.2))
    sides = {"front": (front_ops, hd), "back": ([(-0.45, 0.45, 1.0, 2.1)], hd),
             "right": ([(-0.4, 0.4, 1.0, 2.1)] if rnd.random() < 0.6 else [], hw),
             "left": ([(-0.4, 0.4, 1.0, 2.1)] if rnd.random() < 0.6 else [], hw)}
    for side, (ops, half) in sides.items():
        fc = Facade(mb, side, half)
        span = W if side in ("front", "back") else D
        ext = 0 if side in ("front", "back") else -T0      # 옆벽은 앞뒤벽 사이에 끼움
        wall(fc, M["stone"], -span / 2 - ext * 0, span / 2, 0.0, H0, T0, ops, uvo) if side in ("front", "back") else \
            wall(fc, M["stone"], -span / 2 + T0, span / 2 - T0, 0.0, H0, T0, ops, uvo)
        for ua, ub, za, zb in ops:
            if za == 0.0:
                door(fc, MM, (ua + ub) / 2, ub - ua, zb, T0, rnd)
                info["doors"].append(tuple(fc.P((ua + ub) / 2, 0.6, 0)))
                info["lanterns"].append(tuple(fc.P(ub + 0.45, 0.32, dh + 0.2)))
            else:
                window(fc, MM, ua, ub, za, zb, T0, rnd, rnd.random() < lit_p, stone_frame=True)
    mb.box(M["plank"], (0, 0, H0 + 0.05), (W - 0.1, D - 0.1, 0.1))      # 천장(속 가림)

    # ---- 위층 (반목조, 앞뒤로 돌출)
    z = H0
    Df = D
    for f in range(floors):
        jj = J if f < 2 else 0.0
        Df += 2 * jj
        hdf = Df / 2
        # 바닥 보 띠 + 장선 끝
        for sgn in (-1, 1):
            mb.box(M["wood"], (0, sgn * (hdf - 0.12), z + 0.14), (W + 0.12, 0.26, 0.28), uvoff=(rnd.random(), 0))
            for i in range(int(W / 0.6) + 1):
                x = -W / 2 + 0.15 + i * 0.6
                if x < W / 2 - 0.1:
                    mb.box(M["wood"], (x, sgn * (hdf - jj / 2 - 0.12), z - 0.06), (0.16, jj + 0.3, 0.16))
        z0, z1 = z + 0.28, z + HF
        nw = max(1, int((W - 1.0) / 1.7))
        wins_f = []
        for i in range(nw):
            u = -W / 2 + (i + 0.5) * W / nw
            wins_f.append((u - 0.42, u + 0.42, z0 + 0.75, z0 + 1.85))
        for side in ("front", "back", "right", "left"):
            if side in ("front", "back"):
                fc = Facade(mb, side, hdf)
                ops = wins_f if side == "front" else ([wins_f[0]] if rnd.random() < 0.7 else [])
                wall(fc, plaster, -W / 2, W / 2, z0, z1, TF, ops, uvo)
                timber(fc, MM, -W / 2, W / 2, z0, z1, ops, rnd)
            else:
                fc = Facade(mb, side, W / 2)
                ops = [(-0.4, 0.4, z0 + 0.75, z0 + 1.75)] if rnd.random() < 0.5 else []
                wall(fc, plaster, -hdf + TF, hdf - TF, z0, z1, TF, ops, uvo)
                timber(fc, MM, -hdf + 0.02, hdf - 0.02, z0, z1, ops, rnd)
            for o in ops:
                window(fc, MM, *o, TF, rnd, rnd.random() < lit_p)
        z = z1
    top = z
    # ---- 지붕
    pitch = math.radians(rnd.uniform(42, 55))
    if gable_front:
        RW, RD, R = Df, W, MS.rotz(math.pi / 2)   # 용마루가 y 방향
    else:
        RW, RD, R = W, Df, Matrix.Identity(3)
    ov_e, ov_g, th = 0.55, 0.4, 0.2
    rise = RD / 2 * math.tan(pitch)
    L = (RD / 2 + ov_e) / math.cos(pitch)
    for sgn in (-1, 1):
        # 경사판 (용마루가 x 축, sgn 쪽으로 내려감)
        mid_y = sgn * (RD / 2 + ov_e) / 2
        mid_z = top + rise - (RD / 2 + ov_e) / 2 * math.tan(pitch)
        nrm = Vector((0, sgn * math.sin(pitch), math.cos(pitch)))
        c = Vector((0, mid_y, mid_z)) + nrm * (th / 2 + 0.02)
        Mr = R @ MS.rotx(-sgn * pitch)
        mb.box("roof", R @ c, (RW + 2 * ov_g, L, th), Mr, (rnd.random() * 5, rnd.random() * 5))
        # 처마 아래 판 (끝이 두꺼워 보이게)
        e = Vector((0, sgn * (RD / 2 + ov_e - 0.05), top + rise - (RD / 2 + ov_e) * math.tan(pitch) + 0.02))
        mb.box(M["wood"], R @ e, (RW + 2 * ov_g, 0.08, 0.22), R @ MS.rotx(-sgn * pitch))
        # 박공 끝 장식판 (barge board)
        for gx in (-1, 1):
            cb = Vector((gx * (RW / 2 + ov_g - 0.04), mid_y, mid_z)) + nrm * 0.02
            mb.box(M["wood"], R @ cb, (0.08, L, 0.32), Mr)
    # 용마루
    mb.box("roof", R @ Vector((0, 0, top + rise + th * 0.9)), (RW + 2 * ov_g + 0.1, 0.32, 0.18), R)
    # 박공벽 (삼각형) + 목재
    for gx in (-1, 1):
        x = gx * RW / 2
        tri = [R @ Vector((x - gx * 0.0, -RD / 2, top)), R @ Vector((x, RD / 2, top)), R @ Vector((x, 0, top + rise))]
        inward = R @ Vector((-gx * TF, 0, 0))
        mb.prism(plaster, [tuple(p) for p in tri], tuple(inward))
        # 가운데 기둥 + 대각 버팀 + 아래 보
        out = R @ Vector((gx * 0.035, 0, 0))
        def gbox(c, s, Mloc):
            mb.box(M["wood"], R @ Vector(c) + out, s, R @ Mloc)
        gbox((x, 0, top + rise / 2), (0.12, 0.17, rise), Matrix.Identity(3))
        gbox((x, 0, top + 0.09), (0.12, RD, 0.17), Matrix.Identity(3))
        for sy in (-1, 1):
            a = math.atan2(rise * 0.55, RD / 2 * 0.6)
            gbox((x, sy * RD * 0.17, top + rise * 0.3), (0.12, math.hypot(RD * 0.3, rise * 0.55), 0.15), MS.rotx(sy * a))
        if rise > 2.0:                                                          # 다락 창
            fcw = Facade(mb, "right" if (gx > 0) != gable_front else "left", 0)
            loc = R @ Vector((x, 0, top + rise * 0.45))
            mb.box(M["glass_lit"] if rnd.random() < lit_p else M["glass"], loc + R @ Vector((gx * 0.02, 0, 0)), (0.05, 0.6, 0.8), R)
            for dy, dz, sy2, sz2 in ((0, 0.44, 0.8, 0.09), (0, -0.44, 0.8, 0.09), (0.36, 0, 0.09, 0.8), (-0.36, 0, 0.09, 0.8)):
                mb.box(M["wood"], loc + R @ Vector((gx * 0.06, dy, dz)), (0.08, sy2, sz2), R)
    # 굴뚝
    if rnd.random() < 0.85:
        cx = rnd.uniform(-RW / 2 + 0.8, RW / 2 - 0.8)
        cy = rnd.choice((-1, 1)) * rnd.uniform(0.3, RD / 2 * 0.6)
        zr = top + rise - abs(cy) * math.tan(pitch)
        h = (top + rise + 1.2) - (zr - 0.5)
        c = R @ Vector((cx, cy, zr - 0.5 + h / 2))
        mb.box(M["stone"], c, (0.75, 0.75, h), R, (rnd.random(), rnd.random()))
        ct = R @ Vector((cx, cy, zr - 0.5 + h + 0.08))
        mb.box(M["stone"], ct, (0.92, 0.92, 0.16), R)
        info["chimneys"].append(tuple(ct + Vector((0, 0, 0.2))))
    info["height"] = top + rise
    mats_map = {k: v for k, v in smat.items()}
    mats_map["roof"] = roof_m
    keymap = {}
    # MB 키가 재질 오브젝트일 수도, 문자열일 수도 있음 -> 이름으로 정리
    allm = {}
    for k in mb.parts:
        allm[k] = k if isinstance(k, bpy.types.Material) else mats_map[k]
    ob = mb.build(f"house_{style}_{seed}", allm, collection, bevel=0.025)
    return ob, info
