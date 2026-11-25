"""본편 컷들을 차례로 렌더 (컷마다 별도 블렌더 프로세스). 별도 프로세스(Start-Process)로 띄울 것.
python film/film_runner.py still 50 [컷...]     -> 컷마다 가운데 스틸 + 카메라 충돌 검사
python film/film_runner.py frames 100 [컷...]   -> 전체 프레임 (있는 프레임 건너뜀)
python film/film_runner.py probe 25 [컷...]     -> 충돌 검사만
로그: out/film/runner_<mode>.log, out/film/logs/<mode>_<컷>.txt
"""
import os
import subprocess
import sys
import time

D = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(D, "..")
sys.path.insert(0, D)
import shotlist as SL

BL = r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"
mode = sys.argv[1] if len(sys.argv) > 1 else "still"
pct = sys.argv[2] if len(sys.argv) > 2 else "50"
only = sys.argv[3:] or None
OUT = os.path.join(R, "out", "film")
os.makedirs(os.path.join(OUT, "logs"), exist_ok=True)
log = open(os.path.join(OUT, f"runner_{mode}.log"), "a", encoding="utf-8")


def L(m):
    log.write(time.strftime("%H:%M:%S ") + m + "\n")
    log.flush()


L(f"=== run {mode} {pct} {only or 'all'}")
for name, f0, f1, eng in SL.shots():
    if only and name not in only:
        continue
    if mode == "frames" and all(os.path.exists(os.path.join(OUT, "frames", f"f{f:04d}.png")) for f in range(f0, f1 + 1)):
        L(f"skip {name} (done)")
        continue
    L(f"start {name} {f0}-{f1} {eng}")
    t = time.time()
    with open(os.path.join(OUT, "logs", f"{mode}_{name}.txt"), "w", encoding="utf-8") as f:
        r = subprocess.run([BL, "-b", "--factory-startup", "--python", os.path.join(D, "film.py"), "--", name, mode, pct],
                           cwd=R, stdout=f, stderr=subprocess.STDOUT)
    L(f"end {name} exit {r.returncode} {time.time() - t:.0f}s")
L("all done")
