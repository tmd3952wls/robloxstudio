"""표정 얼굴 (Expressive Cartoon Face) — 매개변수 -> 2D 도형 -> 머리 앞면에 붙는 메시.

모든 부위가 '연속 매개변수'라서 감정 사이를 부드럽게 섞을 수 있다 (이미지 교체 X).
- 눈: 흰자(위 곡선 T(x) = min(타원 위, 윗눈꺼풀 선), 아래 곡선 B(x) = max(타원 아래, 아랫눈꺼풀 곡선))
  · 눈 감기/깜빡임 = 윗눈꺼풀이 내려옴, 웃는 눈(^) = 아랫눈꺼풀이 위로 휘어 올라옴 -> 같은 식에서 자연스럽게 이어짐
  · 동공: 크기·시선(lx, ly), 하이라이트, 눈 안쪽으로 잘림
- 눈썹: 높이·각도(+ 안쪽이 내려감 = 화남)·휨·두께
- 입: 위/아래 입술 곡선 U(x), L(x) — 웃음/찡그림(curve), 벌림(open), 이(teeth: 0~1, 1=악문 이), 떨림(wobble), 비대칭(skew), 혀
- 부가: 눈물(고임 tears·흐름 flow), 땀, 볼터치(blush), 공포 그늘선(gloom)
좌표: 머리 앞면 정사각형을 [-0.5,0.5]^2 로 둔 비율 좌표. 어떤 크기의 머리에도 그대로 재사용.
"""
import math

import bpy

NEUTRAL = dict(
    eye_sep=0.185, eye_y=0.05, eye_w=0.082, eye_h=0.105,
    openL=1.0, openR=1.0,             # 눈 크기 배율 (1.35 = 크게 뜸)
    lidL=1.25, lidR=1.25,             # 윗눈꺼풀 높이 (eye_h 배율, 1.25 이상이면 안 보임, -1 이면 감김)
    lidAngL=0.0, lidAngR=0.0,         # 윗눈꺼풀 기울기 (+ 안쪽이 내려감: 화남 / - : 슬픔)
    lowL=0.0, lowR=0.0,               # 아랫눈꺼풀 올림 (0~1, 웃는 눈은 1.0)
    pupil=0.5,                        # 동공 크기 (eye_w 배율)
    lx=0.0, ly=0.0,                   # 시선 (-1~1)
    browYL=0.0, browYR=0.0,           # 눈썹 높이 오프셋
    browAL=0.0, browAR=0.0,           # 눈썹 각도 (+ 안쪽 내려감)
    browC=0.0,                        # 눈썹 휨 (+ 아치)
    browW=1.0,                        # 두께 배율
    mw=0.115, my=-0.215, mopen=0.0, mcurve=0.25, teeth=0.0, wobble=0.0, skew=0.0, tongue=0.0, mshape=0.0,
    tears=0.0, flow=0.0, sweat=0.0, blush=0.0, gloom=0.0,
)
KEYS = list(NEUTRAL)

# 재질 슬롯
INK, WHITE, MOUTH, TONGUE, TEAR, BLUSH, GLOOM, SWEAT = range(8)


def lerp_params(a, b, t):
    return {k: a[k] + (b[k] - a[k]) * t for k in KEYS}


class Shape:
    """삼각형 모음: (3 점, 층, 재질)"""

    def __init__(self):
        self.tris = []

    def strip(self, xs, top, bot, layer, mat):
        """x 단조 영역: 각 x 에서 bot~top 사이 채움"""
        for i in range(len(xs) - 1):
            a0, a1 = (xs[i], bot[i]), (xs[i], top[i])
            b0, b1 = (xs[i + 1], bot[i + 1]), (xs[i + 1], top[i + 1])
            if top[i] - bot[i] < 1e-5 and top[i + 1] - bot[i + 1] < 1e-5:
                continue
            self.tris.append(((a0, b0, b1), layer, mat))
            self.tris.append(((a0, b1, a1), layer, mat))

    def stroke(self, pts, width, layer, mat=INK, closed=False, taper=None, caps=True):
        """폴리라인 굵은 선 (taper: 점마다 굵기 배율)"""
        n = len(pts)
        if n < 2:
            return
        L = []
        R = []
        for i in range(n):
            p = pts[i]
            if closed:
                q0, q1 = pts[(i - 1) % n], pts[(i + 1) % n]
            else:
                q0, q1 = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
            dx, dy = q1[0] - q0[0], q1[1] - q0[1]
            ln = math.hypot(dx, dy) or 1e-6
            nx, ny = -dy / ln, dx / ln
            w = width * (taper[i] if taper else 1.0) / 2
            L.append((p[0] + nx * w, p[1] + ny * w))
            R.append((p[0] - nx * w, p[1] - ny * w))
        rng = range(n) if closed else range(n - 1)
        for i in rng:
            j = (i + 1) % n
            self.tris.append(((L[i], R[i], R[j]), layer, mat))
            self.tris.append(((L[i], R[j], L[j]), layer, mat))
        if caps and not closed:
            for i in (0, n - 1):
                self.disc(pts[i], width * (taper[i] if taper else 1.0) / 2, layer, mat, 8)

    def disc(self, c, r, layer, mat, seg=14, sx=1.0, sy=1.0):
        if r <= 1e-5:
            return
        for k in range(seg):
            a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
            self.tris.append(((c, (c[0] + r * sx * math.cos(a0), c[1] + r * sy * math.sin(a0)),
                               (c[0] + r * sx * math.cos(a1), c[1] + r * sy * math.sin(a1))), layer, mat))


