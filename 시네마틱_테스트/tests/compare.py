"""기존 vs 개선 나란히 비교 이미지 (라벨 포함). python tests/compare.py"""
import os
import subprocess

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
FONT = "Jua.ttf"   # out 폴더에서 상대 경로로 실행 (윈도우 경로 콜론 문제 회피)
PAIRS = [("compare/old_f0012.png", "A_eevee.png", "A_cycles.png", "A 마을 전경"),
         ("compare/old_f0150.png", "B_eevee.png", "B_cycles.png", "B 마을 거리"),
         ("compare/old_f0178.png", "C_eevee.png", "C_cycles.png", "C 캐릭터 등장")]


def lab(t):
    return f"drawtext=fontfile='{FONT}':text='{t}':x=24:y=24:fontsize=54:fontcolor=white:borderw=4:bordercolor=black"


for old, ee, cy, name in PAIRS:
    ins, f = [], []
    items = [(old, "기존"), (ee, "개선 EEVEE"), (cy, "개선 Cycles")]
    items = [(p, l) for p, l in items if os.path.exists(os.path.join(D, p))]
    for i, (p, l) in enumerate(items):
        ins += ["-i", os.path.join(D, p)]
        f.append(f"[{i}]scale=540:960,{lab(l)}[v{i}]")
    fc = ";".join(f) + ";" + "".join(f"[v{i}]" for i in range(len(items))) + f"hstack={len(items)}"
    out = os.path.join(D, "compare", f"비교_{name.split()[0]}.png")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", fc, out], check=True, cwd=D)
    print(out)
