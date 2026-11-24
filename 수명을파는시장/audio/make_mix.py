"""목소리 + 배경음(바탕화면 haru.mp4 소리) + 효과음(earshot 사운드 뱅크) 믹스.
사용: <earshot venv>/python make_mix.py
출력: sfx/*.wav, mix.wav (-14 LUFS), sfx_placed.json
"""
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

D = os.path.dirname(os.path.abspath(__file__))
SR = 48000
BGM_SRC = os.path.join(os.path.expanduser("~"), "Desktop", "haru.mp4")
TL = {e["n"]: e["start"] for e in json.load(open(os.path.join(D, "timing.json"), encoding="utf-8"))}
TOTAL = 4016 / 30.0


def L(n, dt=0.0):
    return TL[n] + dt


# (시각(초), 소리 id, 옵션, dB, 정렬)
CUES = []
for i in range(7):                                   # 도입: 시계 초침 똑딱
    CUES.append((0.25 + i * 1.0, "tap/knuckle" if i % 2 == 0 else "hover_tick/mid", {}, -19 if i % 2 == 0 else -22, "onset"))
CUES += [
    (L(3, 2.0), "cut_hit/sub", {}, -13, "onset"),               # 멈춰
    (L(4, 0.9), "whoosh_big/gust", {"dur": 2.8, "apex": 1.2}, -17, "peak"),
    (L(6, 0.1), "mallet/marimba", {}, -18, "onset"),
    (L(7, 0.1), "mallet/marimba", {"pitch": "A4"}, -18, "onset"),
    (L(8, 0.1), "mallet/marimba", {"pitch": "C5"}, -18, "onset"),
    (L(9, 0.6), "pro_shimmer/m1", {}, -16, "onset"),            # 숫자가 건너감
    (L(10, 0.0), "swish/soft", {}, -18, "peak"),
    (L(11, 0.8), "pro_shimmer/m0", {}, -19, "onset"),
    (L(13, 1.0), "ui_pop/fall", {}, -16, "onset"),
    (L(14, 0.05), "mallet/celesta", {"pitch": "E6"}, -15, "onset"),   # 하루 등장
    (L(17, 0.0), "reverse_swell/dark", {}, -18, "peak"),
    (L(18, 2.15), "mallet/up4", {}, -15, "onset"),              # 24시간으로 돌아옴
    (L(19, 0.1), "notify/m3", {"pitch": "A3", "dur": 2.5}, -19, "onset"),
    (L(22, 0.2), "ui_pop/soft", {}, -18, "onset"),
    (L(24, 0.0), "cut_hit/punch", {}, -15, "onset"),            # 부자 등장
    (L(26, 0.2), "pro_shimmer/m2", {}, -17, "onset"),
    (L(31, 1.2), "whoosh_big/deep", {}, -18, "peak"),
    (L(33, 0.0), "notify/m3", {"pitch": "A3", "dur": 2.5}, -13, "onset"),   # 자정 종
    (L(33, 0.45), "notify/m3", {"pitch": "A3", "dur": 2.5}, -15, "onset"),
    (L(33, 0.9), "notify/m3", {"pitch": "A3", "dur": 2.5}, -16, "onset"),
    (L(34, 0.1), "swipe/cloth", {}, -20, "peak"),               # 문
    (L(35, 0.7), "tap/soft", {}, -17, "onset"),                 # 손이 닿음
    (L(36, 0.0), "pro_shimmer/m4", {}, -15, "onset"),
    (L(36, 0.2), "riser/swell", {"dur": 2.6}, -20, "onset"),
    (L(38, 0.35), "cut_hit/air", {}, -16, "onset"),             # 눈 뜸
    (L(40, 0.3), "mallet/celesta", {"pitch": "G5"}, -17, "onset"),
    (L(41, 0.9), "swish/soft", {}, -16, "peak"),                # 소매 내림
    (L(42, 0.4), "reverse_swell/dark", {}, -16, "peak"),
    (L(44, 0.0), "cut_hit/sub", {}, -12, "onset"),              # 오 분
    (L(47, 0.0), "shimmer/m4", {}, -19, "onset"),               # 회상
    (L(49, 0.05), "cut_hit/sub", {}, -14, "onset"),             # 영
    (L(51, 1.2), "pro_shimmer/m1", {}, -16, "onset"),
    (L(53, 0.0), "notify/m3", {"pitch": "A3", "dur": 2.0}, -20, "onset"),
    (L(54, 0.0), "notify/m3", {"pitch": "A3", "dur": 2.0}, -21, "onset"),
    (L(56, 0.3), "downlifter/air_fall", {}, -19, "onset"),      # 긴 숫자가 줄어듦
    (L(57, 0.3), "tap/finger", {}, -16, "onset"),
    (L(59, 0.3), "swish/soft", {}, -17, "peak"),
    (L(61, 0.1), "downlifter/air_fall", {}, -17, "onset"),
    (L(62, 0.05), "knock/wood", {}, -13, "onset"),              # 문밖 소란
    (L(62, 0.25), "knock/wood", {}, -14, "onset"),
    (L(62, 0.45), "knock/wood", {}, -15, "onset"),
    (L(63, 0.1), "cut_hit/punch", {}, -14, "onset"),
    (L(64, 0.6), "whoosh_big/deep", {}, -20, "peak"),
    (L(68, 0.5), "swish/soft", {}, -17, "peak"),                # 소매 걷음
    (L(69, 0.7), "pro_shimmer/m1", {}, -15, "onset"),
    (L(70, 0.0), "mallet/glock", {}, -14, "onset"),             # 일 분
    (L(71, 0.25), "pro_shimmer/m2", {}, -16, "onset"),
    (L(72, 0.0), "mallet/glock", {"pitch": "F6"}, -14, "onset"),
    (L(73, 0.2), "pro_shimmer/m3", {}, -16, "onset"),
    (L(74, 0.0), "mallet/up4", {}, -14, "onset"),
    (L(75, 0.8), "whoosh_big/gust", {"dur": 2.0, "apex": 0.9}, -18, "peak"),
    (L(76, 1.3), "pro_shimmer/m2", {}, -14, "onset"),
    (L(77, 0.0), "riser/swell", {"dur": 2.6}, -18, "onset"),
    (L(78, 0.35), "mallet/up4", {"pitch": "E6"}, -12, "onset"),
    (L(79, 0.1), "notify/m2", {}, -20, "onset"),                # 아침
    (L(81, 0.4), "mallet/celesta", {"pitch": "E6"}, -15, "onset"),
    (L(82, 1.3), "mallet/up4", {}, -16, "onset"),
    (L(84, 0.6), "pro_shimmer/m1", {}, -16, "onset"),
    (L(84, 2.1), "notify/m0", {"dur": 2.0}, -18, "onset"),
]