def _eye(sh, P, side, t):
    s = "L" if side < 0 else "R"
    cx = side * P["eye_sep"] + P["lx"] * P["eye_w"] * 0.0
    cy = P["eye_y"]
    w = P["eye_w"] * (0.9 + 0.1 * P[f"open{s}"])
    h = P["eye_h"] * P[f"open{s}"]
    N = 26
    xs = [cx - w + 2 * w * i / (N - 1) for i in range(N)]
    lid = P[f"lid{s}"]
    ang = P[f"lidAng{s}"]
    low = P[f"low{s}"]
    T, B = [], []
    for x in xs:
        dx = (x - cx) / w
        e = math.sqrt(max(0.0, 1 - dx * dx))
        etop, ebot = cy + h * e, cy - h * e
        inner = -dx * side             # 안쪽(코 쪽)이 +1
        ulid = cy + P["eye_h"] * lid - ang * P["eye_h"] * 0.9 * inner
        llid = cy - P["eye_h"] * 1.3 + low * P["eye_h"] * 2.25 * (1 - dx * dx)
        tt, bb = min(etop, ulid), max(ebot, llid)
        if tt < bb:                    # 감김: 선 하나로 모임
            m = min(max((tt + bb) / 2, ebot), etop)
            tt = bb = m
        T.append(tt)
        B.append(bb)
    sh.strip(xs, T, B, 0, WHITE)
    # 동공 (눈 안쪽으로 잘림)
    pr = P["pupil"] * w * 0.95
    px = cx + P["lx"] * (w - pr) * 0.75
    py = cy + P["ly"] * (P["eye_h"] - pr) * 0.6
    pxs, ptop, pbot = [], [], []
    M = 20
    for i in range(M):
        x = px - pr + 2 * pr * i / (M - 1)
        dx = (x - px) / pr
        e = math.sqrt(max(0.0, 1 - dx * dx)) * pr
        k = min(max(int((x - xs[0]) / (xs[1] - xs[0])), 0), N - 2)
        f = (x - xs[k]) / (xs[1] - xs[0])
        tt = T[k] + (T[k + 1] - T[k]) * f
        bb = B[k] + (B[k + 1] - B[k]) * f
        if x < xs[0] or x > xs[-1]:
            tt = bb = 0
        pxs.append(x)
        ptop.append(max(min(py + e, tt), bb if tt > bb else tt))
        pbot.append(min(max(py - e, bb), ptop[-1]))
    sh.strip(pxs, ptop, pbot, 1, INK)
    # 하이라이트
    hx, hy = px + pr * 0.35, py + pr * 0.4
    k = min(max(int((hx - xs[0]) / (xs[1] - xs[0])), 0), N - 2)
    if T[k] - B[k] > pr * 0.8 and pr > 0.012:
        sh.disc((hx, min(hy, T[k] - pr * 0.3)), pr * 0.28, 2, WHITE, 10)
    # 눈물 고임 (흰자 아래쪽을 파랗게 + 반짝임)
    if P["tears"] > 0.02:
        tb = [b + (tt - b) * min(1, P["tears"]) * 0.42 for tt, b in zip(T, B)]
        sh.strip(xs, tb, B, 3, TEAR)
    # 테두리 (위는 굵게)
    width = 0.029
    top_pts = list(zip(xs, T))
    bot_pts = list(zip(xs, B))
    sh.stroke(top_pts, width * 1.25, 4, INK, taper=[0.7 + 0.6 * math.sin(math.pi * i / (N - 1)) for i in range(N)])
    sh.stroke(bot_pts, width * 0.8, 4, INK)
    # 눈물 줄기
    if P["flow"] > 0.02:
        x0 = cx + side * w * 0.25
        y0 = min(B) + 0.005
        L = 0.05 + 0.33 * P["flow"]
        pts = [(x0 + side * 0.012 * math.sin(i * 0.9 + t * 3), y0 - L * i / 8) for i in range(9)]
        sh.stroke(pts, 0.03, 5, TEAR, taper=[1.0 - 0.3 * i / 8 for i in range(9)])
        drop_y = y0 - L - 0.02 - 0.03 * ((t * 1.3) % 1.0)
        sh.disc((x0, drop_y), 0.019, 5, TEAR, 10, 0.8, 1.2)
    return cx, cy, w, h, max(T)


