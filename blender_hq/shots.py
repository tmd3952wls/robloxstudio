"""수명을 파는 시장 — 샷 계획 (로블록스 좌표: x 동서, y 위, z 남북. 거리 단위 스터드).

배우 yaw: 바라보는 방향. 0 = +Z(정문 쪽), 90 = +X, 180 = -Z(시계탑 쪽), -90 = -X
각 샷: lines=(첫 줄, 끝 줄) 대사 번호, light, cam=[(t, 위치, 바라볼 곳, 가로화각)], actors={이름: {...}}
"""
import json
import math
import os

D = os.path.dirname(os.path.abspath(__file__))
TIMING = json.load(open(os.path.join(D, "..", "audio", "timing.json"), encoding="utf-8"))
LS = {e["n"]: e["start"] for e in TIMING}
TOTAL = TIMING[-1]["start"] + TIMING[-1]["dur"] + 0.25

INSTANCES = {"TownA2": "TownA", "TownB2": "TownB", "TownC2": "TownC", "TownD2": "TownD", "TownE2": "TownE",
             "TownF2": "TownF", "TownA3": "TownA", "TownB3": "TownB", "TownC3": "TownC", "TownD3": "TownD"}

# ------------------------------------------------------------------ 배우 치수 (export.txt 에서)
RIG = {}
for line in open(os.path.join(D, "export.txt"), encoding="utf-8").read().split("\n#\n")[3][2:].split("\n"):
    f = line.split("|")
    if f[0] == "R":
        RIG[f[1]] = {"sh": tuple(map(float, f[2].split(","))), "neck": tuple(map(float, f[6].split(",")))}
    elif f[0] == "p" and f[3] in ("LeftLowerArm", "Head"):
        RIG[f[1]][f[3]] = tuple(map(float, f[6].split(",")))


def base(n):
    return INSTANCES.get(n, n)


def rotY(v, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    x, y, z = v
    return (x * c + z * s, y, -x * s + z * c)


def to_world(x, y0, z, yaw, local, scale=1.0):
    lx, ly, lz = rotY(tuple(v * scale for v in local), yaw - 180)
    return (x + lx, y0 + ly, z + lz)


def fwd(yaw):
    return (math.sin(math.radians(yaw)), math.cos(math.radians(yaw)))


def left(yaw):
    return (math.cos(math.radians(yaw)), -math.sin(math.radians(yaw)))


def head(n, x, z, yaw, y0=0.4, scale=1.0):
    return to_world(x, y0, z, yaw, RIG[base(n)]["Head"], scale)


def forearm(n, x, z, yaw, y0=0.4, raise_=0.0, inward=0.0, scale=1.0):
    """왼팔 아래팔 중심 (팔을 앞으로 raise_ 도 들고 안쪽으로 inward 도 돌린 상태)"""
    r = RIG[base(n)]
    sh, la = r["sh"], r["LeftLowerArm"]
    v = (la[0] - sh[0], la[1] - sh[1], la[2] - sh[2])
    th = math.radians(raise_)
    v = (v[0], v[1] * math.cos(th) - v[2] * math.sin(th), v[1] * math.sin(th) + v[2] * math.cos(th))
    v = rotY(v, -inward)
    local = (sh[0] + v[0], sh[1] + v[1], sh[2] + v[2])
    return to_world(x, y0, z, yaw, local, scale)


def add(p, d):
    return tuple(a + b for a, b in zip(p, d))


def front_cam(target, yaw, dist, dh=0.0, side=0.0, fov=36):
    """대상 앞쪽(yaw 방향)에서 side 도 돌아간 곳"""
    fx, fz = fwd(yaw + side)
    return (target[0] + fx * dist, target[1] + dh, target[2] + fz * dist)


def arm_cam(n, x, z, yaw, y0=0.4, raise_=80, inward=0, dist=2.2, back=0.0, dh=0.25, scale=1.0):
    """왼팔 바깥면(숫자)을 보는 카메라 위치, 바라볼 곳"""
    fa = forearm(n, x, z, yaw, y0, raise_, inward, scale)
    lx, lz = left(yaw - inward * 0.7)
    fx, fz = fwd(yaw)
    pos = (fa[0] + lx * dist - fx * back, fa[1] + dh, fa[2] + lz * dist - fz * back)
    return pos, fa


def push(p0, l0, fov0, dur, amt=0.18, fov1=None, rise=0.0, side=(0, 0)):
    """p0 에서 l0 쪽으로 amt 비율만큼 다가가는 카메라 키"""
    p1 = tuple(p0[i] + (l0[i] - p0[i]) * amt for i in range(3))
    p1 = (p1[0] + side[0], p1[1] + rise, p1[2] + side[1])
    return [(0, p0, l0, fov0), (dur, p1, l0, fov1 or fov0)]


def num_live(v, rate=-1.0):
    return {"v": v, "rate": rate}


def num_keys(keys, ease="lin", glow=None, tick=False):
    d = {"keys": keys, "ease": ease}
    if glow:
        d["glow"] = glow
    return d


RICH_TEXT = "8,760,000:00:00\n4,380,000:00:00\n2,190,000:00:00"
LONG_TEXT = "52,560:00:00\n43,800:00:00\n35,040:00:00"
FULL_TEXT = "9,999:59:59\n8,640:00:00\n7,200:00:00"

# 위치 상수
STREET_Y, WALK_Y, ROOM_Y = 0.4, 0.6, 0.0
BED = {"x": 476.0, "y": 3.55, "pillow_z": 4.6}
HARU_LIE_Z = BED["pillow_z"] + 0.3 - RIG["Haru"]["Head"][1]       # 누운 하루 발 위치 z
TOWER = (0.0, 71.6, -257.6)
SHOP = (-12.2, -62.0)        # 시계 수리점 문 앞

S = []


def shot(lines, light="day", **kw):
    kw["lines"] = lines
    kw["light"] = light
    kw.setdefault("actors", {})
    S.append(kw)


def crowd(names, x0, z0, dx, dz, yaw, face="기본 미소", y=STREET_Y, extra=None):
    out = {}
    for i, n in enumerate(names):
        a = {"x": x0 + dx * i + (0.6 if i % 2 else -0.4), "z": z0 + dz * i + (0.5 if i % 3 == 0 else -0.3), "yaw": yaw + (i % 3 - 1) * 12, "face": face, "y": y}
        if extra:
            a.update(extra)
        out[n] = a
    return out


# ================================================================== 1. 도입: 팔의 숫자
# 1-2  이 마을 사람들 팔에는 숫자가 적혀 있어. 일 초에 하나씩 줄어드는 남은 수명이야.
#   하늘 높이 시장 위에서 출발한 카메라가 북적이는 거리 위를 날아 내려와 하루에게 다가가고,
#   하루가 카메라를 보며 팔을 들어 소매를 걷는 순간 팔의 시간이 빛나며 드러난다. 끝은 팔 시간 클로즈업.
def _cr(p0, p1, p2, p3, u):
    return tuple(0.5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u ** 3)
                 for a, b, c, d in zip(p0, p1, p2, p3))


def spline_cam(keys, dur, step=1 / 30.0, warp=2.0):
    """(위치, 바라볼곳, 화각) 제어점들을 부드럽게 잇는 카메라 키. warp>1 이면 처음 빠르고 끝에서 느려짐."""
    out = []
    n = len(keys) - 1
    t = 0.0
    while t <= dur + 1e-6:
        x = t / dur
        u = 1 - (1 - x) ** warp
        f = min(u * n, n - 1e-6)
        i = int(f)
        lu = f - i
        P = [keys[max(0, min(n, j))] for j in (i - 1, i, i + 1, i + 2)]
        pos = _cr(*(k[0] for k in P), lu)
        look = _cr(*(k[1] for k in P), lu)
        fov = P[1][2] + (P[2][2] - P[1][2]) * lu
        out.append((round(t, 4), pos, look, fov))
        t += step
    return out


