"""최종 전체 렌더 (B: EEVEE 64, 1080x1920 100%) -> frames/fNNNN.png -> H.264 MP4.
메모리 누적을 막으려고 200프레임마다 Blender 를 새로 띄우고, 이미 있는 프레임은 건너뛴다(중단돼도 다시 실행하면 이어서).
사용: python render_full.py
"""
import os
import subprocess
import sys
import time

D = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(D)
BL = r"C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"
N, CH, SMP = 4016, 200, 64
FOLDER = sys.argv[1] if len(sys.argv) > 1 else "frames"
F_FROM = int(sys.argv[2]) if len(sys.argv) > 2 else 1
F_TO = int(sys.argv[3]) if len(sys.argv) > 3 else None
NO_ENC = "--no-encode" in sys.argv
OUT = os.path.join(D, FOLDER)
LOG = os.path.join(D, "out", "render_full.log")
os.makedirs(OUT, exist_ok=True)


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def done(f):
    p = os.path.join(OUT, f"f{f:04d}.png")
    return os.path.exists(p) and os.path.getsize(p) > 100000


env = dict(os.environ, HQ_SKIP_EXISTING="1")
t0 = time.time()
if F_TO:
    N = F_TO
for f0 in range(F_FROM, N + 1, CH):
    f1 = min(f0 + CH - 1, N)
    for attempt in range(3):
        if all(done(f) for f in range(f0, f1 + 1)):
            break
        log(f"chunk {f0}-{f1} start (try {attempt + 1})")
        with open(os.path.join(D, "out", f"render_{f0:04d}.log"), "w", encoding="utf-8", errors="replace") as lf:
            r = subprocess.run([BL, "-b", os.path.join(D, "market.blend"), "--python", os.path.join(D, "anim_hq.py"), "--",
                                FOLDER, "100", str(SMP), str(f0), str(f1)], stdout=lf, stderr=subprocess.STDOUT, env=env)
        n_ok = sum(done(f) for f in range(F_FROM, N + 1))
        el = time.time() - t0
        log(f"chunk {f0}-{f1} exit {r.returncode}; total {n_ok}/{N}; elapsed {el / 3600:.2f} h")
    if not all(done(f) for f in range(f0, f1 + 1)):
        log(f"chunk {f0}-{f1} FAILED after 3 tries")
        sys.exit(1)

if NO_ENC:
    log("frames done (no encode)")
    sys.exit(0)
log("all frames done; encoding")
mp4 = os.path.join(ROOT, "수명을파는시장_HQ.mp4")
au = os.path.join(ROOT, "audio")
cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", os.path.join(OUT, "f%04d.png"),
       "-i", "mix.wav", "-vf", "ass=subs.ass:fontsdir=fonts", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
       "-profile:v", "high", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "192k", "-shortest", mp4]
r = subprocess.run(cmd, cwd=au)
log(f"encode exit {r.returncode} -> {mp4}")
