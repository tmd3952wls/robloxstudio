"""'불과 물의 마을' 세계 (실사형): 강 골짜기 + 양쪽 마을 + 돌다리 + 화산 + 산맥 + 숲.
build() 한 번으로 전체를 만들고 정보(dict)를 돌려줌. 장면 스크립트는 여기에 카메라·배우만 얹는다.
"""
import math
import os
import random
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildings  # noqa: E402
import fx  # noqa: E402
import look  # noqa: E402
import pbr  # noqa: E402
import terrain  # noqa: E402
import town as TW  # noqa: E402


def line_x(V, off, y0, y1, step=6.0, wob=0.0, ph=0.0):
    """강과 나란한 길. wob: 구불거림 (m) -> 줄 맞춘 느낌 없애기"""
    return [(float(V.river_x(y)) + off + wob * (math.sin(y / 47.0 + ph) + 0.5 * math.sin(y / 19.0 + ph * 2)), y)
            for y in np.arange(y0, y1 + 1e-6, step)]


def build(detail="full", seed=3, log=print):
    t0 = time.time()
    V = terrain.Valley(seed=seed)
    V.heights()
    info = {"V": V}
    ter = terrain.build_mesh(V)
    log(f"terrain {time.time() - t0:.1f}s verts={len(ter.data.vertices)}")
    terrain.river_mesh(V)
    smat = TW.street_mat()
    zf = lambda x, y: float(V.H(x, y)) + 0.07
    y0, y1 = -240, 330
    yb = 40.0                                     # 다리 축
    info["bridge_y"] = yb
    info["towns"] = {}
    rw = V.river_w / 2
    for side, style in ((-1, "fire"), (1, "water")):
        T = TW.Town(V, side, style, seed=seed * 10 + (side > 0))
        # 광장 자리 비우기 (다리 끝)
        pc = (float(V.river_x(yb)) + side * 42, yb)
        T.occ.append((pc[0], pc[1], 21))
        streets = {
            "river": line_x(V, side * (rw + 7), y0, y1),
            "main": line_x(V, side * 66, y0, y1, wob=7, ph=side),
            "back": line_x(V, side * 132, y0 + 30, y1 - 30, wob=12, ph=side * 2.3),
        }
        for k, pts in streets.items():
            TW.strip(pts, 6.5 if k != "back" else 5.0, zf, f"street_{style}_{k}", smat)
        cross_ys = (-190, -110, yb, 120, 200, 280)
        for cy in cross_ys:
            pts = [(float(V.river_x(cy)) + side * d, cy + (0 if cy == yb else 9 * math.sin(d / 33.0 + cy))) for d in np.arange(rw + 7, 200, 6.0)]
            TW.strip(pts, 5.5 if cy != yb else 9.0, zf, f"street_{style}_x{cy}", smat)
        # 집: 강변 줄(강을 봄), 큰길 양쪽, 뒷길 양쪽, 골목
        fs = side          # 길 진행(+y) 기준 왼쪽 법선 = -x. 강 쪽으로 향하려면 정면이 -side*x
        lit = 0.35 if style == "fire" else 0.2
        T.place_row(streets["river"], -side, 3.6, lit_p=lit)
        T.place_row(streets["main"], side, 3.6, lit_p=lit)
        T.place_row(streets["main"], -side, 3.6, lit_p=lit)
        if detail == "full":
            T.place_row(streets["back"], side, 3.0, lit_p=lit)
            T.place_row(streets["back"], -side, 3.0, lit_p=lit)
        TW.quay(V, y0 - 20, y1 + 20, side, V.town_z + 0.1, f"quay_{style}")
        # 뒷마당 나무: 집·길이 없는 빈자리에 활엽수 (마을이 숲과 섞여 자연스럽게)
        rr = np.random.default_rng(seed + (side > 0))
        yard = []
        streets_all = [p for pts in streets.values() for p in pts]
        SA = np.array(streets_all)
        for _ in range(2600):
            yy = rr.uniform(y0 - 40, y1 + 40)
            dd = rr.uniform(rw + 12, 235)
            xx = float(V.river_x(yy)) + side * dd
            if not T.free(xx, yy, 2.2):
                continue
            if np.min(np.hypot(SA[:, 0] - xx, SA[:, 1] - yy)) < 5.5:
                continue
            yard.append((xx, yy, float(V.H(xx, yy)) - 0.2))
            T.occ.append((xx, yy, 2.5))
        if yard:
            TW.scatter(np.array(yard), TW.tree_variants_town(), f"Yard_{style}", rr.uniform(0.45, 0.9, len(yard)), rr.uniform(0, 6.28, len(yard)))
        T.streets = streets
        info["towns"][style] = T
        info[f"plaza_{style}"] = pc
        log(f"town {style}: {len(T.houses)} houses  {time.time() - t0:.1f}s")
    info["bridge"] = TW.bridge(V, yb, V.town_z + 1.4)
    # 광장 장식
    fx.plaza_fire(info["plaza_fire"], float(V.H(*info["plaza_fire"])))
    fx.plaza_fountain(info["plaza_water"], float(V.H(*info["plaza_water"])))
    # 숲
    rng = np.random.default_rng(seed)
    n = 26000 if detail == "full" else 8000
    X = rng.uniform(V.x0 + 50, V.x1 - 50, n * 3)
    Y = rng.uniform(V.y0 + 50, V.y1 - 50, n * 3)
    Z = V.H(X, Y)
    gy, gx = np.gradient(V.Hm, V.cell)
    ix = np.clip(((X - V.x0) / V.cell).astype(int), 0, len(V.xs) - 1)
    iy = np.clip(((Y - V.y0) / V.cell).astype(int), 0, len(V.ys) - 1)
    slope = np.hypot(gx[iy, ix], gy[iy, ix])
    d = np.abs(X - V.river_x(Y))
    vx, vy = V.volcano
    rv = np.hypot(X - vx, Y - vy)
    dens = terrain.fbm(X / 160, Y / 160, 4, seed + 21)
    ok = (slope < 0.75) & (Z > 3) & (Z < 420 + 60 * dens) & (d > 250) & (rv > 1150) & (dens > 0.42)
    near_town = (d > rw + 15) & (d < 250) & ((Y < -280) | (Y > 380)) & (dens > 0.5)
    ok |= near_town & (Z < 60)
    P = np.stack([X[ok], Y[ok], Z[ok] - 0.3], -1)[:n]
    sc = rng.uniform(0.7, 1.5, len(P)) * np.where(P[:, 2] > 250, 0.75, 1.0)
    TW.scatter(P, TW.tree_variants(), "Forest", sc, rng.uniform(0, 6.28, len(P)))
    log(f"forest {len(P)}  {time.time() - t0:.1f}s")
    fx.volcano_smoke(V)
    info["t_build"] = time.time() - t0
    return info
