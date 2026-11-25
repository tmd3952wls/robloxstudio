"""절차적 지형: 침식된 능선 산맥 + 강 골짜기 + 마을 평지 + 화산(분화구·용암 흐름).

numpy 높이맵 -> 메시. 정점 색 속성 'mask' (R=탄 땅, G=강가 진흙, B=마을 흙, A=용암) 으로 재질을 섞는다.
높이 조회 H(x, y) 로 건물·나무를 땅에 붙인다.
LAYOUTS 에 새 지형 배치를 추가하면 다른 주제(해안·사막·협곡)에도 재사용.
"""
import math

import bpy
import numpy as np

import pbr


# ------------------------------------------------------------------ 노이즈 (numpy, 시드 고정)
def _hash2(ix, iy, seed):
    h = (ix * 374761393 + iy * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h & 0xFFFF) / 65535.0


def vnoise(x, y, seed=0):
    ix, iy = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - ix, y - iy
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = _hash2(ix, iy, seed); b = _hash2(ix + 1, iy, seed)
    c = _hash2(ix, iy + 1, seed); d = _hash2(ix + 1, iy + 1, seed)
    return (a + (b - a) * ux) + ((c + (d - c) * ux) - (a + (b - a) * ux)) * uy


def fbm(x, y, octaves=6, seed=0, lac=2.03, gain=0.5):
    s, amp, f, norm = 0.0, 1.0, 1.0, 0.0
    for o in range(octaves):
        s = s + amp * vnoise(x * f, y * f, seed + o * 17)
        norm += amp
        amp *= gain
        f *= lac
    return s / norm


