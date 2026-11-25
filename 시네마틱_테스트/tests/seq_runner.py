"""남은 연속 렌더 측정을 차례로 실행 (별도 프로세스로 띄워 Claude Code 메모리 정리에 안 죽게).
python tests/seq_runner.py  -> out/seq_runner.log
"""
import os
import subprocess
import time

D = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(D, "..")
BL = r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"
JOBS = [  # (스크립트, 인자, 프레임 수, 이름)
    ("scene_street.py", ["B", "CYCLES", "128", "100"], 30, "B_cy128"),
    ("scene_street.py", ["C", "EEVEE", "64", "100"], 20, "C_ee64"),
    ("scene_street.py", ["C", "CYCLES", "64", "100"], 20, "C_cy64"),
    ("scene_a.py", ["EEVEE", "64", "100"], 20, "A_ee64"),
]
log = open(os.path.join(R, "out", "seq_runner.log"), "a", encoding="utf-8")


def L(m):
    log.write(time.strftime("%H:%M:%S ") + m + "\n")
    log.flush()


for script, args, n, name in JOBS:
    L(f"start {name}")
    env = dict(os.environ, SEQ=str(n))
    with open(os.path.join(R, "out", f"seqlog_{name}.txt"), "w", encoding="utf-8") as f:
        r = subprocess.run([BL, "-b", "--factory-startup", "--python", os.path.join(D, script), "--", *args],
                           cwd=R, env=env, stdout=f, stderr=subprocess.STDOUT)
    L(f"end {name} exit {r.returncode}")
L("all done")