def _brow(sh, P, side, eye_top):
    s = "L" if side < 0 else "R"
    cx = side * P["eye_sep"]
    base = max(eye_top, P["eye_y"] + P["eye_h"] * 0.6) + 0.075 + P[f"browY{s}"]
    ang = P[f"browA{s}"]
    half = 0.085
    N = 10
    pts, tap = [], []
    for i in range(N):
        t = i / (N - 1)                      # 0 = 안쪽, 1 = 바깥
        x = cx - side * half + side * 2 * half * t
        y = base + (t - 0.5) * 2 * half * ang * 1.1 + P["browC"] * 0.03 * (1 - (2 * t - 1) ** 2)
        pts.append((x, y))
        tap.append(1.25 - 0.55 * t)
    sh.stroke(pts, 0.046 * P["browW"], 6, INK, taper=tap)


def _mouth(sh, P, t):
    mw = P["mw"] * (1 + 0.25 * P["mopen"] * (1 - P["mshape"]) - 0.35 * P["mshape"])
    my = P["my"]
    N = 29
    xs = [-mw + 2 * mw * i / (N - 1) for i in range(N)]
    U, L = [], []
    for x in xs:
        u = x / mw
        c = my + P["mcurve"] * 0.055 * (u * u - 0.35) + P["skew"] * 0.04 * u
        wob = P["wobble"] * 0.013 * math.sin(u * math.pi * 3 + t * 9)
        o = P["mopen"]
        env = max(0.0, 1 - u * u)
        up = c + o * 0.03 * env ** 0.8 + wob
        lo = c - o * 0.16 * env ** 0.6 + wob * (1 + o)
        if P["teeth"] > 0.6:                   # 악문 이: 네모난 입
            sq = (P["teeth"] - 0.6) / 0.4
            env2 = 1 - u ** 8
            up = up * (1 - sq) + (c + 0.045 * env2 + wob) * sq
            lo = lo * (1 - sq) + (c - 0.045 * env2 - 0.01 * P["mopen"] + wob) * sq
        U.append(up)
        L.append(lo)
    open_any = any(u - l > 0.004 for u, l in zip(U, L))
    if open_any:
        sh.strip(xs, U, L, 0, MOUTH)
        if P["tongue"] > 0.02:
            tt = [min(u, l + P["tongue"] * 0.06 * (1 - (x / mw) ** 2)) for x, u, l in zip(xs, U, L)]
            sh.strip(xs, tt, L, 1, TONGUE)
        if P["teeth"] > 0.02:
            if P["teeth"] > 0.6:
                sh.strip(xs, U, L, 1, WHITE)
                mid = [(u + l) / 2 for u, l in zip(U, L)]
                sh.stroke(list(zip(xs, mid)), 0.012, 2, INK)
                for k in range(1, 6):
                    i = int(k * (N - 1) / 6)
                    sh.stroke([(xs[i], U[i]), (xs[i], L[i])], 0.011, 2, INK, caps=False)
            else:
                tb = [max(l, u - P["teeth"] * 0.05) for u, l in zip(U, L)]
                sh.strip(xs, U, tb, 1, WHITE)
        pts = list(zip(xs, U)) + list(reversed(list(zip(xs, L))))
        sh.stroke(pts, 0.027, 3, INK, closed=True)
    else:
        sh.stroke(list(zip(xs, U)), 0.03, 3, INK, taper=[0.6 + 0.4 * math.sin(math.pi * i / (N - 1)) for i in range(N)])


