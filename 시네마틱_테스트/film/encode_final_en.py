"""본편 최종 인코딩: 전체 프레임 + mix.wav + 자막 + 회상 색바램. 별도 프로세스로 띄울 것.
[영어판] 결과: out/불과물의마을_영어.mp4 (이미 있으면 _1, _2 … 로 새 이름, 덮어쓰지 않음)"""
import os
import subprocess
import sys
import time

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import shotlist as SL

R = os.path.join(D, "..")
A = r"C:\Users\tmd39\Desktop\haru_short\불과물의마을\audio"
F = os.path.join(R, "out", "film", "frames")
last = SL.shots()[-1][2]
dst = os.path.join(R, "out", "불과물의마을_영어.mp4")
k = 1
while os.path.exists(dst):
    dst = os.path.join(R, "out", f"불과물의마을_영어_{k}.mp4")
    k += 1
en = "+".join(f"between(t,{a},{b})" for a, b in SL.flashback_ranges())
vf = (f"eq=saturation=0.45:enable='{en}',colorbalance=rs=0.08:gs=0.03:bs=-0.08:enable='{en}',"
      "subtitles=en/subs.ass:fontsdir=fonts,format=yuv420p")
log = open(os.path.join(R, "out", "film", "encode_final_en.log"), "a", encoding="utf-8")
log.write(time.strftime("%m-%d %H:%M:%S ") + f"start {last} frames -> {dst}\n{vf}\n")
log.flush()
t = time.time()
r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", "30", "-start_number", "1", "-i", os.path.join(F, "f%04d.png"),
                    "-i", "mix.wav", "-frames:v", str(last), "-vf", vf, "-c:v", "libx264", "-crf", "17", "-preset", "slow",
                    "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", dst], cwd=A, stdout=log, stderr=subprocess.STDOUT)
log.write(time.strftime("%m-%d %H:%M:%S ") + f"end exit {r.returncode} {time.time() - t:.0f}s\n")
log.close()
