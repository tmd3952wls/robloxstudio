"""메시 조립 도우미: 재질별로 상자·쐐기·원기둥을 모아서 한 오브젝트로 만든다 (오브젝트 수 절약).
UV 는 '미터' 단위로 각 면에 평면 투영 -> 회전된 판(지붕)에도 텍스처가 면 방향으로 붙는다.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector


class MB:
    def __init__(self):
        self.parts = {}          # mat_name -> (verts, faces, uvs)

    def _p(self, mat):
        return self.parts.setdefault(mat, ([], [], []))

    def poly(self, mat, pts, uv=None):
        v, f, u = self._p(mat)
        i0 = len(v)
        v.extend(pts)
        f.append(tuple(range(i0, i0 + len(pts))))
        if uv is None:
            # 면 평면에 투영 (미터)
            n = (Vector(pts[1]) - Vector(pts[0])).cross(Vector(pts[2]) - Vector(pts[0]))
            n = n.normalized() if n.length > 1e-9 else Vector((0, 0, 1))
            up = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((0, 1, 0))
            ax = up.cross(n).normalized()
            ay = n.cross(ax).normalized()
            uv = [(Vector(p).dot(ax), Vector(p).dot(ay)) for p in pts]
        u.append(uv)

    def box(self, mat, c, s, M=None, uvoff=(0.0, 0.0)):
        """c 중심, s 크기, M 회전(3x3), 각 면 UV=면 로컬 미터 + uvoff(텍스처 반복 티 안 나게)"""
        M = M or Matrix.Identity(3)
        c = Vector(c)
        hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
        P = lambda x, y, z: tuple(c + M @ Vector((x, y, z)))
        ox, oy = uvoff
        faces = [
            ((-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz), "xz"),   # -y
            ((hx, hy, -hz), (-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz), "xz"),       # +y
            ((hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz), "yz"),       # +x
            ((-hx, hy, -hz), (-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz), "yz"),   # -x
            ((-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz), "xy"),       # +z
            ((-hx, hy, -hz), (hx, hy, -hz), (hx, -hy, -hz), (-hx, -hy, -hz), "xy"),   # -z
        ]
        flip = M.determinant() < 0          # 거울 좌표계면 면 방향 뒤집기
        for a, b, cc, d, pl in faces:
            q = [d, cc, b, a] if flip else [a, b, cc, d]
            if pl == "xz":
                uv = [(p[0] + ox + (p[1] * 0), p[2] + oy) for p in q]
            elif pl == "yz":
                uv = [(p[1] + ox, p[2] + oy) for p in q]
            else:
                uv = [(p[0] + ox, p[1] + oy) for p in q]
            self.poly(mat, [P(*p) for p in q], uv)

    def prism(self, mat, base_pts, h_vec):
        """바닥 다각형을 h_vec 만큼 밀어낸 기둥 (박공벽 삼각형 등)"""
        hv = Vector(h_vec)
        top = [tuple(Vector(p) + hv) for p in base_pts]
        n = len(base_pts)
        self.poly(mat, list(reversed(base_pts)))
        self.poly(mat, top)
        for i in range(n):
            j = (i + 1) % n
            self.poly(mat, [base_pts[i], base_pts[j], top[j], top[i]])

    def cyl(self, mat, c, r, h, segs=12, axis="z", r2=None):
        r2 = r if r2 is None else r2
        c = Vector(c)
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            ring.append((math.cos(a), math.sin(a)))
        def P(x, y, z):
            if axis == "z": return tuple(c + Vector((x, y, z)))
            if axis == "x": return tuple(c + Vector((z, x, y)))
            return tuple(c + Vector((x, z, y)))
        bot = [P(r * x, r * y, -h / 2) for x, y in ring]
        top = [P(r2 * x, r2 * y, h / 2) for x, y in ring]
        self.poly(mat, list(reversed(bot)))
        self.poly(mat, top)
        for i in range(segs):
            j = (i + 1) % segs
            L = 2 * math.pi * r
            self.poly(mat, [bot[i], bot[j], top[j], top[i]],
                      [(L * i / segs, 0), (L * (i + 1) / segs, 0), (L * (i + 1) / segs, h), (L * i / segs, h)])

    def build(self, name, mats, collection=None, bevel=0.0, smooth_angle=None):
        """mats: name->bpy material. 재질 슬롯별 하나의 메시. bevel>0 이면 모서리 깎기 모디파이어 (하이라이트로 실사감)."""
        me = bpy.data.meshes.new(name)
        verts, faces, uvs, mids = [], [], [], []
        order = list(self.parts)
        for mi, m in enumerate(order):
            v, f, u = self.parts[m]
            off = len(verts)
            verts.extend(v)
            for fi, face in enumerate(f):
                faces.append(tuple(i + off for i in face))
                uvs.append(u[fi])
                mids.append(mi)
        me.from_pydata(verts, [], faces)
        uvl = me.uv_layers.new(name="UVMap")
        k = 0
        for p, uvf in zip(me.polygons, uvs):
            for li, uv in zip(p.loop_indices, uvf):
                uvl.data[li].uv = uv
        for m in order:
            me.materials.append(mats[m])
        me.polygons.foreach_set("material_index", mids)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bm.to_mesh(me)
        bm.free()
        me.update()
        ob = bpy.data.objects.new(name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        if bevel > 0:
            md = ob.modifiers.new("Bevel", "BEVEL")
            md.width, md.segments, md.limit_method = bevel, 2, "ANGLE"
            md.harden_normals = True
        return ob


def rotz(a):
    return Matrix.Rotation(a, 3, "Z")


def rotx(a):
    return Matrix.Rotation(a, 3, "X")


def roty(a):
    return Matrix.Rotation(a, 3, "Y")
