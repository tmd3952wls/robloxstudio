"""렌더 시간·RAM·VRAM 측정. nvidia-smi 를 0.5초마다 찍어 최대치 기록 (블렌더 프로세스 RAM 은 psutil 없으면 tasklist)."""
import json
import os
import subprocess
import threading
import time

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "perf_log.jsonl")


def _vram():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=5, creationflags=0x08000000)
        return int(r.stdout.strip().split("\n")[0])
    except Exception:
        return -1


def _ram_mb(pid):
    try:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                           timeout=5, creationflags=0x08000000)
        return int(r.stdout.strip().split('","')[-1].replace('"', "").replace(",", "").replace(" K", "").replace("K", "").strip()) // 1024
    except Exception:
        return -1


class Monitor:
    def __init__(self, dt=0.5):
        self.base_vram = _vram()
        self.peak_vram, self.peak_ram = self.base_vram, 0
        self.pid = os.getpid()
        self.run = True
        self.th = threading.Thread(target=self._loop, args=(dt,), daemon=True)
        self.th.start()

    def _loop(self, dt):
        while self.run:
            self.peak_vram = max(self.peak_vram, _vram())
            self.peak_ram = max(self.peak_ram, _ram_mb(self.pid))
            time.sleep(dt)

    def stop(self):
        self.run = False
        self.th.join(timeout=3)
        return {"vram_base_mb": self.base_vram, "vram_peak_mb": self.peak_vram,
                "vram_used_by_blender_mb": self.peak_vram - self.base_vram, "ram_peak_mb": self.peak_ram}


def log(d):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
