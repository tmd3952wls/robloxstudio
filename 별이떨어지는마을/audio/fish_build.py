"""Fish Audio(보이스1·Drama 3·1.0x) 녹음 -> 숨 구간 없는 narration.wav + timing.json + retime.json

- 문장 경계: whisper 정렬(fish/align.json) 사이에서 가장 조용한 지점
- 문장 앞뒤 무음 제거, 문장 안 쉼(>0.12s)은 0.10s 로, 문장 사이 0.02s
- retime.json: 기존 영상 시각 -> 새 시각 대응점 (문장 시작마다). 장면을 새 음성에 맞추는 데 씀
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

D = Path(__file__).resolve().parent
SR = 48000
GAP_IN, GAP_LINE = 0.10, 0.02
src = D / "fish" / (sys.argv[1] if len(sys.argv) > 1 else "b.mp3")
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
x = np.frombuffer(pcm, dtype=np.float32).copy()
dur = len(x) / SR
al = json.load(open(D / "fish" / "align.json", encoding="utf-8"))
old = json.load(open(D / "timing_edge.json", encoding="utf-8"))
total_old = json.load(open(D / "cut_frames.json"))["total"] / 30.0

# 10ms 에너지
hop = SR // 100
rms = np.sqrt(np.array([np.mean(x[i:i + hop] ** 2) + 1e-12 for i in range(0, len(x) - hop, hop)]))
db = 20 * np.log10(rms)
silent = db < -40


def quiet_point(a, b):
    i0, i1 = max(0, int(a * 100)), min(len(db) - 1, int(b * 100))
    if i1 <= i0:
        return (a + b) / 2
    return (i0 + int(np.argmin(db[i0:i1 + 1]))) / 100


# 문장 경계
cuts = [0.0]
for i in range(len(al) - 1):
    a, b = al[i]["t1"], al[i + 1]["t0"]
    lo, hi = min(a, b) - 0.10, max(a, b) + 0.10
    cuts.append(quiet_point(lo, hi))
cuts.append(dur)


def voiced_segments(a, b):
    """[a,b] 안의 소리 구간 (무음 0.12s 이상으로 나뉨), 앞뒤 무음 제거, 가장자리 30ms 여유"""
    i0, i1 = int(a * 100), int(b * 100)
    segs, cur = [], None
    run = 0
    for i in range(i0, i1):
        if not silent[i]:
            if cur is None:
                cur = i
            run = 0
            last = i
        else:
            if cur is not None:
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


out_parts, timing, T = [], [], 0.0
newstart = {}
for k, e in enumerate(al):
    a, b = cuts[k], cuts[k + 1]
    segs = voiced_segments(a, b) or [(a, b)]
    start = T
    mapping = []   # (원래 t0, t1, 새 t0)
    for j, (s0, s1) in enumerate(segs):
        p = fade(x[int(s0 * SR):int(s1 * SR)])
        out_parts.append(p)
        mapping.append((s0, s1, T))
        T += len(p) / SR
        if j < len(segs) - 1:
            out_parts.append(np.zeros(int(GAP_IN * SR), np.float32))
            T += GAP_IN

    def remap(t):
        for s0, s1, n0 in mapping:
            if t <= s1:
                return n0 + max(0.0, t - s0)
        s0, s1, n0 = mapping[-1]
        return n0 + (s1 - s0)

    words = [[round(remap(w0), 3), round(remap(w1), 3), w] for w0, w1, w in e["words"]]
    timing.append({"n": e["n"], "start": round(start, 3), "dur": round(T - start, 3), "words": words})
    newstart[e["n"]] = start
    out_parts.append(np.zeros(int(GAP_LINE * SR), np.float32))
    T += GAP_LINE

# 빈 줄(55, 56) 포함한 timing.json (기존 형식)
txt = {int(l.split("\t")[0]): (l.split("\t") + ["", ""])[2] for l in (D / "script.tsv").read_text(encoding="utf-8").strip("\n").split("\n")}
full = []
for o in old:
    n = o["n"]
    t = next((t for t in timing if t["n"] == n), None)
    if t:
        full.append({"n": n, "text": txt[n], **t})
    else:
        prev = full[-1]
        full.append({"n": n, "text": "", "start": round(prev["start"] + prev["dur"], 3), "dur": 0.0, "words": []})

voice = np.concatenate(out_parts)
tail_old = total_old - max(o["start"] + o["dur"] for o in old)
total_new = round(len(voice) / SR + max(0.6, tail_old), 3)
sf.write(D / "narration.wav", voice, SR, subtype="PCM_16")
json.dump(full, open(D / "timing.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
anchors = [[0.0, 0.0]] + [[o["start"], newstart[o["n"]]] for o in old if o["n"] in newstart and o["n"] != 1] + [[total_old, total_new]]
json.dump({"anchors": anchors, "total_old": total_old, "total_new": total_new}, open(D / "retime.json", "w"), indent=1)
print("목소리", round(len(voice) / SR, 2), "s / 영상", total_new, "s (기존", round(total_old, 2), ")")
r = [(o["n"], round(full[i]["dur"] / max(0.01, o["dur"]), 2)) for i, o in enumerate(old) if o["dur"] > 0]
print("문장 길이 비 (새/기존) 최소·최대:", min(r, key=lambda z: z[1]), max(r, key=lambda z: z[1]))
