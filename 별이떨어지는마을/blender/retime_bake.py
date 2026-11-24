"""bake_export.txt 의 각 컷 길이를 새 음성(audio/retime.json)에 맞게 다시 샘플링.

- 컷 시작: 기존 시작 시각을 retime 대응점으로 옮김 -> 새 프레임 수 n'
- 카메라(c): 기존 프레임 u = j*n/n' 에서 위치·FOV 선형, 회전 정규화 보간
- 별(f): 프레임별 목록이면 같은 방식(별마다 선형, 없으면 가까운 값)
- S 의 k (연출 시간/실제 시간) = k * n/n'  -> 캐릭터·하늘·뚜껑 등 연출 시각은 그대로 맞음
사용: python retime_bake.py  (bake_export.txt 를 bake_export_r4.txt 로 백업 후 덮어씀)
"""
import json
import math
import shutil
from pathlib import Path

B = Path(__file__).resolve().parent
A = B.parent / "audio"
RT = json.load(open(A / "retime.json"))
anch = RT["anchors"]
src = B / "bake_export_r4.txt"
if not src.exists():
    shutil.copyfile(B / "bake_export.txt", src)


def remap(t):
    for (o0, n0), (o1, n1) in zip(anch, anch[1:]):
        if t <= o1:
            return n0 + (t - o0) * (n1 - n0) / max(1e-6, o1 - o0)
    return anch[-1][1]


shots, cur = [], None
for line in src.read_text(encoding="utf-8").split("\n"):
    if not line:
        continue
    if line[0] == "S":
        cur = {"S": line.split("|"), "c": [], "f": [], "other": []}
        shots.append(cur)
    elif line[0] == "c":
        cur["c"].append(line.split("|"))
    elif line[0] == "f":
        cur["f"].append(line[2:].split(";"))
    else:
        cur["other"].append(line)

TOT = int(round(RT["total_new"] * 30))
starts = [int(round(remap(int(s["S"][2]) / 30) * 30)) for s in shots]
starts[0] = 0
ends = starts[1:] + [TOT]


def lerp(a, b, t):
    return [x + (y - x) * t for x, y in zip(a, b)]


def qlerp(a, b, t):
    if sum(x * y for x, y in zip(a, b)) < 0:
        b = [-y for y in b]
    q = lerp(a, b, t)
    m = math.sqrt(sum(x * x for x in q)) or 1
    return [x / m for x in q]


out, rep = [], []
for s, st, en in zip(shots, starts, ends):
    S = s["S"]
    n, nn = int(S[3]), max(1, en - st)
    k = float(S[8]) if len(S) > 8 else 1.0
    S2 = S[:2] + [str(st), str(nn)] + S[4:8] + [f"{k * n / nn:.6f}"]
    out.append("|".join(S2))
    for o in s["other"]:
        if o.startswith("k|"):        # 캐릭터 스냅샷: 프레임 번호도 새 길이에 맞게
            _, f0, rest = o.split("|", 2)
            o = f"k|{min(nn - 1, int(round(int(f0) * nn / n)))}|{rest}"
        out.append(o)
    cams = s["c"]
    stars = s["f"] or None          # 앞쪽 m 프레임만 있을 수 있음 (그 뒤는 별 없음)
    m = len(s["f"])
    for j in range(nn):
        u = min(j * n / nn, n - 1)
        i0 = int(math.floor(u))
        i1 = min(i0 + 1, n - 1)
        t = u - i0
        c0, c1 = cams[i0], cams[i1]
        pos = lerp(list(map(float, c0[2].split(","))), list(map(float, c1[2].split(","))), t)
        q = qlerp(list(map(float, c0[3].split(","))), list(map(float, c1[3].split(","))), t)
        fov = float(c0[4]) + (float(c1[4]) - float(c0[4])) * t
        rest = c0[5:]
        out.append("|".join(["c", str(j), ",".join(f"{v:.3f}" for v in pos), ",".join(f"{v:.5f}" for v in q), f"{fov:.2f}"] + rest))
        if stars and i0 < m:
            a, b = stars[i0], stars[min(i1, m - 1)]
            row = []
            for x, y in zip(a, b):
                if x == "-" or y == "-":
                    row.append(x if t < 0.5 else y)
                else:
                    row.append(",".join(f"{v:.2f}" for v in lerp(list(map(float, x.split(","))), list(map(float, y.split(","))), t)))
            out.append("f|" + ";".join(row))
    rep.append((int(S[1]), n, nn))
(B / "bake_export.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print("total frames", TOT, "=", RT["total_new"], "s")
print([r for r in rep if isinstance(r, str)])
print("비율 범위", min(r[2] / r[1] for r in rep if not isinstance(r, str)), max(r[2] / r[1] for r in rep if not isinstance(r, str)))