def loudnorm(src, dst, lufs, extra=None):
    af = f"loudnorm=I={lufs}:TP=-2:LRA=20"
    if extra:
        af = extra + "," + af
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af", af, "-ar", str(SR), "-ac", "1", dst], check=True)


def read(path):
    a, sr = sf.read(path, dtype="float32", always_2d=True)
    a = a.mean(axis=1)
    if sr != SR:
        tmp = path.replace(".wav", "_48k.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-ar", str(SR), tmp], check=True)
        a, _ = sf.read(tmp, dtype="float32", always_2d=True)
        a = a.mean(axis=1)
    return a


N = int(round(TOTAL * SR))
mix = np.zeros(N, dtype=np.float32)
loudnorm(os.path.join(D, "narration.wav"), os.path.join(D, "_voice.wav"), -16)
v = read(os.path.join(D, "_voice.wav"))
mix[:min(N, len(v))] += v[:N]
loudnorm(BGM_SRC, os.path.join(D, "_bgm.wav"), -23.0, extra=f"atrim=0:{TOTAL:.3f},asetpts=N/SR/TB,afade=t=in:d=0.6,afade=t=out:st={TOTAL - 2.5:.2f}:d=2.5")
b = read(os.path.join(D, "_bgm.wav"))
mix[:min(N, len(b))] += b[:N]

os.makedirs(os.path.join(D, "sfx"), exist_ok=True)
placed = []
for i, (t, sid, opt, db, align) in enumerate(CUES):
    out = os.path.join(D, "sfx", f"{i:03d}_{sid.replace('/', '_')}.wav")
    cmd = [sys.executable, "-m", "earshot", "sfx", "render", sid, "-o", out, "--json"]
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
    a = read(out)
    meta = info.get("meta", {})
    peak_s, onset_s = float(meta.get("peak_s", 0.0)), float(meta.get("onset_s", 0.0))
    at = max(0.0, t - (peak_s if align == "peak" else onset_s))
    g = 10 ** (db / 20) / max(1e-6, float(np.abs(a).max()))
    i0 = int(at * SR)
    seg = a[: max(0, min(len(a), N - i0))] * g
    mix[i0:i0 + len(seg)] += seg
    placed.append({"sound": sid, "time": round(at, 3), "db": db})
json.dump(placed, open(os.path.join(D, "sfx_placed.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
sf.write(os.path.join(D, "_mix_raw.wav"), mix, SR, subtype="FLOAT")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(D, "_mix_raw.wav"), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), "-ac", "2",
                os.path.join(D, "mix.wav")], check=True)
print("MIX", round(TOTAL, 2), "s, sfx", len(placed), "/", len(CUES))
