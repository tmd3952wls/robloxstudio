"""script.tsv 전 문장을 CapCut '활기찬 바리톤'(1.1x)으로 자동 생성·수확 (대기 시간 늘린 버전).
없는 문장만 5개씩 묶어 반복. 결과는 capcut/line_XX.wav 로 복사.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

D = Path(__file__).resolve().parent
AUTO = Path(r"C:\Users\tmd39\Desktop\60SEC_YOUTUBE_AUTO_SHORT")
sys.path.insert(0, str(AUTO))
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
import tools.capcut_auto_tts as A  # noqa: E402
from shorts.common import ASSETS, JOBS, read_json  # noqa: E402
from shorts.textnorm import tts_say  # noqa: E402
from tools.capcut_voice import harvest, key, make  # noqa: E402

VO = ASSETS / "voices" / "vibrant_baritone"
rows = [l.split("\t") for l in (D / "script.tsv").read_text(encoding="utf-8").strip("\n").split("\n")]
lines = [(int(r[0]), r[2].strip()) for r in rows if len(r) > 2 and r[2].strip()]


def have(t):
    return (VO / f"{key(tts_say(t))}.wav").exists()


def kill():
    subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Process CapCut -ErrorAction SilentlyContinue | Stop-Process -Force"])
    time.sleep(1.5)


def mainwin():
    w = A.find_capcut_windows()
    return w, max(w, key=lambda x: x[5] * x[6])[0]


def one_batch(job, batch):
    (JOBS / job).mkdir(parents=True, exist_ok=True)
    (JOBS / job / "edl.json").write_text(json.dumps({"items": [{"type": "narration", "text": t} for t in batch]}, ensure_ascii=False), encoding="utf-8")
    kill()
    make(job, "edl.json", "vibrant_baritone")
    man = read_json(JOBS / job / "capcut_voice_vibrant_baritone.json")
    folder = Path(man["draft"])
    A.bump_draft_to_top(folder)
    env = os.environ.copy()
    env["QSG_RHI_BACKEND"] = "opengl"
    env["QT_OPENGL"] = "software"
    proc = subprocess.Popen([A.resolve_capcut_exe()], env=env)
    try:
        time.sleep(10)
        for _ in range(20):
            if A.find_capcut_windows():
                break
            time.sleep(2)
        time.sleep(2)
        wins, mw = mainwin()
        for w in wins:
            if w[0] != mw:
                A.user32.PostMessageW(w[0], A.WM_CLOSE, 0, 0)
        time.sleep(1)
        A.user32.ShowWindow(mw, 3)
        time.sleep(1.5)
        A.post_click(A.find_capcut_windows(), 300, 750)      # 첫 프로젝트 열기
        time.sleep(8)
        wins, mw = mainwin()
        A.user32.ShowWindow(mw, 3)
        time.sleep(2)
        wins = A.find_capcut_windows()
        im = np.array(A.grab_composite(wins))
        ys = np.where((im[700:900, 230, 0] > 150) & (im[700:900, 230, 1] < 120))[0] + 700
        ym = int(ys.mean()) if len(ys) else 832
        xs = np.where((im[ym, 150:1880, 0] > 140) & (im[ym, 150:1880, 1] < 120))[0] + 150
        xr = min(1880, (int(xs.max()) + 40) if len(xs) else 1600)
        A.post_drag(wins, xr, ym - 22, 165, ym + 22, steps=25)  # 텍스트 전부 선택
        time.sleep(1.5)
        A.post_click(A.find_capcut_windows(), 1535, 50)       # 텍스트에서 음성으로
        time.sleep(7)
        A.post_click(A.find_capcut_windows(), 1600, 101)      # 검색창
        time.sleep(1)
        wins, mw = mainwin()
        A.post_type(mw, "활기찬 바리톤", enter=True)
        time.sleep(4)
        A.post_click(A.find_capcut_windows(), 1384, 207)      # Vibrant Baritone
        time.sleep(2.5)
        A.post_click(A.find_capcut_windows(), 1862, 670)      # 음성 생성
        tr = folder / "textReading"
        n = 0
        for _ in range(60):
            n = len(list(tr.glob("*.wav"))) if tr.exists() else 0
            if n >= len(man["lines"]):
                break
            time.sleep(2)
        time.sleep(3)
        print(f"  생성 wav {n}/{len(man['lines'])}")
        for w in A.find_capcut_windows():
            A.user32.PostMessageW(w[0], A.WM_CLOSE, 0, 0)
        time.sleep(7)
    finally:
        proc.terminate()
        kill()
    harvest(job, "vibrant_baritone", fallback_speed=1.1)


fails, bi = 0, 1
while True:
    miss = []
    for _, t in lines:
        if not have(t) and t not in miss:
            miss.append(t)
    print(f"남은 문장 {len(miss)}")
    if not miss or fails >= 5:
        break
    before = len(miss)
    try:
        # 한 문장만 남으면 타임라인이 꽉 차서 드래그 선택이 안 됨 -> 버리는 문장을 하나 덧붙임
        b = miss[:5] if len(miss) > 1 else miss + ["여기는 시험용 문장이에요."]
        one_batch(f"byeol_d{bi:02d}", b)
    except Exception as ex:
        print("  배치 오류:", ex)
        kill()
    bi += 1
    after = sum(1 for t in miss if not have(t))
    fails = fails + 1 if after == before else 0

out = D / "capcut"
out.mkdir(exist_ok=True)
lost = []
for n, t in lines:
    src = VO / f"{key(tts_say(t))}.wav"
    if src.exists():
        shutil.copyfile(src, out / f"line_{n:02d}.wav")
    else:
        lost.append(n)
print("DONE 없는 줄:", lost)
