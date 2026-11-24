"""fish/b.mp3 를 whisper 단어 시각으로 대본 74문장에 맞춤 -> fish/align.json [{n, t0, t1, words:[[t0,t1,w]]}]
대본 글자열과 인식 글자열을 글자 단위로 정렬(difflib)해 각 대본 어절의 시작·끝 시각을 얻음.
"""
import difflib
import json
import re
import sys
from pathlib import Path

from faster_whisper import WhisperModel

D = Path(__file__).resolve().parent
src = D / "fish" / (sys.argv[1] if len(sys.argv) > 1 else "b.mp3")
rows = [l.split("\t") for l in (D / "script.tsv").read_text(encoding="utf-8").strip("\n").split("\n")]
lines = [(int(r[0]), r[2].strip()) for r in rows if len(r) > 2 and r[2].strip()]

model = WhisperModel("small", device="cpu", compute_type="int8")
import subprocess
import numpy as np
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
audio = np.frombuffer(pcm, dtype=np.float32)
segs, _ = model.transcribe(audio, language="ko", word_timestamps=True, vad_filter=False, beam_size=5,
                           initial_prompt=" ".join(t for _, t in lines)[:800])
rc, rt = [], []          # 인식 글자, 글자별 (t0,t1)
for s in segs:
    for w in s.words:
        cs = re.sub(r"[^가-힣A-Za-z0-9]", "", w.word)
        if not cs:
            continue
        dt = (w.end - w.start) / len(cs)
        for i, c in enumerate(cs):
            rc.append(c)
            rt.append((w.start + i * dt, w.start + (i + 1) * dt))
# 대본 글자 (어절 번호 기록)
sc, sw = [], []
words = []
for n, t in lines:
    for w in t.split():
        cs = re.sub(r"[^가-힣A-Za-z0-9]", "", w)
        words.append((n, w.strip(".,!?"), len(sc), len(sc) + len(cs)))
        sc.extend(cs)
m = difflib.SequenceMatcher(None, sc, rc, autojunk=False)
tm = [None] * len(sc)
for a, b, size in m.get_matching_blocks():
    for k in range(size):
        tm[a + k] = rt[b + k]
matched = sum(1 for x in tm if x)
# 빈 곳은 앞뒤 시각으로 보간
known = [i for i, x in enumerate(tm) if x]
for i in range(len(tm)):
    if tm[i] is None:
        p = max([k for k in known if k < i], default=None)
        q = min([k for k in known if k > i], default=None)
        if p is None:
            tm[i] = (tm[q][0], tm[q][0])
        elif q is None:
            tm[i] = (tm[p][1], tm[p][1])
        else:
            f = (i - p) / (q - p)
            t = tm[p][1] + (tm[q][0] - tm[p][1]) * f
            tm[i] = (t, t)
out = {}
for n, w, a, b in words:
    t0, t1 = tm[a][0], tm[b - 1][1]
    out.setdefault(n, []).append([round(t0, 3), round(t1, 3), w])
res = [{"n": n, "t0": ws[0][0], "t1": ws[-1][1], "words": ws} for n, ws in out.items()]
(D / "fish" / "align.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("글자 일치", matched, "/", len(sc))
for r in res[:5] + res[-3:]:
    print(r["n"], r["t0"], r["t1"], " ".join(w[2] for w in r["words"]))
