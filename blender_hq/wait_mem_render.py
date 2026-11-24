"""여유 메모리가 MIN_GB 이상이 될 때까지 기다렸다가 render_full.py 를 실행 (이미 그린 프레임은 건너뜀).
사용: python wait_mem_render.py [MIN_GB]"""
import ctypes
import os
import subprocess
import sys
import time

D = os.path.dirname(os.path.abspath(__file__))
MIN_GB = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
LOG = os.path.join(D, "out", "render_full.log")


class MS(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def free_gb():
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 2 ** 30


def log(s):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + s + "\n")


log(f"waiting for free memory >= {MIN_GB} GB (now {free_gb():.1f})")
ok = 0
while ok < 3:            # 30초 연속(3번) 여유가 있을 때 시작
    ok = ok + 1 if free_gb() >= MIN_GB else 0
    time.sleep(10)
log(f"memory ok ({free_gb():.1f} GB) -> render start")
subprocess.run([sys.executable, os.path.join(D, "render_full.py"), "frames2", "1", "4016"], cwd=D)
