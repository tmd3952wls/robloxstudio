#!/usr/bin/env bash
# 렌더 프레임 + mix.wav + subs.ass -> 수명을파는시장_최종.mp4
set -e
ROOT="C:/Users/tmd39/Documents/수명을파는시장"
cd "$ROOT/audio"
ffmpeg -y -v error -framerate 30 -start_number 1 -i "$ROOT/blender/frames/f%04d.png" -i mix.wav \
  -vf "subtitles=subs.ass:fontsdir=fonts" -c:v libx264 -crf 17 -preset slow -pix_fmt yuv420p \
  -c:a aac -b:a 256k -shortest -movflags +faststart "$ROOT/수명을파는시장_최종.mp4"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$ROOT/수명을파는시장_최종.mp4"
