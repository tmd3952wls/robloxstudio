"""25번 줄 '네 시간을' -> '니 시간을' 교체 (같은 자리, 같은 길이 안에). 타이밍 이동 없음."""
import json, os, shutil, subprocess
import numpy as np
import soundfile as sf

D = os.path.dirname(os.path.abspath(__file__))
SR = 48000
nar = os.path.join(D, "narration.wav")
bak = os.path.join(D, "fish", "re", "narration_before_l25.wav")
if not os.path.exists(bak):
    shutil.copy(nar, bak)
a, sr = sf.read(bak, dtype="float32")
assert sr == SR
tmp = os.path.join(D, "fish", "re", "_l25.wav")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(D, "fish", "re", "l25_t1.mp3"), "-ar", str(SR), "-ac", "1", tmp], check=True)
b, _ = sf.read(tmp, dtype="float32")
seg = b[int(2.39 * SR):int(3.70 * SR)].copy()
f = int(0.012 * SR)
seg[:f] *= np.linspace(0, 1, f)
seg[-f:] *= np.linspace(1, 0, f)
w0, w1 = int(42.17 * SR), int(43.56 * SR)
old = a[w0:w1]
rms = lambda x: float(np.sqrt(np.mean(x[np.abs(x) > 0.01] ** 2)))
g = rms(old) / rms(seg)
out = a.copy()
fo = int(0.01 * SR)
out[w0:w0 + fo] *= np.linspace(1, 0, fo)
out[w0 + fo:w1] = 0.0
p = int(42.22 * SR)
out[p:p + len(seg)] += seg * g
assert p + len(seg) < w1, (len(seg) / SR)
sf.write(nar, out, SR, subtype="PCM_16")
print("seg", round(len(seg) / SR, 3), "gain", round(g, 3))

tj = os.path.join(D, "timing.json")
T = json.load(open(tj, encoding="utf-8"))
for l in T:
    if l["n"] == 25:
        l["text"] = "니 시간을 전부 사겠다."
        l["words"] = [[42.22, 42.68, "니 시간을"], [42.68, 43.02, "전부"], [43.02, 43.46, "사겠다"]]
json.dump(T, open(tj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for fn in ("script.tsv", "fish_script.txt"):
    p2 = os.path.join(D, fn)
    if os.path.exists(p2):
        s = open(p2, encoding="utf-8").read()
        if "네 시간을 전부 사겠다" in s:
            open(p2, "w", encoding="utf-8").write(s.replace("네 시간을 전부 사겠다", "니 시간을 전부 사겠다"))
            print("text fixed", fn)