def build_shapes(P, t=0.0):
    sh = Shape()
    tops = {}
    for side in (-1, 1):
        cx, cy, w, h, top = _eye(sh, P, side, t)
        tops[side] = top
    for side in (-1, 1):
        _brow(sh, P, side, tops[side])
    _mouth(sh, P, t)
    if P["blush"] > 0.02:
        for side in (-1, 1):
            sh.disc((side * 0.27, -0.09), 0.06 * P["blush"], 0, BLUSH, 16, 1.4, 0.7)
    if P["sweat"] > 0.02:
        s = P["sweat"]
        c = (0.36, 0.2 - 0.03 * ((t * 0.8) % 1.0))
        sh.disc(c, 0.035 * s, 7, SWEAT, 14, 0.85, 1.0)
        sh.tris.append((((c[0] - 0.03 * s, c[1] + 0.005), (c[0] + 0.03 * s, c[1] + 0.005), (c[0], c[1] + 0.075 * s)), 7, SWEAT))
    if P["gloom"] > 0.02:
        for i, x in enumerate((-0.2, -0.1, 0.0, 0.1, 0.2)):
            L = 0.16 * P["gloom"] * (1.0 if i % 2 == 0 else 0.7)
            sh.stroke([(x, 0.4), (x, 0.4 - L * 1.3)], 0.026, 0, GLOOM, caps=False)
    return sh


# ------------------------------------------------------------------ 블렌더 메시
def face_materials(prefix="Face"):
    def m(name, col, emit=0.0, alpha=1.0, rough=0.35):
        mat = bpy.data.materials.get(f"{prefix}_{name}")
        if mat:
            return mat
        mat = bpy.data.materials.new(f"{prefix}_{name}")
        mat.use_nodes = True
        bs = mat.node_tree.nodes["Principled BSDF"]
        bs.inputs["Base Color"].default_value = col + (1,)
        bs.inputs["Roughness"].default_value = rough
        if emit:
            bs.inputs["Emission Color"].default_value = col + (1,)
            bs.inputs["Emission Strength"].default_value = emit
        if alpha < 1:
            bs.inputs["Alpha"].default_value = alpha
            try:
                mat.surface_render_method = "BLENDED"
            except Exception:
                pass
        return mat
    return [m("ink", (0.004, 0.004, 0.004), rough=0.85), m("white", (0.92, 0.92, 0.9), rough=0.3),
            m("mouth", (0.22, 0.02, 0.03), rough=0.5), m("tongue", (0.85, 0.3, 0.35)),
            m("tear", (0.35, 0.7, 1.0), emit=0.6, alpha=0.85, rough=0.05), m("blush", (1.0, 0.45, 0.5), alpha=0.45),
            m("gloom", (0.18, 0.12, 0.45), alpha=0.95), m("sweat", (0.55, 0.85, 1.0), emit=0.4, alpha=0.9, rough=0.05)]


class FaceRig:
    """머리 오브젝트에 붙는 얼굴 메시. 머리 로컬: 앞면이 -Y, 머리 가운데가 원점.
    size: 머리 앞면 한 변 (m), depth: 가운데~앞면 거리, bevel: 머리 모서리 반지름 (곡면 따라 붙이기)"""

    def __init__(self, head_ob, size, depth, bevel, z_center=0.0, prefix="Face"):
        self.head, self.S, self.Dp, self.Rb, self.zc = head_ob, size, depth, bevel, z_center
        me = bpy.data.meshes.new(head_ob.name + "_face")
        self.ob = bpy.data.objects.new(head_ob.name + "_face", me)
        for c in head_ob.users_collection:
            c.objects.link(self.ob)
        self.ob.parent = head_ob
        for mt in face_materials(prefix):
            me.materials.append(mt)
        self.ob.visible_shadow = False

    def _surf(self, u, v, layer):
        S, Rb = self.S, self.Rb
        x, z = u * S, v * S
        y = -self.Dp
        flat = S / 2 - Rb
        for c in (abs(x), abs(z)):
            if c > flat:
                d = min(c - flat, Rb * 0.98)
                y += Rb - math.sqrt(Rb * Rb - d * d)
        return (x, y - 0.0015 - layer * 0.0006, z + self.zc)

    def update(self, P, t=0.0):
        sh = build_shapes(P, t)
        verts, faces, mids = [], [], []
        for (a, b, c), layer, mat in sh.tris:
            i = len(verts)
            verts += [self._surf(*a, layer), self._surf(*b, layer), self._surf(*c, layer)]
            area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            faces.append((i, i + 1, i + 2) if area > 0 else (i, i + 2, i + 1))     # 법선이 앞(-Y)을 보도록
            mids.append(mat)
        me = self.ob.data
        me.clear_geometry()
        me.from_pydata(verts, [], faces)
        me.polygons.foreach_set("material_index", mids)
        me.update()