def ridged(x, y, octaves=7, seed=0):
    """날카로운 능선 + 골짜기 (산맥 침식 느낌): 1-|2n-1| 을 쌓고 앞 옥타브가 뒤를 조절"""
    s, amp, f, w, norm = 0.0, 1.0, 1.0, 1.0, 0.0
    for o in range(octaves):
        n = 1.0 - np.abs(2 * vnoise(x * f, y * f, seed + o * 31) - 1)
        n = n * n * w
        w = np.clip(n * 1.6, 0, 1)
        s = s + amp * n
        norm += amp
        amp *= 0.52
        f *= 2.1
    return s / norm


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ 배치
class Valley:
    """강 골짜기 두 마을 + 뒤쪽 산맥 + 화산"""

    def __init__(self, seed=3, x0=-1700, x1=1700, y0=-600, y1=3400, cell=5.0):
        self.seed, self.x0, self.x1, self.y0, self.y1, self.cell = seed, x0, x1, y0, y1, cell
        self.volcano = (-720.0, 1650.0)
        self.river_w = 36.0
        self.town_z = 2.4
        self.water_z = -0.9

    def river_x(self, y):
        return 22 * np.sin(y / 150.0) + 9 * np.sin(y / 61.0 + 1.3)

    def heights(self):
        xs = np.arange(self.x0, self.x1 + 1e-6, self.cell)
        ys = np.arange(self.y0, self.y1 + 1e-6, self.cell)
        X, Y = np.meshgrid(xs, ys)
        sd = self.seed
        d = np.abs(X - self.river_x(Y))                       # 강까지 거리
        # 언덕 (마을 뒤) + 산맥 (멀리)
        hills = 70 * fbm(X / 380, Y / 380, 6, sd) * smooth(160, 520, d)
        mtn_mask = smooth(600, 1500, Y) * smooth(120, 700, d)
        mtn = 820 * ridged(X / 900, Y / 900, 7, sd + 5) * mtn_mask
        h = 4 + hills + mtn + 6 * fbm(X / 60, Y / 60, 4, sd + 9)
        # 골짜기 양옆 가파른 벽 (마을 뒤 낮은 절벽)
        h += 30 * smooth(250, 330, d) * fbm(X / 120, Y / 120, 3, sd + 2)
        # 화산
        vx, vy = self.volcano
        r = np.hypot(X - vx, Y - vy)
        cone = 1050 * np.clip(1 - r / 1000, 0, 1) ** 1.5
        cone *= 1 + 0.08 * (ridged(X / 140, Y / 140, 5, sd + 7) - 0.5) * np.clip(r / 300, 0, 1)
        crater = 120 * (1 - smooth(60, 120, r))
        h = np.maximum(h, cone - crater)
        # 마을 평지 (강 양쪽 띠, 앞뒤 경계는 완만하게)
        town = smooth(240, 190, d) * smooth(-330, -250, Y) * smooth(420, 340, Y)
        h = h * (1 - town) + (self.town_z + 0.15 * fbm(X / 30, Y / 30, 3, sd + 11)) * town
        # 강둑 + 강바닥
        bank = smooth(self.river_w / 2 + 14 - 11 * town, self.river_w / 2 + 2, d)
        h = h * (1 - bank) + (self.water_z - 2.2 + 0.6 * fbm(X / 12, Y / 12, 3, sd)) * bank
        self.X, self.Y, self.Hm, self.D = X, Y, h, d
        self.xs, self.ys = xs, ys
        return h

    def masks(self):
        X, Y, h, d = self.X, self.Y, self.Hm, self.D
        sd = self.seed
        vx, vy = self.volcano
        r = np.hypot(X - vx, Y - vy)
        fire_side = (X < self.river_x(Y)).astype(float)
        burned = np.clip(smooth(1150, 850, r), 0, 1)
        burned = np.maximum(burned, fire_side * smooth(900, 250, d) * smooth(-200, 500, Y) * 0.6 * (0.6 + 0.8 * fbm(X / 90, Y / 90, 4, sd + 3)))
        mud = smooth(self.river_w / 2 + 22, self.river_w / 2 + 6, d)
        town = smooth(235, 200, d) * smooth(-330, -260, Y) * smooth(420, 350, Y)
        lava = self._lava_paths(r)
        return np.stack([np.clip(burned, 0, 1), mud, town * (1 - mud), lava], -1)

    def _lava_paths(self, r):
        """분화구에서 경사 따라 내려가는 용암 줄기 몇 개 (입자 내려보내기)"""
        h = self.Hm
        ny, nx = h.shape
        lava = np.zeros_like(h)
        vx, vy = self.volcano
        rng = np.random.default_rng(self.seed)
        gy, gx = np.gradient(h)
        for k in range(16):
            a = rng.uniform(-math.pi * 0.95, -math.pi * 0.05) if k % 3 else rng.uniform(0, 2 * math.pi)
            px = (vx + 110 * math.cos(a) - self.x0) / self.cell
            py = (vy + 110 * math.sin(a) - self.y0) / self.cell
            wid = rng.uniform(4.0, 8.0)
            for step in range(260):
                ix, iy = int(px), int(py)
                if not (2 <= ix < nx - 2 and 2 <= iy < ny - 2):
                    break
                w = wid * (1 - step / 300)
                rr = int(w) + 2
                yy, xx = np.mgrid[iy - rr:iy + rr + 1, ix - rr:ix + rr + 1]
                yy, xx = np.clip(yy, 0, ny - 1), np.clip(xx, 0, nx - 1)
                dist = np.hypot(xx - px, yy - py)
                lava[yy, xx] = np.maximum(lava[yy, xx], np.clip(1 - dist / max(w, 0.8), 0, 1))
                g = np.array([gx[iy, ix], gy[iy, ix]])
                n = np.linalg.norm(g)
                if n < 1e-3:
                    break
                px -= g[0] / n * 1.0 + rng.normal(0, 0.35)
                py -= g[1] / n * 1.0 + rng.normal(0, 0.35)
                if h[iy, ix] < 120:
                    break
        return lava

    def D_at(self, x, y):
        return abs(x - float(self.river_x(y)))

    def H(self, x, y):
        """높이 조회 (쌍선형)"""
        fx = (np.asarray(x) - self.x0) / self.cell
        fy = (np.asarray(y) - self.y0) / self.cell
        ix = np.clip(np.floor(fx).astype(int), 0, len(self.xs) - 2)
        iy = np.clip(np.floor(fy).astype(int), 0, len(self.ys) - 2)
        tx, ty = fx - ix, fy - iy
        h = self.Hm
        return (h[iy, ix] * (1 - tx) * (1 - ty) + h[iy, ix + 1] * tx * (1 - ty) +
                h[iy + 1, ix] * (1 - tx) * ty + h[iy + 1, ix + 1] * tx * ty)

    def flatten(self, x, y, rad, z):
        """건물 자리 평평하게 (마을 평지 밖 언덕에 지을 때)"""
        m = smooth(rad + 6, rad, np.hypot(self.X - x, self.Y - y))
        self.Hm = self.Hm * (1 - m) + z * m


