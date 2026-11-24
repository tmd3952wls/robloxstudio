"""capcut/line_XX.wav (CapCut 활기찬 바리톤 1.1x) -> 기존 영상 타이밍(timing_edge.json)의 각 문장 자리에 맞춘 narration.wav + timing.json

- 문장 앞뒤 무음 제거, 문장 안 쉼은 0.10초로
- 자리보다 길면 그 문장만 살짝 빠르게(atempo), 짧으면 자리 시작에 붙임 -> 그림(렌더)은 그대로
사용: <earshot venv python> capcut_build.py
"""
import json
import os
import re
import shutil
import subprocess

import numpy as np
import soundfile as sf

D = os.path.dirname(os.path.abspath(__file__))
SR = 48000
GAP_IN, GAP_LINE = 0.10, 0.02
if not os.path.exists(os.path.join(D, "timing_edge.json")):
    shutil.copyfile(os.path.join(D, "timing.json"), os.path.join(D, "timing_edge.json"))
old = json.load(open(os.path.join(D, "timing_edge.json"), encoding="utf-8"))
total = json.load(open(os.path.join(D, "cut_frames.json")))["total"] / 30.0


def segments(path):
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True).stdout)
    log = subprocess.run(["ffmpeg", "-i", path, "-af", "silencedetect=noise=-40dB:d=0.12", "-f", "null", "-"], capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    sil = list(zip(st, en + [dur] * (len(st) - len(en))))
    segs, t = [], 0.0
    for a, b in sil:
        if a - t > 0.03:
            segs.append((max(0.0, t - 0.02), a + 0.03))
        t = b
    if dur - t > 0.03:
        segs.append((max(0.0, t - 0.02), dur))
    return segs


def load(path, extra=""):
    tmp = os.path.join(D, "capcut", "_tmp.wav")
    af = ["-af", extra] if extra else []
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, *af, "-ar", str(SR), "-ac", "1", tmp], check=True)
    a, _ = sf.read(tmp, dtype="float32")
    return a


def fade(a):
    n1, n2 = int(0.01 * SR), int(0.015 * SR)
    a = a.copy()
    a[:n1] *= np.linspace(0, 1, n1)
    a[-n2:] *= np.linspace(1, 0, n2)
    return a


def syl(w):
    return max(1, len(re.sub(r"[^가-힣A-Za-z0-9]", "", w)))


starts = [e["start"] for e in old if e["text"]]
mix = np.zeros(int(total * SR) + SR, dtype=np.float32)
out, report = [], []
EARLY, LATE = 0.20, 0.35
prev_end = -1.0
voiced = [e for e in old if e["text"]]
for e in old:
    n, text = e["n"], e["text"]
    if not text:
        out.append(dict(e, words=[]))
        continue
    i = voiced.index(e)
    nxt = voiced[i + 1]["start"] if i + 1 < len(voiced) else total - 0.3
    # 그림 자리에서 0.2초 일찍 ~ 0.35초 늦게까지 허용하며 앞 문장 바로 뒤에 이어 붙임 -> 덜 빨라짐
    st = max(e["start"] - EARLY, prev_end + GAP_LINE, 0.0)
    slot = nxt + LATE - st - GAP_LINE
    src = os.path.join(D, "capcut", f"line_{n:02d}.wav")
    full = load(src)
    segs = segments(src)
    parts, seg_t, t = [], [], 0.0
    for k, (a, b) in enumerate(segs):
        p = fade(full[int(a * SR):int(b * SR)])
        parts.append(p)
        seg_t.append((t, t + len(p) / SR))
        t += len(p) / SR
        if k < len(segs) - 1:
            parts.append(np.zeros(int(GAP_IN * SR), dtype=np.float32))
            t += GAP_IN
    line = np.concatenate(parts)
    L = len(line) / SR
    f = 1.0
    if L > slot:
        f = L / slot
        tmpw = os.path.join(D, "capcut", "_line.wav")
        sf.write(tmpw, line, SR)
        line = load(tmpw, f"atempo={f:.5f}")
    i0 = int(st * SR)
    mix[i0:i0 + len(line)] += line
    prev_end = st + len(line) / SR
    # 어절 시각: 쉼표 구절 = 소리 구간, 구절 안은 글자 수 비율
    phrases = [p.split() for p in re.split(r"[,]", text) if p.strip()]
    groups = list(zip(phrases, seg_t)) if len(phrases) == len(seg_t) else [(sum(phrases, []), (seg_t[0][0], seg_t[-1][1]))]
    words = []
    for ws, (a, b) in groups:
        tot = sum(syl(w) for w in ws)
        tt = a
        for w in ws:
            d = (b - a) * syl(w) / tot
            words.append([round(st + tt / f, 3), round(st + (tt + d) / f, 3), w.strip(".,!?")])
            tt += d
    out.append({"n": n, "text": text, "start": round(st, 3), "dur": round(len(line) / SR, 3), "words": words})
    report.append((n, round(L, 2), round(slot, 2), round(f, 3), round(st - e["start"], 2)))

sf.write(os.path.join(D, "narration.wav"), mix[:int(total * SR)], SR, subtype="PCM_16")
json.dump(out, open(os.path.join(D, "timing.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
fs = [r[3] for r in report]
gaps = [r[2] - r[1] for r in report if r[1] < r[2]]
print("빨라진 문장", sum(1 for x in fs if x > 1.001), "/", len(fs), " 최대 x", max(fs))
print("남는 틈 평균", round(float(np.mean(gaps)) if gaps else 0, 2), "s, 최대", round(max(gaps) if gaps else 0, 2))
for r in report:
    print(*r)
