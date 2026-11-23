"""Fish Audio 테이크 -> 숨 구간 없는 narration.wav + timing.json

사용: fish_build.py t1.mp3 [--dry]   (fish/align_<take>.json 필요)
- 문장 경계: whisper 정렬 사이에서 가장 조용한 지점
- 문장 앞뒤 무음 제거, 문장 안 쉼(>0.12s)은 0.10s 로, 문장 사이 0.02s
--dry: 길이만 출력 (파일 안 씀)
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

D = Path(__file__).resolve().parent
SR = 48000
GAP_IN, GAP_LINE = 0.10, 0.02
src = D / "fish" / sys.argv[1]
dry = "--dry" in sys.argv
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
x = np.frombuffer(pcm, dtype=np.float32).copy()
dur = len(x) / SR
al = json.load(open(D / "fish" / f"align_{src.stem}.json", encoding="utf-8"))
txt = {int(l.split("\t")[0]): l.split("\t")[2] for l in (D / "script.tsv").read_text(encoding="utf-8").strip("\n").split("\n")}

hop = SR // 100
rms = np.sqrt(np.array([np.mean(x[i:i + hop] ** 2) + 1e-12 for i in range(0, len(x) - hop, hop)]))
db = 20 * np.log10(rms)
silent = db < -40


def quiet_point(a, b):
    i0, i1 = max(0, int(a * 100)), min(len(db) - 1, int(b * 100))
    if i1 <= i0:
        return (a + b) / 2
    return (i0 + int(np.argmin(db[i0:i1 + 1]))) / 100


cuts = [0.0]
for i in range(len(al) - 1):
    a, b = al[i]["t1"], al[i + 1]["t0"]
    cuts.append(quiet_point(min(a, b) - 0.10, max(a, b) + 0.10))
cuts.append(dur)


def voiced_segments(a, b):
    i0, i1 = int(a * 100), min(len(silent), int(b * 100))
    segs, cur, run, last = [], None, 0, 0
    for i in range(i0, i1):
        if not silent[i]:
            if cur is None:
                cur = i
            run, last = 0, i
        elif cur is not None:
            run += 1
            if run >= 12:
                segs.append((cur, last + 1))
                cur, run = None, 0
    if cur is not None:
        segs.append((cur, last + 1))
    return [(max(a, s / 100 - 0.03), min(b, e / 100 + 0.03)) for s, e in segs if e - s >= 3]


def fade(p):
    n1, n2 = min(len(p), int(0.008 * SR)), min(len(p), int(0.012 * SR))
    p = p.copy()
    p[:n1] *= np.linspace(0, 1, n1)
    p[len(p) - n2:] *= np.linspace(1, 0, n2)
    return p


parts, timing, T = [], [], 0.0
for k, e in enumerate(al):
    a, b = cuts[k], cuts[k + 1]
    segs = voiced_segments(a, b) or [(a, b)]
    start, mapping = T, []
    for j, (s0, s1) in enumerate(segs):
        p = fade(x[int(s0 * SR):int(s1 * SR)])
        parts.append(p)
        mapping.append((s0, s1, T))
        T += len(p) / SR
        if j < len(segs) - 1:
            parts.append(np.zeros(int(GAP_IN * SR), np.float32))
            T += GAP_IN

    def remap(t):
        for s0, s1, n0 in mapping:
            if t <= s1:
                return n0 + max(0.0, t - s0)
        s0, s1, n0 = mapping[-1]
        return n0 + (s1 - s0)

    words = [[round(remap(w0), 3), round(remap(w1), 3), w] for w0, w1, w in e["words"]]
    timing.append({"n": e["n"], "text": txt[e["n"]], "start": round(start, 3), "dur": round(T - start, 3), "words": words})
    parts.append(np.zeros(int(GAP_LINE * SR), np.float32))
    T += GAP_LINE

voice = np.concatenate(parts)
print(src.name, "원본", round(dur, 2), "s -> 숨 제거", round(len(voice) / SR, 2), "s")
if not dry:
    sf.write(D / "narration.wav", voice, SR, subtype="PCM_16")
    json.dump(timing, open(D / "timing.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("narration.wav, timing.json 저장")