hx0, hz0, hyaw0 = 0.0, 14.0, 0.0
hhead0 = head("Haru", hx0, hz0, hyaw0)
_fa0 = forearm("Haru", hx0, hz0, hyaw0, raise_=80)
_pA, _ = arm_cam("Haru", hx0, hz0, hyaw0, raise_=80, dist=2.7, dh=0.15)
_pB, _ = arm_cam("Haru", hx0, hz0, hyaw0, raise_=80, dist=2.25, dh=0.1)
_open_keys = [((0.0, 32.0, 62.0), (0.0, 6.0, hz0 - 20), 52),     # 정문 안쪽 시장 하늘 위, 시계탑 쪽을 내려다봄
              ((0.3, 15.0, 44.0), add(hhead0, (0, 0.5, 0)), 46),   # 깃발 줄 아래로 날아 내려옴
              ((1.2, 6.2, 27.0), add(hhead0, (0, -0.4, 0)), 40),   # 사람들 사이 눈높이, 하루 정면
              ((2.9, 4.4, 19.5), add(_fa0, (0, 0.6, 0)), 34),      # 하루 왼쪽으로 돌며 팔 쪽으로
              (_pA, _fa0, 30),
              (_pB, _fa0, 27)]
shot((1, 2), fstop=4.0, ease="lin", cam=spline_cam(_open_keys, 4.45, warp=1.6),
     actors={"Haru": {"x": hx0, "z": hz0, "yaw": hyaw0, "bare": [(0, False), (1.55, True)],
                      "num": {"v": 13 * 3600 + 27 * 60 + 41.5, "rate": -1.0, "glow": [(1.55, 2.5)]},
                      "acts": [("look", -6, -12, 0.2, 0.7), ("look", 6, 12, 1.0, 1.3), ("arm", "L", 80, 0, 1.15, 0.45),
                               ("expr", [(0, "기본 미소"), (1.1, "장난기"), (2.6, "기본 미소")])]}})
# 3  숫자가 영이 되는 순간, 그 사람은 멈춰.  (노인 TownE: 0:00:02 -> 0:00:00, 멈춤)
x, z, yaw = -4.0, -20.0, 160.0
hp = head("TownE", x, z, yaw)
fa = forearm("TownE", x, z, yaw, raise_=40)
p3, l3 = arm_cam("TownE", x, z, yaw, raise_=40, dist=2.4)
shot((3, 3), cam=[(0, p3, l3, 32), (1.2, add(p3, (0, 0, 0)), l3, 30), (2.17, front_cam(hp, yaw, 6.0, 0.4, -20), hp, 40)],
     ease="out", temp=5800, fstop=2.4,
     actors={"TownE": {"x": x, "z": z, "yaw": yaw, "bare": True, "acts": [("arm", "L", 40, 0, -1, 0.1), ("freeze", 2.05), ("expr", [(0, "무표정"), (2.05, "무표정|closed")])],
                       "num": {"keys": [(0, 2.9), (2.05, 0.0)], "ease": "lin"}, "tint": (0.25, 0.25, 0.27)},
             "TownB2": {"x": x + 3.5, "z": z - 3.0, "yaw": -60, "face": "충격", "acts": [("jerk", 1.9, 1.2)]}})
# 4-5  그리고 이 마을에선, 그 숫자를 돈 주고 사고팔 수 있어.  (시장 전경, 크레인 다운)
market = {**crowd(["TownA", "TownB", "TownC", "TownD"], -6, 30, 4, -6, 180),
          **crowd(["TownE2", "TownF", "TownA2", "TownB3"], 5, 10, -3, -7, 0),
          "Baker": {"x": -16.0, "z": 34.0, "yaw": 90, "y": WALK_Y, "face": "활짝 웃음"},
          "Soup": {"x": -16.0, "z": 6.0, "yaw": 90, "y": WALK_Y},
          "Umbrella": {"x": 16.0, "z": -8.0, "yaw": -90, "y": WALK_Y},
          "Flower": {"x": 16.0, "z": 22.0, "yaw": -90, "y": WALK_Y, "face": "활짝 웃음"}}
for i, n in enumerate(["TownA", "TownB", "TownC", "TownD", "TownE2", "TownF", "TownA2", "TownB3"]):
    mx, mz = market[n]["x"], market[n]["z"]
    sgn = 1 if i < 4 else -1
    market[n]["path"] = [(0, mx, mz, market[n]["yaw"]), (3.0, mx, mz - sgn * 4.2, market[n]["yaw"])]
shot((4, 5), nodyn=True, cam=[(0, (0, 46, 80), (0, 4, -40), 50), (2.85, (0, 18, 40), (0, 6, -40), 46)], ease="smooth", actors=market)
# 6  빵 하나에 한 시간.
tag = (-13.5, 7.0, 34.0)
shot((6, 6), cam=push((-4.5, 6.2, 37.5), tag, 40, 1.05, amt=0.22), fstop=4.0,
     actors={"Baker": {"x": -16.3, "z": 32.5, "yaw": 70, "y": WALK_Y, "face": "활짝 웃음", "acts": [("wave", "R", 0.1, 2)]}})
# 7  따뜻한 수프는 세 시간.
tag = (-13.5, 7.0, 6.0)
shot((7, 7), cam=push((-4.0, 6.0, 2.0), tag, 40, 1.35, amt=0.22, side=(0, 1.0)), fstop=4.0,
     actors={"Soup": {"x": -16.3, "z": 7.5, "yaw": 110, "y": WALK_Y, "face": "기본 미소", "acts": [("nod", 10, 0.3, 0.5)]}})
# 8  비 오는 날 우산은, 하루.
tag = (13.5, 7.0, -8.0)
shot((8, 8), cam=push((4.2, 5.8, -4.0), tag, 40, 1.35, amt=0.22, side=(0, -1.0)), fstop=4.0,
     actors={"Umbrella": {"x": 16.3, "z": -9.5, "yaw": -70, "y": WALK_Y, "face": "장난기", "acts": [("arm", "R", 60, 40, 0.0, 0.3)]}})
# 9  손목을 맞대면, 숫자가 건너가.  (손님 TownA <-> 빵집 아저씨)
ax_, az_ = -1.0, 26.0
shot((9, 9), cam=None, fstop=2.4, actors={})
S[-1]["actors"] = {
    "TownA": {"x": ax_, "z": az_, "yaw": -90, "bare": True, "y": STREET_Y, "acts": [("arm", "L", 84, 0, 0.0, 0.35, None, 26)],
              "num": num_keys([(0, 52 * 3600 + 600), (0.7, 52 * 3600 + 600), (1.3, 51 * 3600 + 600)], "smooth", glow=[(0.6, 1.3)]), "face": "기본 미소"},
    "Baker": {"x": ax_ - 4.3, "z": az_, "yaw": 90, "bare": True, "y": STREET_Y, "acts": [("arm", "L", 84, 0, 0.0, 0.35, None, 26)],
              "num": num_keys([(0, 12 * 3600), (0.7, 12 * 3600), (1.3, 13 * 3600)], "smooth", glow=[(0.6, 1.3)]), "face": "활짝 웃음"},
}
mid = (ax_ - 2.15, 3.55, az_)
S[-1]["cam"] = [(0, (ax_ - 2.0, 4.8, az_ + 5.0), mid, 40), (1.86, (ax_ - 2.1, 4.4, az_ + 4.0), mid, 36)]
S[-1]["touchglow"] = (0.5, 1.4, "TownA", 40)
# 10  부자들 팔엔, 소매 끝까지 숫자가 이어져 있고,
x, z, yaw = 2.0, -14.0, 0.0
p, l = arm_cam("Rich", x, z, yaw, raise_=80, dist=2.5, back=0.4)
hp = head("Rich", x, z, yaw)
shot((10, 10), cam=[(0, p, l, 34), (1.2, add(p, (0, 0.1, 0.6)), add(l, (0, 0, 0.3)), 30), (2.47, front_cam(hp, yaw, 5.5, -1.0, -25), hp, 40)],
     ease="smooth", fstop=2.6,
     actors={"Rich": {"x": x, "z": z, "yaw": yaw, "bare": True, "acts": [("arm", "L", 80, 0, -1, 0.1, 1.6), ("expr", [(0, "뿌듯")])], "num": {"text": RICH_TEXT, "size": 0.62}},
             **crowd(["TownB", "TownD"], -5, -6, 9, 1, 160, "놀람")})
# 11  가난한 사람들은 한 시간씩 팔아서 버티지.  (시간 삽니다 노점, TownD 가 판다)
x, z = 10.0, -30.0
shot((11, 11), fstop=2.8,
     cam=[(0, (x - 3.2, 4.6, z + 5.0), (x + 0.2, 3.6, z), 40), (2.23, (x - 2.8, 4.2, z + 4.0), (x + 0.2, 3.6, z), 36)],
     actors={"TownD": {"x": x - 2.0, "z": z, "yaw": 90, "bare": True, "acts": [("arm", "L", 84, 0, 0.2, 0.35, None, 26), ("expr", [(0, "슬픔")])],
                       "num": num_keys([(0, 3 * 3600 + 120), (0.9, 3 * 3600 + 120), (1.6, 2 * 3600 + 120)], "smooth", glow=[(0.8, 1.6)])},
             "TownB": {"x": x + 2.3, "z": z, "yaw": -90, "bare": True, "y": STREET_Y, "acts": [("arm", "L", 84, 0, 0.2, 0.35, None, 26)], "face": "무표정"}},
     touchglow=(0.8, 1.7, "TownD", 30))
