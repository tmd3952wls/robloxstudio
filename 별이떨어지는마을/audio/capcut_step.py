"""실행 중인 CapCut 에 동작 하나 보내고 캡처. 사용: capcut_step.py <shotdir> <name> <op> [args...]
op: click x y | drag x1 y1 x2 y2 | type 텍스트 | key vk | snap
"""
import sys
import time
from pathlib import Path

AUTO = Path(r"C:\Users\tmd39\Desktop\60SEC_YOUTUBE_AUTO_SHORT")
sys.path.insert(0, str(AUTO))
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
import tools.capcut_auto_tts as A  # noqa: E402

shot, name, op, *args = sys.argv[1:]
wins = A.find_capcut_windows()
main = max(wins, key=lambda x: x[5] * x[6])[0]
if op == "click":
    A.post_click(wins, int(args[0]), int(args[1]))
elif op == "drag":
    A.post_drag(wins, *map(int, args), steps=25)
elif op == "type":
    A.post_type(main, args[0], enter=len(args) < 2)
elif op == "key":
    vk = int(args[0], 0)
    A.user32.PostMessageW(main, A.WM_KEYDOWN, vk, 0)
    time.sleep(0.05)
    A.user32.PostMessageW(main, A.WM_KEYUP, vk, 0xC0000001)
time.sleep(float(args[-1]) if op == "snap" and args else 2.0)
wins = A.find_capcut_windows()
A.grab_composite(wins).save(Path(shot) / f"{name}.png")
print([(x[1], x[3], x[4], x[5], x[6]) for x in wins])
