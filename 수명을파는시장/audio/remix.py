"""이미 만든 효과음(sfx/*.wav)과 배치(sfx_placed.json)를 재사용해 다시 믹스. earshot 없이 동작.
사용: python remix.py <bgm_lufs>   (목소리 -16 LUFS 기준; -26.5 = 목소리의 약 30%)
"""
import glob
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

D = os.path.dirname(os.path.abspath(__file__))
SR = 48000
TOTAL = 4016 / 30.0
BGM_LUFS = float(sys.argv[1]) if len(sys.argv) > 1 else -26.5
BGM_SRC = os.path.join(os.path.expanduser("~"), "Desktop", "haru.mp4")


def loudnorm(src, dst, lufs, extra=None):
    af = f"loudnorm=I={lufs}:TP=-2:LRA=20"
    if extra:
        af = extra + "," + af
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af", af, "-ar", str(SR), "-ac", "1", dst], check=True)


def read(path):
    a, sr = sf.read(path, dtype="float32", always_2d=True)
    a = a.mean(axis=1)
    if sr != SR:
        tmp = os.path.join(D, "_tmp48k.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-ar", str(SR), tmp], check=True)
        a, _ = sf.read(tmp, dtype="float32", always_2d=True)
        a = a.mean(axis=1)
    return a


N = int(round(TOTAL * SR))
mix = np.zeros(N, dtype=np.float32)
loudnorm(os.path.join(D, "narration.wav"), os.path.join(D, "_voice.wav"), -16)
v = read(os.path.join(D, "_voice.wav"))
mix[:min(N, len(v))] += v[:N]
loudnorm(BGM_SRC, os.path.join(D, "_bgm.wav"), BGM_LUFS,
         extra=f"atrim=0:{TOTAL:.3f},asetpts=N/SR/TB,afade=t=in:d=0.6,afade=t=out:st={TOTAL - 2.5:.2f}:d=2.5")
b = read(os.path.join(D, "_bgm.wav"))
mix[:min(N, len(b))] += b[:N]

placed = json.load(open(os.path.join(D, "sfx_placed.json"), encoding="utf-8"))
files = sorted(f for f in glob.glob(os.path.join(D, "sfx", "*.wav")) if not f.endswith("_48k.wav"))
assert len(files) == len(placed), (len(files), len(placed))
for f, p in zip(files, placed):
    assert p["sound"].replace("/", "_") in os.path.basename(f), (f, p)
    a = read(f)
    g = 10 ** (p["db"] / 20) / max(1e-6, float(np.abs(a).max()))
    i0 = int(p["time"] * SR)
    seg = a[: max(0, min(len(a), N - i0))] * g
    mix[i0:i0 + len(seg)] += seg
sf.write(os.path.join(D, "_mix_raw.wav"), mix, SR, subtype="FLOAT")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(D, "_mix_raw.wav"), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                "-ar", str(SR), "-ac", "2", os.path.join(D, "mix.wav")], check=True)
print("REMIX bgm", BGM_LUFS, "sfx", len(placed))
