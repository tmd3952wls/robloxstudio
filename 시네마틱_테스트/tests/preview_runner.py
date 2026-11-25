"""미리보기 컷들을 차례로 렌더 (별도 프로세스로 띄움).
python tests/preview_runner.py still 50       -> 컷마다 가운데 프레임 스틸
python tests/preview_runner.py frames 100     -> 전체 프레임 + 마지막에 영상 조립(음성·자막)
"""
import os
import subprocess
import sys
import time

D = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(D, "..")
BL = r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"
sys.path.insert(0, D)
mode = sys.argv[1] if len(sys.argv) > 1 else "still"
pct = sys.argv[2] if len(sys.argv) > 2 else "50"
only = sys.argv[3:] or None
SHOTS = ["sky", "river", "fireroofs", "waterroofs", "firestreet", "night", "waterfall", "rain", "bridge"]
OUT = os.path.join(R, "out", "preview10")
os.makedirs(OUT, exist_ok=True)
log = open(os.path.join(OUT, f"runner_{mode}.log"), "a", encoding="utf-8")


def L(m):
    log.write(time.strftime("%H:%M:%S ") + m + "\n")
    log.flush()


for s in SHOTS:
    if only and s not in only:
        continue
    L(f"start {s}")
    with open(os.path.join(OUT, f"log_{mode}_{s}.txt"), "w", encoding="utf-8") as f:
        r = subprocess.run([BL, "-b", "--factory-startup", "--python", os.path.join(D, "preview10.py"), "--", s, mode, pct],
                           cwd=R, stdout=f, stderr=subprocess.STDOUT)
    L(f"end {s} exit {r.returncode}")

if mode == "frames":
    A = r"C:\Users\tmd39\Desktop\haru_short\불과물의마을\audio"
    dst = os.path.join(R, "out", "미리보기_10초_시네마틱.mp4")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", "30", "-start_number", "1",
                        "-i", os.path.join(OUT, "frames", "f%04d.png"), "-i", "mix.wav", "-frames:v", "300",
                        "-vf", "subtitles=subs.ass:fontsdir=fonts", "-c:v", "libx264", "-crf", "17", "-preset", "slow",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-t", "10", "-movflags", "+faststart", dst], cwd=A)
    L(f"encode exit {r.returncode}")
L("all done")
