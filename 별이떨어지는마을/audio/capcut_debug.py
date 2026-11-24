"""capcut_auto_tts 의 단계를 하나씩 실행하며 화면 캡처를 남김 (디버그)."""
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

AUTO = Path(r"C:\Users\tmd39\Desktop\60SEC_YOUTUBE_AUTO_SHORT")
sys.path.insert(0, str(AUTO))
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
import tools.capcut_auto_tts as A  # noqa: E402

SHOT = Path(sys.argv[1])
SHOT.mkdir(parents=True, exist_ok=True)
draft = Path(r"C:\Users\tmd39\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft") / sys.argv[2]
step = sys.argv[3] if len(sys.argv) > 3 else "open"


def snap(name):
    w = A.find_capcut_windows()
    A.grab_composite(w).save(SHOT / f"{name}.png")
    print("snap", name, [(x[1], x[3], x[4], x[5], x[6]) for x in w])


subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Process CapCut -ErrorAction SilentlyContinue | Stop-Process -Force"])
time.sleep(1)
A.bump_draft_to_top(draft)
env = os.environ.copy()
env["QSG_RHI_BACKEND"] = "opengl"
env["QT_OPENGL"] = "software"
proc = subprocess.Popen([A.resolve_capcut_exe()], env=env)
time.sleep(10)
for _ in range(20):
    if A.find_capcut_windows():
        break
    time.sleep(2)
time.sleep(2)
wins = A.find_capcut_windows()
main = max(wins, key=lambda x: x[5] * x[6])[0]
for w in wins:
    if w[0] != main:
        A.user32.PostMessageW(w[0], A.WM_CLOSE, 0, 0)
time.sleep(0.8)
A.user32.ShowWindow(main, 3)
time.sleep(1.5)
snap("01_home")
A.post_click(A.find_capcut_windows(), 300, 750)
time.sleep(7)
wins = A.find_capcut_windows()
main = max(wins, key=lambda x: x[5] * x[6])[0]
A.user32.ShowWindow(main, 3)
time.sleep(1.5)
snap("02_editor")
print("남겨 둠: CapCut 켜진 상태")
