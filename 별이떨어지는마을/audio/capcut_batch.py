"""script.tsv 문장을 CapCut '활기찬 바리톤'(1.1x)으로 자동 생성 (60SEC_YOUTUBE_AUTO_SHORT 의 자동 도구 사용).

사용: python -X utf8 capcut_batch.py [시작배치] [끝배치]   (배치당 6문장)
결과: 60SEC_YOUTUBE_AUTO_SHORT/assets/voices/vibrant_baritone/<md5>.wav  -> capcut/line_XX.wav 로 복사
"""
import json
import shutil
import sys
from pathlib import Path

D = Path(__file__).resolve().parent
AUTO = Path(r"C:\Users\tmd39\Desktop\60SEC_YOUTUBE_AUTO_SHORT")
sys.path.insert(0, str(AUTO))
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
from shorts.common import ASSETS, JOBS  # noqa: E402
from tools.capcut_voice import key  # noqa: E402
from shorts.textnorm import tts_say  # noqa: E402
from tools.capcut_auto_tts import run_auto_tts  # noqa: E402

rows = [l.split("\t") for l in (D / "script.tsv").read_text(encoding="utf-8").strip("\n").split("\n")]
lines = [(int(r[0]), r[2].strip()) for r in rows if len(r) > 2 and r[2].strip()]
uniq = []
for _, t in lines:
    if t not in uniq:
        uniq.append(t)
B = 6
batches = [uniq[i:i + B] for i in range(0, len(uniq), B)]
a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
b = int(sys.argv[2]) if len(sys.argv) > 2 else len(batches) - 1
VO = ASSETS / "voices" / "vibrant_baritone"
for bi in range(a, b + 1):
    job = f"byeol_b{bi:02d}"
    (JOBS / job).mkdir(parents=True, exist_ok=True)
    edl = {"items": [{"type": "narration", "text": t} for t in batches[bi]]}
    (JOBS / job / "edl.json").write_text(json.dumps(edl, ensure_ascii=False), encoding="utf-8")
    print(f"== 배치 {bi}/{len(batches) - 1}")
    try:
        run_auto_tts(job, "edl.json", voice="vibrant_baritone", speed=1.1)
    except Exception as e:  # 한 배치 실패해도 다음 진행
        print("  배치 실패:", e)

out = D / "capcut"
out.mkdir(exist_ok=True)
miss = []
for n, t in lines:
    src = VO / f"{key(tts_say(t))}.wav"
    if src.exists():
        shutil.copyfile(src, out / f"line_{n:02d}.wav")
    else:
        miss.append(n)
print("없는 줄:", miss)
