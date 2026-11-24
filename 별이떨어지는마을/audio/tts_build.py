"""tts/line_XX.mp3 -> 실제 소리 구간을 재서 숨 쉬는 구간 없이 이어 붙임.

- 문장 앞뒤 무음 제거, 문장 안 쉼(쉼표)은 0.10초로 줄임, 문장 사이 0.02초
- 단어(어절) 시각: 쉼표로 나눈 구절을 소리 구간에 맞추고, 구절 안에서는 글자 수 비율로 나눔
출력: narration.wav, timing.json [{n, start, dur, words:[[t0,t1,word],...]}]
"""
import json
import os
import re
import subprocess

D = os.path.dirname(os.path.abspath(__file__))
SR = 48000
GAP_IN, GAP_LINE = 0.10, 0.02
LINES = [(l.split("\t") + ["", ""])[:3] for l in open(os.path.join(D, "script.tsv"), encoding="utf-8").read().strip("\n").split("\n")]


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
        segs.append((t - 0.02, dur))
    return segs


def syl(w):
    return max(1, len(re.sub(r"[^가-힣A-Za-z0-9]", "", w)))


out, pieces, T = [], [], 0.0
tmp = os.path.join(D, "tts", "seg")
os.makedirs(tmp, exist_ok=True)
for n, _, text in LINES:
    n = int(n)
    if not text.strip():
        out.append({"n": n, "text": "", "start": T, "dur": 0.0, "words": []})
        continue
    mp3 = os.path.join(D, "tts", f"line_{n:02d}.mp3")
    segs = segments(mp3)
    phrases = [p.split() for p in re.split(r"[,]", text) if p.strip()]
    start = T
    seg_times = []
    for k, (a, b) in enumerate(segs):
        wav = os.path.join(tmp, f"l{n:02d}_{k}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-ar", str(SR), "-ac", "1",
                        "-af", "afade=t=in:d=0.01,areverse,afade=t=in:d=0.015,areverse", wav], check=True)
        pieces.append(wav)
        seg_times.append((T, T + (b - a)))
        T += b - a
        if k < len(segs) - 1:
            pieces.append(("gap", GAP_IN))
            T += GAP_IN
    # 단어 시각
    words = []
    if len(phrases) == len(seg_times):
        groups = list(zip(phrases, seg_times))
    else:
        groups = [(sum(phrases, []), (seg_times[0][0], seg_times[-1][1]))]
    for ws, (a, b) in groups:
        tot = sum(syl(w) for w in ws)
        t = a
        for w in ws:
            d = (b - a) * syl(w) / tot
            words.append([round(t, 3), round(t + d, 3), w.strip(".,!?")])
            t += d
    out.append({"n": n, "text": text, "start": round(start, 3), "dur": round(T - start, 3), "words": words})
    pieces.append(("gap", GAP_LINE))
    T += GAP_LINE

gap_files = {}
lst = []
for p in pieces:
    if isinstance(p, tuple):
        g = p[1]
        if g not in gap_files:
            gf = os.path.join(tmp, f"gap_{int(g * 1000)}.wav")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", f"{g}", gf], check=True)
            gap_files[g] = gf
        lst.append(gap_files[g])
    else:
        lst.append(p)
cl = os.path.join(tmp, "concat.txt")
open(cl, "w", encoding="utf-8").write("\n".join(f"file '{x}'" for x in lst))
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", cl, "-c:a", "pcm_s16le", os.path.join(D, "narration.wav")], check=True)
json.dump(out, open(os.path.join(D, "timing.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("TOTAL", round(T, 2))