terrain_smooth = smooth


def build_mesh(V, name="Terrain", crop=None):
    """crop=(x0,x1,y0,y1) 이면 그 부분만 (가까운 장면용 고해상도 조각)"""
    h, m = V.Hm, V.masks()
    xs, ys = V.xs, V.ys
    if crop:
        ix0, ix1 = np.searchsorted(xs, crop[0]), np.searchsorted(xs, crop[1])
        iy0, iy1 = np.searchsorted(ys, crop[2]), np.searchsorted(ys, crop[3])
        xs, ys, h, m = xs[ix0:ix1], ys[iy0:iy1], h[iy0:iy1, ix0:ix1], m[iy0:iy1, ix0:ix1]
    ny, nx = h.shape
    X, Y = np.meshgrid(xs, ys)
    verts = np.stack([X.ravel(), Y.ravel(), h.ravel()], -1).astype(np.float32)
    ii = np.arange(ny * nx).reshape(ny, nx)
    a, b, c, d = ii[:-1, :-1].ravel(), ii[:-1, 1:].ravel(), ii[1:, 1:].ravel(), ii[1:, :-1].ravel()
    quads = np.stack([a, b, c, d], -1)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(len(quads) * 4)
    me.loops.foreach_set("vertex_index", quads.ravel().astype(np.int32))
    me.polygons.add(len(quads))
    me.polygons.foreach_set("loop_start", np.arange(0, len(quads) * 4, 4, dtype=np.int32))
    me.polygons.foreach_set("loop_total", np.full(len(quads), 4, dtype=np.int32))
    me.update(calc_edges=True)
    me.validate()
    fa = me.attributes.new("field", "FLOAT", "POINT")
    gy, gx = np.gradient(h, V.cell)
    flat = np.clip(1 - np.hypot(gx, gy) / 0.12, 0, 1)
    dd = np.abs(X - V.river_x(Y))
    field = flat * terrain_smooth(250, 300, dd) * terrain_smooth(900, 600, dd) * (h < 80) * (1 - m[..., 0]) * (1 - m[..., 3])
    fa.data.foreach_set("value", field.astype(np.float32).ravel())
    ca = me.color_attributes.new("mask", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", m.reshape(-1, 4).astype(np.float32).ravel())
    me.polygons.foreach_set("use_smooth", np.ones(len(quads), dtype=bool))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(terrain_mat())
    return ob


def terrain_mat():
    """경사·높이·마스크로 풀/바위/눈/탄 땅/진흙/마을 흙/용암 섞기 (월드 좌표 투영, 미터 단위)"""
    if "Terrain" in bpy.data.materials:
        return bpy.data.materials["Terrain"]
    m = pbr.new_mat("Terrain")
    b = pbr.NB(m)
    geo = b.n("ShaderNodeNewGeometry")
    sep = b.n("ShaderNodeSeparateXYZ")
    b.ln(geo.outputs["Position"], sep.inputs[0])
    nsep = b.n("ShaderNodeSeparateXYZ")
    b.ln(geo.outputs["Normal"], nsep.inputs[0])
    att = b.n("ShaderNodeAttribute", attribute_name="mask")
    msep = b.n("ShaderNodeSeparateColor")
    b.ln(att.outputs["Color"], msep.inputs[0])

    def T(aid, tile, tint=None, gain=1.0):
        tc = b.n("ShaderNodeTexCoord")
        mp = b.n("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1 / tile,) * 3
        b.ln(geo.outputs["Position"], mp.inputs["Vector"])
        out = {}
        for k in ("diff", "rough", "nor_gl"):
            e = pbr.assets.catalog()[aid]
            if k not in e["files"]:
                continue
            t = b.n("ShaderNodeTexImage", image=pbr.img(pbr.assets.path(aid, k), k != "diff"))
            b.ln(mp.outputs[0], t.inputs["Vector"])
            out[k] = t.outputs[0]
        col = out["diff"]
        if tint or gain != 1:
            hs = b.n("ShaderNodeHueSaturation", i_Value=gain)
            b.ln(col, hs.inputs["Color"])
            col = hs.outputs[0]
            if tint:
                col = b.mix(1.0, col, tuple(tint) + (1,), blend="MULTIPLY")
        return col, out.get("rough"), out.get("nor_gl")

    grass = T("leafy_grass", 5.0, pbr.srgb(150, 190, 110))
    grass2 = T("sparse_grass", 9.0, pbr.srgb(170, 175, 100))
    rock = T("aerial_rocks_02", 22.0, pbr.srgb(150, 150, 150), 0.85)
    cliff = T("rock_face", 9.0, pbr.srgb(180, 178, 172))
    snow = T("snow_02", 8.0, None, 1.15)
    burned = T("burned_ground_01", 7.0)
    mud = T("dry_riverbed_rock", 5.0)
    dirt = T("brown_mud_rocks_01", 4.0)

    def blend(f, A, B):
        return (b.mix(f, A[0], B[0]),
                b.mix(f, A[1], B[1], dtype="FLOAT") if A[1] and B[1] else (A[1] or B[1]),
                b.mix(f, A[2], B[2]) if A[2] and B[2] else (A[2] or B[2]))

    def rng(v, a, c, interp="SMOOTHSTEP"):
        mr = b.n("ShaderNodeMapRange", i_From_Min=a, i_From_Max=c, interpolation_type=interp)
        b.ln(v, mr.inputs["Value"])
        return mr.outputs[0]

    nz = b.n("ShaderNodeTexNoise", i_Scale=0.004, i_Detail=5.0)
    b.ln(geo.outputs["Position"], nz.inputs["Vector"])
    nzs = b.n("ShaderNodeTexNoise", i_Scale=0.08, i_Detail=4.0)
    b.ln(geo.outputs["Position"], nzs.inputs["Vector"])
    # 풀 두 종류 큰 얼룩
    L = blend(rng(nz.outputs["Fac"], 0.42, 0.6), grass, grass2)
    # 밭 조각 (보로노이 칸마다 다른 색: 초록/노랑/갈색), 평지에서만
    fv = b.n("ShaderNodeTexVoronoi", i_Scale=0.012, i_Randomness=0.85)
    b.ln(geo.outputs["Position"], fv.inputs["Vector"])
    cr = b.n("ShaderNodeValToRGB")
    els = cr.color_ramp.elements
    els[0].position, els[0].color = 0.0, pbr.srgb(120, 150, 60) + (1,)
    els[1].position, els[1].color = 1.0, pbr.srgb(140, 110, 60) + (1,)
    for pos, c in ((0.3, pbr.srgb(190, 170, 80)), (0.55, pbr.srgb(90, 125, 55)), (0.8, pbr.srgb(170, 140, 70))):
        e = els.new(pos); e.color = c + (1,)
    cr.color_ramp.interpolation = "CONSTANT"
    b.ln(fv.outputs["Color"], cr.inputs["Fac"]) if "Color" in fv.outputs else None
    sepc = b.n("ShaderNodeSeparateColor")
    b.ln(fv.outputs["Color"], sepc.inputs[0])
    b.ln(sepc.outputs[0], cr.inputs["Fac"])
    fieldcol = b.mix(1.0, L[0], cr.outputs[0], blend="MULTIPLY")
    fieldcol = b.n("ShaderNodeHueSaturation", i_Value=1.7)
    b.ln(b.mix(1.0, L[0], cr.outputs[0], blend="MULTIPLY"), fieldcol.inputs["Color"])
    att_d = b.n("ShaderNodeAttribute", attribute_name="field")
    fieldf = b.math("MULTIPLY", att_d.outputs["Fac"], rng(fv.outputs["Distance"], 0.0, 0.05))
    L = (b.mix(fieldf, L[0], fieldcol.outputs[0]), L[1], L[2])
    # 마을 흙
    L = blend(b.math("MULTIPLY", msep.outputs["Blue"], rng(nzs.outputs["Fac"], 0.3, 0.55)), L, dirt)
    # 경사 -> 바위 (멀리 큰 바위 / 가까운 절벽)
    steep = rng(b.math("ADD", nsep.outputs["Z"], b.math("MULTIPLY", nzs.outputs["Fac"], 0.15)), 0.86, 0.72)
    R = blend(rng(sep.outputs["Z"], 40, 140), cliff, rock)
    L = blend(steep, L, R)
    # 높은 곳 바위 (나무 한계선 위)
    L = blend(rng(b.math("ADD", sep.outputs["Z"], b.math("MULTIPLY", nz.outputs["Fac"], 120)), 330, 420), L, rock)
    # 눈 (높고 덜 가파른 곳)
    snowf = b.math("MULTIPLY", rng(b.math("ADD", sep.outputs["Z"], b.math("MULTIPLY", nz.outputs["Fac"], 160)), 560, 640),
                   rng(nsep.outputs["Z"], 0.45, 0.7))
    snowf = b.math("MULTIPLY", snowf, b.math("SUBTRACT", 1.0, msep.outputs["Red"]))
    L = blend(snowf, L, snow)
    # 화산 지대: 탄 땅 + 검은 현무암 (경사 급하면 바위), 눈보다 우선
    basalt = T("rock_face", 12.0, pbr.srgb(70, 64, 60), 0.8)
    volc = blend(steep, burned, basalt)
    L = blend(msep.outputs["Red"], L, volc)
    # 강가 진흙·자갈
    L = blend(msep.outputs["Green"], L, mud)
    col, rough, nor = L
    # 용암: 균열 무늬 (보로노이) 빛나는 주황 + 검은 껍질
    vor = b.n("ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE", i_Scale=0.18)
    b.ln(geo.outputs["Position"], vor.inputs["Vector"])
    crack = rng(vor.outputs["Distance"], 0.12, 0.0)
    lava_m = msep.outputs["Alpha"] if "Alpha" in msep.outputs else att.outputs["Alpha"]
    lava_m = att.outputs["Alpha"]
    hot = b.math("MULTIPLY", rng(lava_m, 0.15, 0.6), b.math("ADD", crack, rng(lava_m, 0.75, 1.0)), clamp=True)
    col = b.mix(rng(lava_m, 0.05, 0.4), col, (0.03, 0.025, 0.02, 1))
    rough = b.mix(rng(lava_m, 0.05, 0.4), rough, 0.6, dtype="FLOAT")
    pbr.finish(b, col, rough, nor, None, normal_str=0.9, bump=0)
    bs = b.N["Principled BSDF"]
    bs.inputs["Emission Color"].default_value = (1.0, 0.2, 0.025, 1)     # 진한 주황빨강 (분홍·하얗게 타지 않게)
    b.ln(b.math("MULTIPLY", hot, 5.0), bs.inputs["Emission Strength"])
    return m


def water_mat(name="Water", deep=(0.01, 0.06, 0.07), wave_scale=0.25, rough=0.03):
    """강물: 어두운 청록 + 잔물결 노멀 (EEVEE 레이트레이싱 반사 / Cycles 동일)"""
    m = pbr.new_mat(name)
    b = pbr.NB(m)
    bs = b.N["Principled BSDF"]
    bs.inputs["Base Color"].default_value = deep + (1,)
    bs.inputs["Roughness"].default_value = rough
    bs.inputs["IOR"].default_value = 1.33
    geo = b.n("ShaderNodeNewGeometry")
    tm = b.n("ShaderNodeValue")
    fc = tm.outputs[0].driver_add("default_value")
    fc.driver.expression = "frame/30"
    mp = b.n("ShaderNodeMapping")
    b.ln(geo.outputs["Position"], mp.inputs["Vector"])
    cmb = b.n("ShaderNodeCombineXYZ")
    b.ln(b.math("MULTIPLY", tm.outputs[0], 0.6), cmb.inputs["Y"])
    b.ln(cmb.outputs[0], mp.inputs["Location"])
    n1 = b.n("ShaderNodeTexNoise", i_Scale=wave_scale, i_Detail=6.0, i_Roughness=0.55)
    b.ln(mp.outputs[0], n1.inputs["Vector"])
    bp = b.n("ShaderNodeBump", i_Strength=0.25, i_Distance=0.4)
    b.ln(n1.outputs["Fac"], bp.inputs["Height"])
    b.ln(bp.outputs[0], bs.inputs["Normal"])
    return m


def river_mesh(V, y0=-600, y1=3400, step=4.0, name="River"):
    ys = np.arange(y0, y1, step)
    w = V.river_w / 2 + 6
    verts, faces = [], []
    for i, y in enumerate(ys):
        xc = float(V.river_x(y))
        verts += [(xc - w, y, V.water_z), (xc + w, y, V.water_z)]
        if i:
            k = 2 * i
            faces.append((k - 2, k - 1, k + 1, k))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(water_mat())
    return ob