# 12  그래서 다들 소매를 내리고 다녀.  (거리, 모두 소매 내림)
walkers = {}
for i, n in enumerate(["TownA", "TownB", "TownC", "TownD", "TownE", "TownF", "TownA2", "TownC2"]):
    sx = -6 + (i % 4) * 4
    sz = 18 - (i // 4) * 8
    d = 1 if i % 2 == 0 else -1
    walkers[n] = {"path": [(0, sx, sz, 0 if d > 0 else 180), (1.6, sx, sz + d * 5.2, 0 if d > 0 else 180)], "face": "무표정", "y": STREET_Y}
shot((12, 12), cam=[(0, (-3, 4.2, 34), (1, 3.4, 10), 42), (1.57, (-2.2, 4.0, 31), (1, 3.4, 10), 40)], actors=walkers, fstop=5.6)
# 13  남의 숫자를 보는 건, 큰 실례거든.  (아이가 엿보다 혼남)
x, z = -2.0, 2.0
shot((13, 13), fstop=2.8,
     cam=[(0, (x + 1.3, 4.6, z - 7.5), (x + 1.2, 3.4, z), 40), (2.08, (x + 1.3, 4.4, z - 6.5), (x + 1.2, 3.4, z), 38)],
     actors={"TownC": {"x": x, "z": z, "yaw": 90, "bare": [(0, True), (1.0, False)], "num": num_live(18 * 3600), "acts": [("arm", "L", 40, 0, -1, 0.1, 0.8), ("expr", [(0, "무표정"), (0.9, "짜증")]), ("look", -10, 25, 0.8, 1.1)]},
             "TownF": {"x": x + 3.5, "z": z + 0.2, "yaw": -95, "acts": [("lean", 9, 0, 0.4), ("lean", -9, 1.0, 1.3), ("expr", [(0, "장난기"), (1.0, "당황")]), ("look", -18, 0, 0, 0.3)]}})

# ================================================================== 2. 하루
# 14  이건 하루야.
hx, hz, hyaw = 0.0, -4.0, 20.0
hp = head("Haru", hx, hz, hyaw)
shot((14, 14), cam=[(0, front_cam(hp, hyaw, 9.0, -1.0), hp, 40), (0.71, front_cam(hp, hyaw, 4.4, -0.3), hp, 36)], ease="out", fstop=2.8,
     actors={"Haru": {"x": hx, "z": hz, "yaw": hyaw, "face": "활짝 웃음", "acts": [("wave", "R", 0.05, 2)]},
             **crowd(["TownA2", "TownD"], -7, -14, 13, -2, 30)})
# 15-16  하루의 팔엔, 이십사 시간이 적혀 있어. 딱 하루.
p, l = arm_cam("Haru", hx, hz, hyaw, raise_=82, dist=2.0)
shot((15, 16), cam=[(0, add(p, (0.6, 0.3, 0.8)), l, 36), (2.75, add(p, (-0.1, 0.0, 0.0)), l, 28)], ease="smooth", fstop=2.0,
     actors={"Haru": {"x": hx, "z": hz, "yaw": hyaw, "bare": True, "num": {"text": "24:00:00"}, "acts": [("arm", "L", 82, 0, -1, 0.1), ("expr", [(0, "기본 미소"), (2.2, "뿌듯")])]}})
# 17-18  이상한 건, 자정만 지나면 숫자가 다시 이십사 시간으로 돌아온다는 거야.  (밤 다락방, 0:00:02 -> 24:00:00)
haru_lie = {"x": BED["x"], "z": HARU_LIE_Z, "yaw": 180, "y": BED["y"], "lie": True, "bare": True}
fa = forearm("Haru", 0, 0, 180, 0, 0)          # 서 있을 때 기준 -> 누운 자세로 변환
fa_lie = (BED["x"] + fa[0], BED["y"] + 0.0, HARU_LIE_Z + fa[1])
shot((17, 18), "night", fstop=2.2,
     cam=[(0, (470.5, 7.5, -9.0), (475.0, 3.4, 1.5), 46), (1.4, (472.0, 5.8, fa_lie[2] - 3.0), fa_lie, 34), (3.77, (472.9, 4.5, fa_lie[2] - 1.0), fa_lie, 26)],
     actors={"Haru": {**haru_lie, "face": "잠|closed", "num": num_keys([(0, 4.0), (2.15, 0.0), (2.2, 24 * 3600), (3.8, 24 * 3600 - 1)], "lin", glow=[(2.15, 2.9)])}},
     touchglow=(2.1, 3.0, "Haru", 25))
# 19  태어나서 지금까지, 매일 밤.  (밤 시계탑, 바늘 자정)
shot((19, 19), "night", cam=[(0, (0, 30, -200), TOWER, 30), (1.8, (0, 38, -214), TOWER, 28)], fstop=11)
# 20  하루는 그게 원래 그런 줄 알았어.  (낮, 하루가 신나게 걷는다)
shot((20, 20), fstop=4.0,
     cam=[(0, (2.0, 4.4, -19.0), (0.0, 3.8, -7.0), 42), (1.78, (1.8, 4.3, -20.5), (0.0, 3.8, -12.0), 40)],
     actors={"Haru": {"path": [(0, 0.0, -6.0, 180), (1.78, 0.0, -13.5, 180)], "face": "활짝 웃음", "acts": [("bounce", 0.15, 0.2, 3)]},
             **crowd(["TownA", "TownE"], -7, -16, 14, 0, 0)})
# 21  그런데 그 소문이 시장에 퍼졌어.  (귓속말)
x, z = 8.0, -40.0
shot((21, 21), fstop=2.8,
     cam=[(0, (x + 0.8, 4.8, z - 6.5), (x + 0.8, 4.0, z), 40), (1.68, (x + 0.8, 4.6, z - 5.6), (x + 0.8, 4.0, z), 38)],
     actors={"TownB": {"x": x, "z": z, "yaw": 145, "face": "놀람", "acts": [("look", 0, -10, 0, 0.3)]},
             "TownD": {"x": x + 1.7, "z": z - 0.2, "yaw": 215, "face": "의심", "acts": [("lean", 10, 0, 0.3)]},
             "TownA3": {"x": x - 1.5, "z": z - 4, "yaw": 40, "face": "의심"}})
# 22  숫자가 다시 차오르는 아이가 있다.
x, z = -6.0, -48.0
shot((22, 22), fstop=2.8,
     cam=[(0, (x + 3.0, 4.6, z + 6.5), (x, 4.0, z), 42), (1.73, (x + 2.6, 4.5, z + 5.5), (x, 4.0, z), 40)],
     actors={"TownC": {"x": x, "z": z, "yaw": 40, "face": "충격", "acts": [("jerk", 0.4, 1.0)]},
             "TownE": {"x": x - 1.8, "z": z + 1.3, "yaw": 70, "face": "놀람"},
             "TownF2": {"x": x + 1.6, "z": z - 1.0, "yaw": 10, "face": "신남", "acts": [("bounce", 0.2, 0.3, 2)]}})
# 23  사람들은 하루를 보면, 손목부터 쳐다봤지.
lookers = {}
for i, (n, lx_, lz_) in enumerate([("TownA", -6, -60), ("TownB", 7, -62), ("TownD", -7, -68), ("TownE2", 6, -70), ("TownC2", -5, -76), ("TownB2", 7, -77)]):
    ang = math.degrees(math.atan2(0 - lx_, -70 + 2.0 * 1.5 - lz_))
    lookers[n] = {"x": lx_, "z": lz_, "yaw": ang, "face": "의심" if i % 2 else "놀람", "acts": [("look", -22, 0, 0.3 + i * 0.12, 0.6 + i * 0.12)]}
shot((23, 23), fstop=5.6,
     cam=[(0, (0.8, 4.6, -84), (0, 3.6, -66), 46), (2.32, (0.8, 4.4, -82), (0, 3.6, -68), 44)],
     actors={"Haru": {"path": [(0, 0, -64, 180), (2.32, 0, -69, 180)], "face": "당황", "acts": [("look", -10, -20, 0.8, 1.1)]}, **lookers})

# ================================================================== 3. 부자
# 24  시장에서 제일 큰 부자가 찾아왔어.  (낮은 앵글, 부자가 걸어옴)
shot((24, 24), fstop=5.0,
     cam=[(0, (1.5, 1.6, -96), (0, 6.5, -86), 48), (1.86, (1.4, 1.8, -97.5), (0, 6.0, -90), 44)],
     actors={"Rich": {"path": [(0, 0, -80, 180), (1.86, 0, -88, 180)], "face": "장난기"},
             "TownA": {"x": -4, "z": -78, "yaw": 160, "face": "놀람"}, "TownD2": {"x": 4.5, "z": -79, "yaw": 200, "face": "놀람"}})
# 이후 부자와 하루 대화 위치
rx, rz, ryaw = 0.0, -96.0, 180.0
hx, hz, hyaw = 0.0, -101.0, 0.0
rhp = head("Rich", rx, rz, ryaw)
hhp = head("Haru", hx, hz, hyaw)
pair = lambda rich_face, haru_face, racts=(), hacts=(), rbare=False: {
    "Rich": {"x": rx, "z": rz, "yaw": ryaw, "face": rich_face, "acts": list(racts), "bare": rbare, "num": {"text": RICH_TEXT, "size": 0.62}},
    "Haru": {"x": hx, "z": hz, "yaw": hyaw, "face": haru_face, "acts": list(hacts)}}
# 25  네 시간을 전부 사겠다.
shot((25, 25), fstop=2.4, cam=push(front_cam(rhp, ryaw, 4.6, -0.6, 22), rhp, 36, 1.38, amt=0.12),
     actors=pair("장난기", "놀람", racts=[("arm", "R", 70, 10, 0.1, 0.3)]))
# 26  대신, 백 년을 주지.  (부자가 소매를 걷고 숫자 팔을 내민다)
p, l = arm_cam("Rich", rx, rz, ryaw, raise_=82, dist=2.6, back=0.3)
shot((26, 26), fstop=2.4, cam=[(0, add(p, (0, 0.2, -0.5)), l, 36), (1.25, p, l, 32)],
     actors=pair("뿌듯", "놀람", racts=[("arm", "L", 82, 0, -1, 0.1)], rbare=True))
# 27  하루는 이상했어.
shot((27, 27), fstop=2.2, cam=push(front_cam(hhp, hyaw, 3.6, 0.4, -15), hhp, 32, 0.98, amt=0.1),
     actors=pair("장난기", "의심", hacts=[("tilt", 12, 0.1, 0.5)]))
# 28  왜 겨우 하루를, 백 년이나 주고 사려는 걸까.  (투샷)
shot((28, 28), fstop=4.0, cam=[(0, (9.5, 4.8, -98.5), (0, 3.9, -98.5), 52), (2.42, (8.5, 4.7, -98.5), (0, 3.9, -98.5), 50)],
     actors=pair("장난기", "생각 중", hacts=[("look", 8, 0, 0.6, 1.0)]))
# 29  부자가 웃으며 말했어.
shot((29, 29), fstop=2.4, cam=push(front_cam(rhp, ryaw, 4.0, -0.4, 18), rhp, 34, 1.18, amt=0.1),
     actors=pair("폭소", "의심", racts=[("bounce", 0.12, 0.1, 3), ("look", 12, 0, 0.0, 0.2)]))
# 30  매일 밤, 누군가 너한테 시간을 넣고 있다.  (하루 어깨 너머)
shot((30, 30), fstop=2.8,
     cam=[(0, add(hhp, (1.6, 0.5, -2.8)), rhp, 38), (2.36, add(hhp, (1.3, 0.4, -2.2)), rhp, 34)],
     actors=pair("장난기", "당황", racts=[("lean", 12, 0.2, 0.6), ("arm", "R", 60, 0, 0.6, 0.3)]))
# 31  그 사람만 찾으면, 이 마을의 시간을 전부 가질 수 있다고.  (부자 뒤에서 시계탑을 향해)
shot((31, 31), fstop=8.0, nodyn=True,
     # 시장 사람들 전체가 보이도록 높고 먼 뒤쪽에서 시작해 부자 등 뒤로 날아 들어감 (드론)
     cam=spline_cam([((rx + 7.0, 22.0, rz + 34.0), (0, 14, -120), 52),
                     ((rx + 5.0, 14.0, rz + 20.0), (0, 22, -170), 48),
                     ((rx + 3.0, 9.5, rz + 11.0), (0, 32, -220), 43),
                     ((rx + 2.0, 9.0, rz + 9.0), (0, 40, -240), 40)], 3.06, warp=1.7),
     ease="lin",
     actors={"Rich": {"x": rx, "z": rz, "yaw": 180, "face": "장난기", "acts": [("arms_up", 1.2)]},
             "Haru": {"x": -3.5, "z": rz + 3.5, "yaw": 160, "face": "생각 중"}})

# ================================================================== 4. 자정
# 32  그날 밤, 하루는 자는 척하며 기다렸어.
hp_lie = (BED["x"], BED["y"] + 0.75, BED["pillow_z"] + 0.3)
shot((32, 32), "night", fstop=2.4,
     cam=[(0, (472.0, 6.5, -4.0), hp_lie, 42), (2.2, (473.5, 5.6, 0.5), hp_lie, 34)],
     actors={"Haru": {**haru_lie, "bare": False, "acts": [("expr", [(0, "잠|closed"), (0.9, "의심"), (1.5, "잠|closed")])]}})
# 33  시계탑이 열두 번 울렸어.
shot((33, 33), "night", cam=[(0, (0, 40, -215), TOWER, 34), (1.38, (0, 46, -228), TOWER, 26)], fstop=11, shake=3.0)
# 34  문이 아주 조용히 열리고,
shot((34, 34), "night", fstop=4.0,
     cam=[(0, (468.5, 5.0, 2.5), (460.5, 3.8, -4.8), 40), (1.33, (467.5, 4.8, 1.8), (460.5, 3.8, -4.8), 38)],
     actors={"Grandma": {"path": [(0, 459.4, -4.8, 90), (1.33, 461.0, -4.4, 70)], "y": ROOM_Y, "face": "무표정"}})
# 35  차가운 손 하나가, 하루의 손목에 닿았어.
gx, gz = 472.2, fa_lie[2] + 2.2
shot((35, 35), "night", fstop=2.0,
     cam=[(0, (469.5, 6.8, fa_lie[2] - 4.5), (474.0, 3.6, fa_lie[2] + 0.5), 42), (2.26, (470.2, 6.2, fa_lie[2] - 3.5), (474.0, 3.6, fa_lie[2] + 0.5), 38)],
     actors={"Haru": {**haru_lie, "bare": True, "face": "잠|closed", "num": {"text": "0:00:00"}},
             "Grandma": {"x": gx, "z": gz, "yaw": 90, "y": ROOM_Y, "face": "무표정", "acts": [("arm", "L", 82, 0, 0.3, 0.9, None, -25)]}})
# 36-37  팔이 따뜻해지면서, 숫자가 다시 올라가기 시작했어.
shot((36, 37), "night", fstop=2.0,
     cam=[(0, (471.2, 5.4, fa_lie[2] - 0.3), fa_lie, 27), (2.79, (471.6, 5.1, fa_lie[2] - 0.2), fa_lie, 23)],
     actors={"Haru": {**haru_lie, "bare": True, "face": "잠|closed",
                      "num": num_keys([(0, 0), (0.3, 0), (2.7, 24 * 3600)], "smooth", glow=[(0.2, 2.9)])}},
     touchglow=(0.1, 2.9, "Haru", 45))
# 38  하루는 눈을 떴어.
shot((38, 38), "night", fstop=2.0,
     cam=[(0, (BED["x"] - 0.2, 6.8, hp_lie[2] - 2.0), hp_lie, 34), (1.06, (BED["x"] - 0.2, 6.2, hp_lie[2] - 1.5), hp_lie, 30)],
     actors={"Haru": {**haru_lie, "bare": True, "num": {"text": "24:00:00"}, "acts": [("expr", [(0, "잠|closed"), (0.35, "놀람")]), ("jerk", 0.35, 0.8)]},
             "Grandma": {"x": gx, "z": gz, "yaw": 90, "y": ROOM_Y, "face": "기본 미소", "acts": [("arm", "L", 82, 0, -1, 0.1, None, -25)]}})
# 39  거기엔, 시계 수리점 할머니가 있었어.
ghp = head("Grandma", gx, gz, 90, ROOM_Y)
shot((39, 39), "night", fstop=2.4,
     cam=[(0, (476.5, 4.2, gz - 1.0), ghp, 38), (1.87, (476.0, 4.4, gz - 0.6), ghp, 32)],
     actors={"Haru": {**haru_lie, "face": "놀람"},
             "Grandma": {"x": gx, "z": gz, "yaw": 90, "y": ROOM_Y, "face": "놀람", "acts": [("arm", "L", 82, 0, -1, 0.1, 0.4, -25), ("jerk", 0.1, 0.8)]}})
# 40  매일 아침 하루한테 사탕을 쥐여 주던, 그 할머니.  (낮 회상: 수리점 앞에서 사탕)
shot((40, 40), "day", temp=7800, fstop=3.2,
     cam=[(0, (SHOP[0] + 5.0, 4.6, SHOP[1] - 6.5), (SHOP[0] + 1.8, 3.6, SHOP[1]), 42), (2.56, (SHOP[0] + 4.6, 4.4, SHOP[1] - 5.6), (SHOP[0] + 1.8, 3.6, SHOP[1]), 38)],
     actors={"Grandma": {"x": SHOP[0], "z": SHOP[1], "yaw": 90, "y": WALK_Y, "face": "활짝 웃음", "acts": [("arm", "R", 55, 0, 0.2, 0.4)]},
             "Haru": {"x": SHOP[0] + 3.6, "z": SHOP[1] + 0.4, "yaw": -95, "face": "활짝 웃음", "scale": 0.92, "acts": [("arm", "R", 55, 0, 0.5, 0.4), ("bounce", 0.12, 1.2, 2)]}})
# 41  할머니는 깜짝 놀라서 소매를 내렸어.
shot((41, 41), "night", fstop=2.4,
     cam=[(0, (gx + 3.4, 5.2, gz - 3.4), (gx + 0.3, 3.6, gz - 0.4), 40), (2.02, (gx + 3.0, 5.0, gz - 3.0), (gx + 0.3, 3.6, gz - 0.4), 36)],
     actors={"Haru": {**haru_lie, "face": "놀람"},
             "Grandma": {"x": gx, "z": gz, "yaw": 90, "y": ROOM_Y, "bare": [(0, True), (0.9, False)], "num": num_live(5 * 60 + 2),
                         "acts": [("arm", "L", 60, 0, -1, 0.1, 0.6), ("arm", "R", 45, 0, 0.3, 0.3, 1.1, 25), ("expr", [(0, "당황")]), ("look", -10, 15, 0.5, 0.8)]}})
# 42  하지만 하루는 이미 봤어.
shot((42, 42), "night", fstop=2.0,
     cam=push((BED["x"] - 1.0, 5.6, hp_lie[2] - 1.6), hp_lie, 30, 1.36, amt=0.15),
     actors={"Haru": {**haru_lie, "face": "충격"}})
# 43-44  할머니 팔에 남은 숫자. 오 분.  (회상하듯 팔 클로즈업)
p, l = arm_cam("Grandma", gx, gz, 90, ROOM_Y, raise_=60, dist=1.8, back=0.2)
shot((43, 44), "night", fstop=2.0, temp=6000,
     cam=[(0, add(p, (0, 0.2, 0)), l, 32), (1.75, p, l, 25)],
     actors={"Grandma": {"x": gx, "z": gz, "yaw": 90, "y": ROOM_Y, "bare": True, "num": num_live(5 * 60), "acts": [("arm", "L", 60, 0, -1, 0.1)], "face": "무표정"}})
# 45-46  할머니는 웃었어. 들켰네.
shot((45, 46), "night", fstop=2.2,
     cam=push(front_cam(ghp, 90, 3.6, -0.3, 25), ghp, 32, 1.68, amt=0.12),
     actors={"Grandma": {"x": gx, "z": gz, "yaw": 90, "y": ROOM_Y, "face": "민망", "acts": [("expr", [(0, "기본 미소"), (1.0, "민망")]), ("tilt", -10, 0.9, 1.3)]},
             "Haru": {**haru_lie, "face": "울먹"}})

# ================================================================== 5. 회상
# 47-48  하루가 태어나던 날, 하루 팔엔 숫자가 하나도 없었대.  (수리점 안, 아기 하루)
bx, bz = 400.0, 3.0
baby = {"x": bx + 2.0, "z": bz - 1.0, "yaw": 180, "y": 3.05, "lie": True, "scale": 0.42, "face": "잠|closed"}
shot((47, 48), "night", temp=9000, exp=0.15, fstop=2.8,
     cam=[(0, (bx - 6.0, 6.5, bz - 9.0), (bx + 1.0, 3.6, bz), 44), (2.87, (bx - 3.5, 5.6, bz - 6.0), (bx + 1.6, 3.4, bz), 38)],
     actors={"Grandma": {"x": bx - 0.2, "z": bz - 0.8, "yaw": 90, "y": ROOM_Y, "face": "슬픔"}, "Haru": dict(baby)})
# 49-50  영. 태어나자마자 멈출 아이였던 거야.
bfa = forearm("Haru", 0, 0, 180, 0, 0, scale=0.42)
bfa_w = (bx + 2.0 + bfa[0], 3.05, bz - 1.0 + bfa[1])
shot((49, 50), "night", temp=9000, exp=0.15, fstop=1.8,
     cam=[(0, (bfa_w[0] - 1.1, bfa_w[1] + 0.5, bfa_w[2] - 0.6), bfa_w, 30), (2.1, (bfa_w[0] - 0.9, bfa_w[1] + 0.4, bfa_w[2] - 0.5), bfa_w, 26)],
     actors={"Haru": {**baby, "bare": True, "num": {"text": "0:00:00", "size": 1.0}}})
# 51-52  그날 할머니가 하루의 손목을 잡고, 하루치를 넘겼어.
shot((51, 52), "night", temp=9000, exp=0.15, fstop=2.4,
     cam=[(0, (bx - 1.2, 5.4, bz - 6.0), (bx + 0.8, 3.4, bz - 0.8), 42), (2.87, (bx - 1.0, 5.0, bz - 5.0), (bx + 0.8, 3.4, bz - 0.8), 38)],
     actors={"Grandma": {"x": bx - 0.6, "z": bz - 1.6, "yaw": 90, "y": ROOM_Y, "face": "결심", "bare": True, "num": {"text": LONG_TEXT, "size": 0.62},
                         "acts": [("arm", "L", 55, 0, 0.1, 0.6, None, 10)]},
             "Haru": {**baby, "bare": True, "num": num_keys([(0, 0), (1.2, 0), (2.6, 24 * 3600)], "smooth", glow=[(1.1, 2.9)])}},
     touchglow=(1.0, 2.9, "Grandma", 50))
# 53  그 다음 날도.  (시계탑 바늘, 밤)
shot((53, 53), "night", cam=[(0, (-8, 50, -232), TOWER, 22), (0.79, (-6, 52, -236), TOWER, 20)], fstop=11, temp=8500)
# 54  그 다음 날도.  (다락방, 조금 자란 하루)
kid = {"x": BED["x"], "z": BED["pillow_z"] + 0.3 - RIG["Haru"]["Head"][1] * 0.65, "yaw": 180, "y": BED["y"] - 0.15, "lie": True, "scale": 0.65, "face": "잠|closed"}
shot((54, 54), "night", temp=8500, fstop=3.2,
     cam=[(0, (469.5, 6.0, -6.0), (475.0, 3.2, 0.5), 42), (0.81, (469.8, 5.8, -5.0), (475.0, 3.2, 0.5), 40)],
     actors={"Haru": kid, "Grandma": {"x": 472.6, "z": 1.2, "yaw": 90, "y": ROOM_Y, "face": "기본 미소", "acts": [("arm", "L", 65, 0, -1, 0.1, None, 15)]}},
     touchglow=(0.0, 0.81, "Grandma", 40))
# 55  십이 년 동안, 매일 밤.  (자란 하루, 넓게)
teen = {**haru_lie, "scale": 0.88, "z": BED["pillow_z"] + 0.3 - RIG["Haru"]["Head"][1] * 0.88, "face": "잠|closed"}
shot((55, 55), "night", temp=8000, fstop=5.6,
     cam=[(0, (466.0, 9.0, -11.0), (474.0, 3.0, 1.0), 48), (1.53, (467.0, 8.0, -9.0), (474.0, 3.0, 1.0), 46)],
     actors={"Haru": teen, "Grandma": {"x": 472.5, "z": 1.6, "yaw": 90, "y": ROOM_Y, "face": "기본 미소", "acts": [("arm", "L", 68, 0, -1, 0.1, None, 15)]}},
     touchglow=(0.0, 1.53, "Grandma", 40))
# 56  할머니 팔의 긴 숫자는, 그렇게 하루한테 건너온 거야.  (할머니 팔: 긴 숫자 -> 짧아짐)
gx2, gz2 = 401.0, -2.0
p, l = arm_cam("Grandma", gx2, gz2, 90, ROOM_Y, raise_=70, dist=1.9, back=0.2)
steps = [(0.0, LONG_TEXT), (0.7, "43,800:00:00\n35,040:00:00"), (1.4, "26,280:00:00"), (2.1, "8,760:00:00"), (2.6, "0:05:00")]
shot((56, 56), "night", temp=8000, fstop=2.0,
     cam=[(0, add(p, (0, 0.3, 0.3)), l, 34), (2.95, p, l, 28)],
     actors={"Grandma": {"x": gx2, "z": gz2, "yaw": 90, "y": ROOM_Y, "bare": True, "acts": [("arm", "L", 70, 0, -1, 0.1)],
                         "num": {"text": (lambda st: (lambda t: [s for tt, s in st if t >= tt][-1]))(steps), "size": 0.62}}})

# ================================================================== 6. 선택
# 이후 다락방 현재: 하루는 일어나 할머니와 마주 섬
hx3, hz3 = 471.0, 2.0
gx3, gz3 = 471.0, -2.3
h3 = head("Haru", hx3, hz3, 180, ROOM_Y)
g3 = head("Grandma", gx3, gz3, 0, ROOM_Y)
room2 = lambda hf, gf, hacts=(), gacts=(), gbare=False, gnum=None: {
    "Haru": {"x": hx3, "z": hz3, "yaw": 180, "y": ROOM_Y, "face": hf, "acts": list(hacts), "bare": True, "num": {"text": "24:00:00"}},
    "Grandma": {"x": gx3, "z": gz3, "yaw": 0, "y": ROOM_Y, "face": gf, "acts": list(gacts), "bare": gbare, "num": gnum or num_live(4 * 60 + 40)}}
# 57  하루는 할머니 손목을 붙잡았어.
shot((57, 57), "night", fstop=2.8,
     cam=[(0, (hx3 + 7.5, 5.0, -0.2), (hx3, 3.6, -0.2), 44), (1.73, (hx3 + 6.8, 4.8, -0.2), (hx3, 3.6, -0.2), 42)],
     actors=room2("결심", "놀람", hacts=[("arm", "R", 75, 0, 0.1, 0.3, None, 20)], gacts=[("arm", "L", 60, 0, -1, 0.1, None, -10)], gbare=True))
# 58  자기 숫자를 전부 돌려주려고.
shot((58, 58), "night", fstop=2.2, cam=push(front_cam(h3, 180, 3.4, -0.2, 15), h3, 32, 1.68, amt=0.12),
     actors=room2("울먹", "놀람", hacts=[("arm", "R", 75, 0, -1, 0.1, None, 20), ("nod", 10, 0.6, 0.5)], gacts=[("arm", "L", 60, 0, -1, 0.1, None, -10)], gbare=True))
# 59  할머니가 손을 뺐어.
shot((59, 59), "night", fstop=2.8,
     cam=[(0, (hx3 - 7.0, 5.0, -0.2), (hx3, 3.6, -0.2), 44), (1.13, (hx3 - 6.5, 4.8, -0.2), (hx3, 3.6, -0.2), 42)],
     actors=room2("울먹", "슬픔", hacts=[("arm", "R", 75, 0, -1, 0.1, 0.3, 20)], gacts=[("arm", "L", 60, 0, -1, 0.1, 0.25, -10), ("shake", 10, 0.3, 0.7)], gbare=[(0, True), (0.7, False)]))
# 60  그럼 네가 멈추잖니.
shot((60, 60), "night", fstop=2.2, cam=push(front_cam(g3, 0, 3.2, 0.1, -12), g3, 32, 1.19, amt=0.1),
     actors=room2("울먹", "슬픔", gacts=[("tilt", -8, 0.2, 0.6)]))
# 61  둘 중 하나는, 멈춰야 했어.  (넓게, 둥근 창과 달빛)
shot((61, 61), "night", fstop=6.0,
     cam=[(0, (468.0, 6.0, -9.0), (471.0, 4.5, 2.0), 40), (1.61, (467.0, 7.0, -12.0), (471.0, 4.5, 2.0), 44)],
     actors=room2("울먹", "슬픔", hacts=[("freeze", 0)], gacts=[("freeze", 0)]))
# 62  그때, 문밖이 시끄러워졌어.
shot((62, 62), "night", fstop=3.2,
     cam=[(0, (hx3 + 3.6, 4.6, -4.5), (hx3 - 0.5, 3.8, 0.0), 40), (1.76, (hx3 + 3.2, 4.5, -3.8), (hx3 - 0.5, 3.8, 0.0), 38)],
     actors=room2("놀람", "놀람", hacts=[("look", 0, -60, 0.15, 0.4), ("jerk", 0.15, 0.8)], gacts=[("look", 0, 60, 0.2, 0.45)]))
# 63  몰래 따라온 부자가 소리친 거야.  (문 앞 부자)
dr = (459.6, -4.6)
rhp2 = head("Rich", dr[0], dr[1], 90, ROOM_Y)
shot((63, 63), "night", fstop=2.6,
     cam=[(0, front_cam(rhp2, 90, 6.0, -1.6, -10), rhp2, 38), (1.64, front_cam(rhp2, 90, 4.0, -1.2, -8), rhp2, 34)], ease="out",
     actors={"Rich": {"x": dr[0], "z": dr[1], "yaw": 90, "y": ROOM_Y, "face": "분노", "acts": [("arm", "R", 85, 0, 0.0, 0.2), ("jerk", 0.1, 1.0)]}})

# ================================================================== 7. 나눔 (밤, 수리점 앞 거리)
gS = {"x": SHOP[0] + 0.6, "z": SHOP[1] - 1.2, "yaw": 90, "y": WALK_Y}
hS = {"x": SHOP[0] + 0.6, "z": SHOP[1] + 2.2, "yaw": 90, "y": WALK_Y}
ghS = head("Grandma", gS["x"], gS["z"], 90, WALK_Y)
gfa_touch = forearm("Grandma", gS["x"], gS["z"], 90, WALK_Y, raise_=84, inward=26)
village = ["TownA", "TownB", "TownC", "TownD", "TownE", "TownF", "TownA2", "TownB2", "TownC2", "TownD2", "TownE2", "TownF2"]


def street_crowd(n_use, face="무표정", acts=None):
    out = {}
    for i, n in enumerate(village[:n_use]):
        row, col = divmod(i, 4)
        out[n] = {"x": -6.5 + row * 2.8 + (col % 2) * 0.7, "z": SHOP[1] - 4.5 + col * 3.0, "yaw": -90 + (col - 1.5) * 8, "face": face, "y": STREET_Y,
                  "acts": list(acts or [])}
    return out


# 64  마을 사람들이 하나둘 모였어.
gather = {}
for i, n in enumerate(village):
    row, col = divmod(i, 4)
    tx, tz = -6.5 + row * 2.8 + (col % 2) * 0.7, SHOP[1] - 4.5 + col * 3.0
    sx_, sz_ = tx + 5 + (i % 3) * 2, tz + (12 if i % 2 else -12)
    t_arr = 0.2 + (i % 6) * 0.2
    gather[n] = {"path": [(0, sx_, sz_, -90), (t_arr, sx_, sz_, -90), (t_arr + 1.0, tx, tz, -90)], "face": "놀람", "y": STREET_Y}
shot((64, 64), "night", fstop=8.0,
     cam=[(0, (8.0, 14.0, -40.0), (-5.0, 3.0, -62.0), 50), (1.52, (7.0, 12.0, -44.0), (-5.0, 3.0, -62.0), 48)],
     actors={**gather, "Grandma": {**gS, "face": "당황"}, "Haru": {**hS, "face": "놀람"}, "Rich": {"x": -2.0, "z": SHOP[1] - 8.5, "yaw": -60, "face": "장난기"}})
crowd_still = street_crowd(12)
# 65  사람들은 할머니 팔을 보고,
shot((65, 65), "night", fstop=3.2,
     cam=[(0, (-12.4, 5.9, SHOP[1] - 5.2), (-4.5, 4.0, SHOP[1] + 0.5), 46), (1.27, (-12.2, 5.7, SHOP[1] - 4.6), (-4.5, 4.0, SHOP[1] + 0.5), 44)],
     actors={**street_crowd(12, "충격", [("look", -15, 0, 0.1, 0.4)]), "Grandma": {**gS, "face": "슬픔", "bare": True, "num": num_live(4 * 60 + 30)}})
# 66  하루의 팔을 봤어.
p, l = arm_cam("Haru", hS["x"], hS["z"], 90, WALK_Y, raise_=70, dist=2.0)
shot((66, 66), "night", fstop=2.0, cam=[(0, add(p, (0, 0.2, 0.3)), l, 32), (1.31, p, l, 28)],
     actors={"Haru": {**hS, "bare": True, "num": {"text": "24:00:00"}, "acts": [("arm", "L", 70, 0, -1, 0.1)], "face": "울먹"}})
# 67  아무도 말이 없었어.
shot((67, 67), "night", fstop=8.0,
     cam=[(0, (2.0, 7.0, SHOP[1] + 12.0), (-7.0, 3.5, SHOP[1]), 46), (1.09, (1.5, 6.8, SHOP[1] + 11.0), (-7.0, 3.5, SHOP[1]), 45)],
     actors={**street_crowd(12, "무표정", [("freeze", 0)]), "Grandma": {**gS, "face": "슬픔"}, "Haru": {**hS, "face": "울먹"},
             "Rich": {"x": -2.0, "z": SHOP[1] - 8.5, "yaw": -60, "face": "무표정"}})
# 68  그런데 빵집 아저씨가 먼저 소매를 걷었어.
bk = {"x": -5.0, "z": SHOP[1] - 1.2, "yaw": -90, "y": STREET_Y}
bkh = head("Baker", bk["x"], bk["z"], -90)
shot((68, 68), "night", fstop=2.8,
     cam=[(0, front_cam(bkh, -90, 3.4, -0.4, 30), bkh, 42), (2.23, front_cam(bkh, -90, 3.0, -0.5, 24), bkh, 40)],
     actors={"Grandma": {**gS, "face": "놀람"}, "Haru": {**hS, "face": "놀람"}, "Baker": {"path": [(0, -2.5, SHOP[1] - 1.2, -90), (0.9, -2.5, SHOP[1] - 1.2, -90), (2.2, bk["x"], bk["z"], -90)],
                                              "y": STREET_Y, "bare": [(0, False), (0.5, True)], "num": num_live(9 * 3600), "face": "결심",
                                              "acts": [("arm", "L", 50, 0, 0.1, 0.3, 0.6), ("arm", "R", 60, 0, 0.1, 0.3, 0.6, 40)]}})
# 69  할머니 손목에, 자기 손목을 댔어.  (손목 맞대기: 할머니 숫자 쪽에서)
touch_bk = {"x": gS["x"] + 4.3, "z": gS["z"], "yaw": -90, "y": STREET_Y}


def touch_pair(giver, gface, gnum0, t_touch, dur, gm0, gm1, extra=None):
    act = [("arm", "L", 84, 0, 0.0, 0.35, None, 26)]
    acts = {"Grandma": {**gS, "bare": True, "acts": list(act), "face": "울먹",
                        "num": num_keys([(0, gm0), (t_touch, gm0), (t_touch + 0.6, gm1), (dur, gm1 - (dur - t_touch - 0.6))], "smooth", glow=[(t_touch, t_touch + 0.7)])},
            giver: {**touch_bk, "bare": True, "acts": list(act), "face": gface, "num": num_keys([(0, gnum0), (t_touch, gnum0), (t_touch + 0.6, gnum0 - 60)], "smooth")}}
    if extra:
        acts.update(extra)
    return acts


mid_t = ((gS["x"] + 2.15 + gfa_touch[0]) / 2, 3.7, (gS["z"] + gfa_touch[2]) / 2)
shot((69, 69), "night", fstop=2.2, touchglow=(0.7, 1.95, "Grandma", 45),
     cam=[(0, (mid_t[0] - 0.4, 4.6, mid_t[2] - 3.4), mid_t, 38), (1.95, (mid_t[0] - 0.3, 4.2, mid_t[2] - 2.7), mid_t, 34)],
     actors=touch_pair("Baker", "결심", 9 * 3600, 0.7, 1.95, 4 * 60 + 28, 5 * 60 + 28, {"Haru": {**hS, "face": "놀람"}}))
# 70  일 분.  (할머니 팔 숫자)
p, l = arm_cam("Grandma", gS["x"], gS["z"], 90, WALK_Y, raise_=84, inward=26, dist=2.4)
shot((70, 70), "night", fstop=2.0, cam=[(0, p, l, 28), (0.46, add(p, (0.0, 0.0, 0.0)), l, 27)],
     actors={"Grandma": {**gS, "bare": True, "acts": [("arm", "L", 84, 0, -1, 0.1, None, 26)], "num": num_live(5 * 60 + 27), "face": "울먹"}})
# 71  꽃집 누나도.
shot((71, 71), "night", fstop=2.4, touchglow=(0.25, 0.77, "Grandma", 45),
     cam=[(0, (mid_t[0] - 0.4, 4.6, mid_t[2] - 3.6), mid_t, 40), (0.77, (mid_t[0] - 0.3, 4.4, mid_t[2] - 3.2), mid_t, 38)],
     actors=touch_pair("Flower", "기본 미소", 6 * 3600, 0.25, 0.77, 5 * 60 + 26, 6 * 60 + 26))
# 72  일 분.
shot((72, 72), "night", fstop=2.0, cam=[(0, p, l, 27), (0.46, p, l, 26)],
     actors={"Grandma": {**gS, "bare": True, "acts": [("arm", "L", 84, 0, -1, 0.1, None, 26)], "num": num_live(6 * 60 + 25), "face": "울먹"}})
# 73  우산 장수도, 수프 가게 아줌마도,
shot((73, 73), "night", fstop=2.8, touchglow=(0.2, 1.99, "Grandma", 45),
     cam=[(0, (mid_t[0] + 2.5, 5.0, mid_t[2] - 5.5), mid_t, 44), (1.99, (mid_t[0] + 2.0, 4.8, mid_t[2] - 4.6), mid_t, 40)],
     actors={**touch_pair("Umbrella", "기본 미소", 20 * 3600, 0.2, 1.0, 6 * 60 + 24, 7 * 60 + 24),
             "Soup": {"x": touch_bk["x"] + 1.8, "z": touch_bk["z"] + 2.4, "yaw": -100, "y": STREET_Y, "bare": [(0, False), (0.9, True)], "num": num_live(15 * 3600), "face": "결심",
                      "acts": [("arm", "L", 40, 0, 0.9, 0.3)]}})
# 74  일 분씩.  (할머니 숫자가 빨리 오름)
shot((74, 74), "night", fstop=2.0, cam=[(0, p, l, 27), (0.57, p, l, 25)],
     actors={"Grandma": {**gS, "bare": True, "acts": [("arm", "L", 84, 0, -1, 0.1, None, 26)], "face": "울먹",
                         "num": num_keys([(0, 7 * 60 + 23), (0.57, 11 * 60 + 23)], "lin", glow=[(0, 0.6)])}})
# 75  줄은 시장 끝까지 이어졌어.  (높은 곳에서 길게 늘어선 줄)
line_names = ["TownA", "TownB", "TownC", "TownD", "TownE", "TownF", "TownA2", "TownB2", "TownC2", "TownD2", "TownE2", "TownF2", "TownA3", "TownB3", "TownC3", "TownD3", "Flower", "Soup"]
queue = {}
for i, n in enumerate(line_names):
    queue[n] = {"x": -2.0 + (0.6 if i % 2 else -0.4), "z": SHOP[1] + 4.5 + i * 3.6, "yaw": 180 + (i % 3 - 1) * 10, "face": "기본 미소", "y": STREET_Y,
                "bare": i % 3 == 0, "num": num_live(10 * 3600 + i * 777),
                "tint": [None, (0.55, 0.2, 0.18), (0.2, 0.35, 0.5), (0.4, 0.5, 0.25)][i // 4 % 4] if i >= 6 else None}
shot((75, 75), "night", fstop=11,
     cam=[(0, (6.0, 12.0, SHOP[1] - 6.0), (-2.0, 3.0, SHOP[1] + 30.0), 46), (1.59, (6.5, 18.0, SHOP[1] - 10.0), (-2.0, 3.0, SHOP[1] + 34.0), 48)],
     actors={**queue, "Grandma": {**gS, "face": "울먹"}, "Haru": {**hS, "face": "감동"},
             "Baker": {**touch_bk, "x": touch_bk["x"] - 0.3, "face": "활짝 웃음", "bare": True, "num": num_live(9 * 3600 - 60), "acts": [("arm", "L", 84, 0, -1, 0.1, None, 26)]}})
# 76  마지막으로, 그 부자가 소매를 걷었어.
rS = {**touch_bk}
rsh = head("Rich", rS["x"], rS["z"], -90)
shot((76, 76), "night", fstop=2.6, touchglow=(1.3, 2.05, "Grandma", 50),
     cam=[(0, front_cam(rsh, -90, 5.0, -1.0, -28), rsh, 38), (2.05, front_cam(rsh, -90, 4.0, -1.0, -20), rsh, 34)],
     actors={"Rich": {**rS, "bare": [(0, False), (0.6, True)], "num": {"text": RICH_TEXT, "size": 0.62}, "face": "슬픔",
                      "acts": [("expr", [(0, "무표정"), (1.0, "기본 미소")]), ("arm", "L", 84, 0, 1.0, 0.35, None, 26)]},
             "Grandma": {**gS, "bare": True, "face": "놀람", "num": num_live(11 * 60 + 20), "acts": [("arm", "L", 84, 0, 1.0, 0.35, None, 26)]},
             "Haru": {**hS, "face": "놀람"}})
# 77  할머니의 숫자는,
shot((77, 77), "night", fstop=2.0, cam=[(0, add(p, (0, 0.4, 0)), l, 30), (0.74, p, l, 28)],
     actors={"Grandma": {**gS, "bare": True, "acts": [("arm", "L", 84, 0, -1, 0.1, None, 26)], "face": "감동",
                         "num": {"text": "0:11:19"}}})
# 78  이제 소매 끝까지 이어져 있어.  (숫자가 팔을 가득 채움)
steps2 = [(0.0, "0:11:19"), (0.35, "87,600:11:19"), (0.7, "87,600:11:19\n35,040:00:00"), (1.05, FULL_TEXT)]
shot((78, 78), "night", fstop=2.0, cam=[(0, p, l, 27), (1.94, add(p, (0.0, 0.25, 0.0)), add(l, (0, 0.1, 0)), 31)],
     touchglow=(0.0, 1.9, "Grandma", 50),
     actors={"Grandma": {**gS, "bare": True, "acts": [("arm", "L", 84, 0, -1, 0.1, None, 26)], "face": "감동",
                         "num": {"text": (lambda st: (lambda t: [s for tt, s in st if t >= tt][-1]))(steps2), "size": 0.62, "glow": [(0.0, 1.6)]}}})

# ================================================================== 8. 그 후
# 79  그날 이후, 이 마을 시장엔 규칙이 하나 생겼어.  (낮, 게시판)
shot((79, 79), "day", fstop=4.0, rule=True,
     cam=[(0, (0.0, 5.6, 26.0), (0.0, 5.2, 14.0), 40), (2.47, (0.0, 5.4, 21.5), (0.0, 5.2, 14.0), 38)],
     actors={**crowd(["TownA", "TownF"], -7.0, 17.0, 14.0, 0.5, 180, "기본 미소"), "Flower": {"x": 16.0, "z": 22.0, "yaw": -90, "y": WALK_Y, "face": "활짝 웃음"}})
# 80  시간은 팔 수 있어.  (빵 가게, 거래)
shot((80, 80), "day", fstop=3.2,
     cam=[(0, (-6.0, 5.2, 40.0), (-12.5, 4.5, 34.0), 42), (1.09, (-5.6, 5.0, 38.6), (-12.5, 4.5, 34.0), 40)],
     actors={"Baker": {"x": -16.3, "z": 34.0, "yaw": 90, "y": WALK_Y, "face": "활짝 웃음", "acts": [("wave", "R", 0.0, 2)]},
             "TownE": {"x": -10.8, "z": 30.5, "yaw": -57, "face": "기본 미소"}})
# 81  그런데, 나눌 수도 있다.  (두 사람이 웃으며 손목을 맞댐)
ax_, az_ = 3.0, 8.0
mid2 = (ax_ - 2.15, 3.55, az_)
shot((81, 81), "day", fstop=2.6, touchglow=(0.4, 1.41, "TownB", 30),
     cam=[(0, (ax_ - 2.0, 4.9, az_ + 5.4), mid2, 42), (1.41, (ax_ - 2.1, 4.6, az_ + 4.5), mid2, 38)],
     actors={"TownB": {"x": ax_, "z": az_, "yaw": -90, "bare": True, "acts": [("arm", "L", 84, 0, 0.0, 0.3, None, 26)], "face": "활짝 웃음",
                       "num": num_keys([(0, 2 * 3600), (0.4, 2 * 3600), (1.0, 2 * 3600 + 60)], "smooth", glow=[(0.4, 1.0)])},
             "TownC": {"x": ax_ - 4.3, "z": az_, "yaw": 90, "bare": True, "acts": [("arm", "L", 84, 0, 0.0, 0.3, None, 26)], "face": "기본 미소",
                       "num": num_keys([(0, 40 * 3600), (0.4, 40 * 3600), (1.0, 40 * 3600 - 60)], "smooth")}})
# 82  하루의 숫자는 여전히, 매일 밤 다시 차올라.  (밤, 자는 하루, 미소)
shot((82, 82), "night", fstop=2.2,
     cam=[(0, (472.0, 6.2, fa_lie[2] - 4.0), (475.0, 3.6, 1.5), 40), (2.41, (472.9, 4.6, fa_lie[2] - 1.2), fa_lie, 28)],
     actors={"Haru": {**haru_lie, "face": "기본 미소|closed", "num": num_keys([(0, 3.0), (1.3, 0.0), (1.35, 24 * 3600), (2.5, 24 * 3600 - 1)], "lin", glow=[(1.3, 2.2)])}},
     touchglow=(1.25, 2.2, "Haru", 25))
# 83  그리고 이제는 하루도,  (밤거리를 걷는 하루)
shot((83, 83), "night", fstop=4.0,
     cam=[(0, (1.6, 4.4, -12.0), (0.0, 3.8, -1.0), 42), (1.09, (1.5, 4.3, -12.8), (0.0, 3.8, -4.0), 40)],
     actors={"Haru": {"path": [(0, 0.0, -1.0, 180), (1.09, 0.0, -4.5, 180)], "face": "결심"}})
# 84  매일 밤 누군가의 손목에, 일 분을 놓고 와.  (가로등 아래 잠든 노인 손목에 살짝, 그리고 시계탑으로)
ex_, ez_ = 9.0, -20.0
shot((84, 84), "night", fstop=3.5, touchglow=(0.5, 1.6, "Haru", 35),
     cam=[(0, (ex_ - 0.3, 4.6, ez_ + 6.0), (ex_ - 0.2, 3.6, ez_), 42), (1.3, (ex_ - 0.6, 5.2, ez_ + 7.5), (ex_ - 0.2, 3.8, ez_), 44),
          (2.7, (ex_ - 6.0, 12.0, ez_ + 14.0), (0.0, 50.0, -240.0), 46)], ease="smooth",
     actors={"Haru": {"x": ex_ - 2.2, "z": ez_ + 0.3, "yaw": 90, "face": "기본 미소", "acts": [("arm", "L", 75, 0, 0.0, 0.4, 1.7, 20), ("lean", 10, 0.0, 0.4)]},
             "TownE": {"x": ex_ + 1.9, "z": ez_, "yaw": -90, "face": "잠", "bare": True, "num": num_keys([(0, 3600), (0.6, 3600), (1.2, 3660)], "smooth", glow=[(0.6, 1.3)]),
                       "acts": [("arm", "L", 60, 0, 0.0, 0.3, None, 20), ("tilt", 14, 0, 0.1)]}})

# ------------------------------------------------------------------ 시작 시각 정리
SHOTS = []
for i, s in enumerate(S):
    a = s["lines"][0]
    s["start"] = 0.0 if i == 0 else LS[a]
    s["n"] = i + 1
    if s.get("cam") is None:
        raise ValueError(f"shot {i + 1} cam missing")
    SHOTS.append(s)
for s, nx in zip(SHOTS, SHOTS[1:] + [None]):
    s["dur"] = (nx["start"] if nx else TOTAL) - s["start"]
