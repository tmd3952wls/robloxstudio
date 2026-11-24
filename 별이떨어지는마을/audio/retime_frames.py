"""retime.json 으로 기존 렌더 프레임을 새 음성 타이밍에 맞춘 프레임 목록(ffconcat) 생성.
사용: retime_frames.py <frames_dir> <out.ffconcat>   (렌더된 프레임까지만)
"""
import json
import sys
from pathlib import Path

D = Path(__file__).resolve().parent
RT = json.load(open(D / "retime.json"))
A = RT["anchors"]
fr = Path(sys.argv[1])
have = len(list(fr.glob("f*.png")))


def inv(t):
    for (o0, n0), (o1, n1) in zip(A, A[1:]):
        if t <= n1:
            return o0 + (t - n0) * (o1 - o0) / max(1e-6, n1 - n0)
    return A[-1][0]


lines, j = ["ffconcat version 1.0"], 0
while True:
    t = j / 30
    if t >= RT["total_new"]:
        break
    f = int(round(inv(t) * 30)) + 1
    if f > have:
        break
    lines.append(f"file '{(fr / f'f{f:04d}.png').as_posix()}'")
    lines.append("duration 0.0333333")
    j += 1
Path(sys.argv[2]).write_text("\n".join(lines) + "\n", encoding="utf-8")
print("new frames", j, "=", round(j / 30, 2), "s")
