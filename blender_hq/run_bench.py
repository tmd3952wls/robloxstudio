"""bench.py 를 실행하며 최대 VRAM(전체 GPU 사용량 - 시작 전 기준)과 Blender 최대 RAM 을 잰다.
사용: python run_bench.py <mode> <samples> <out.png> <frame> [pct]
"""
import json
import os
import subprocess
import sys
import threading
import time

import psutil

D = os.path.dirname(os.path.abspath(__file__))
BL = r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"


def vram():
    r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True)
    return int(r.stdout.strip().splitlines()[0])


base = vram()
p = subprocess.Popen([BL, "-b", os.path.join(D, "market.blend"), "--python", os.path.join(D, "bench.py"), "--"] + sys.argv[1:],
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
peak = {"vram": base, "ram": 0}
stop = False


def poll():
    pr = psutil.Process(p.pid)
    while not stop:
        try:
            peak["ram"] = max(peak["ram"], pr.memory_info().peak_wset)
        except Exception:
            pass
        try:
            peak["vram"] = max(peak["vram"], vram())
        except Exception:
            pass
        time.sleep(0.3)


th = threading.Thread(target=poll, daemon=True)
th.start()
log = []
for line in p.stdout:
    log.append(line)
p.wait()
stop = True
th.join(1)
res = {}
for line in log:
    if line.startswith("BENCH "):
        res = json.loads(line[6:])
res.update({"vram_peak_mb": peak["vram"], "vram_base_mb": base, "vram_used_mb": peak["vram"] - base,
            "ram_peak_gb": round(peak["ram"] / 2**30, 2), "exit": p.returncode})
name = os.path.splitext(os.path.basename(sys.argv[3]))[0]
open(os.path.join(D, "out", name + ".log"), "w", encoding="utf-8").write("".join(log))
open(os.path.join(D, "out", name + ".json"), "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps(res, ensure_ascii=False))
errs = [l for l in log if "Error" in l or "Traceback" in l or "skip" in l]
print("".join(errs[-25:]))
