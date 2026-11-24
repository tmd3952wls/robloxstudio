"""목소리 + 배경음(QKThr.mp4 소리만) + 효과음을 영상 타임라인(2900프레임)에 맞춰 믹스.

사용법 (earshot 가상환경 파이썬): <venv>/python make_mix.py
출력: sfx/*.wav, mix.wav (-14 LUFS, -1 dBTP), sfx_placed.json
"""
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
from sfx_cues import CUES  # noqa: E402

SR = 48000
BGM_SRC = os.path.join(os.path.expanduser("~"), "Desktop", "haru.mp4")
cf = json.load(open(os.path.join(D, "cut_frames.json")))
total = cf["total"] / 30.0
design = {int(l.split("\t")[0]): float(l.split("\t")[1]) for l in open(os.path.join(D, "script.tsv"), encoding="utf-8").read().strip("\n").split("\n")}
KOP = 129 / sum(cf["count"][:4])          # 오프닝 1~4컷: 연출 시각 g -> 실제 g / KOP


RT = json.load(open(os.path.join(D, "retime.json"))) if os.path.exists(os.path.join(D, "retime.json")) else None
if RT:
    total = RT["total_new"]


def remap(t):
    """기존 영상 시각 -> 새 음성에 맞춘 시각 (문장 시작 대응점 사이 선형)"""
    if not RT:
        return t
    A = RT["anchors"]
    for (o0, n0), (o1, n1) in zip(A, A[1:]):
        if t <= o1:
            return n0 + (t - o0) * (n1 - n0) / max(1e-6, o1 - o0)
    return A[-1][1]


def when(cut, t):
    if cut <= 4:
        return remap(t / KOP)
    n = cf["count"][cut - 1]
    k = design[cut] * 30 / n
    return remap(cf["start"][cut - 1] / 30 + t / k)


def loudnorm(src, dst, lufs, extra=None):
    af = f"loudnorm=I={lufs}:TP=-2:LRA=20"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src]
    if extra:
        af = extra + "," + af
    cmd += ["-af", af, "-ar", str(SR), "-ac", "1", dst]
    subprocess.run(cmd, check=True)


def read(path):
    a, sr = sf.read(path, dtype="float32", always_2d=True)
    a = a.mean(axis=1)
    assert sr == SR, (path, sr)
    return a


N = int(round(total * SR))
mix = np.zeros(N, dtype=np.float32)

# 1) 목소리 -16 LUFS
loudnorm(os.path.join(D, "narration.wav"), os.path.join(D, "_voice.wav"), -16)
v = read(os.path.join(D, "_voice.wav"))
mix[:min(N, len(v))] += v[:N]

# 2) 배경음: haru.mp4 소리를 원래 속도로 앞에서부터 영상 길이만큼, 목소리보다 약 13 dB 아래, 끝 2.5초 페이드아웃
loudnorm(BGM_SRC, os.path.join(D, "_bgm.wav"), -29, extra=f"atrim=0:{total:.3f},asetpts=N/SR/TB,afade=t=out:st={total - 2.5:.2f}:d=2.5")
b = read(os.path.join(D, "_bgm.wav"))
mix[:min(N, len(b))] += b[:N]

# 3) 효과음
os.makedirs(os.path.join(D, "sfx"), exist_ok=True)
EAR = sys.executable
placed = []
for i, (cut, t, sid, opt, db, align) in enumerate(CUES):
    out = os.path.join(D, "sfx", f"{i:03d}_{sid.replace('/', '_')}.wav")
    cmd = [EAR, "-m", "earshot", "sfx", "render", sid, "-o", out, "--json"]
    for k2 in ("dur", "apex", "pitch"):
        if k2 in opt:
            cmd += [f"--{k2}", str(opt[k2])]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.exists(out):
        print("FAIL", sid, r.stderr.strip()[-300:])
        continue
    try:
        info = json.loads(r.stdout[r.stdout.index("{"):])
    except Exception:
        info = {}
    a, sr = sf.read(out, dtype="float32", always_2d=True)
    a = a.mean(axis=1)
    if sr != SR:
        tmp = out.replace(".wav", "_48k.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", out, "-ar", str(SR), tmp], check=True)
        a = read(tmp)
    meta = info.get("meta", {})
    peak_s, onset_s = float(meta.get("peak_s", 0.0)), float(meta.get("onset_s", 0.0))
    if "checks:" in info.get("summary", ""):
        print("WARN", sid, info["summary"].split("checks:")[1][:160])
    at = when(cut, t) - (peak_s if align == "peak" else onset_s)
    at = max(0.0, at)
    g = 10 ** (db / 20) / max(1e-6, float(np.abs(a).max()))
    i0 = int(at * SR)
    seg = a[: max(0, min(len(a), N - i0))] * g
    mix[i0:i0 + len(seg)] += seg
    placed.append({"cut": cut, "sound": sid, "time": round(at, 3), "db": db})

json.dump(placed, open(os.path.join(D, "sfx_placed.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
sf.write(os.path.join(D, "_mix_raw.wav"), mix, SR, subtype="FLOAT")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(D, "_mix_raw.wav"), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), "-ac", "2",
                os.path.join(D, "mix.wav")], check=True)
print("MIX", round(total, 2), "s, sfx", len(placed), "/", len(CUES))
