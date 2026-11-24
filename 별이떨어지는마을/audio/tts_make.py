"""대사별 TTS(edge-tts, 한국어 남성 InJoon, 1.1배속, 낮은 음높이) + 단어 시각 -> 앞뒤 무음을 잘라 숨 쉬는 구간 없이 이어 붙임.

출력: tts/line_XX.mp3, tts_lines.json (컷별 길이·단어 시각), narration.wav (전체 이어 붙인 목소리)
사용법: python tts_make.py
"""
import asyncio
import json
import os
import subprocess

import edge_tts

D = os.path.dirname(os.path.abspath(__file__))
VOICE, RATE, PITCH = "ko-KR-InJoonNeural", "+10%", "-8Hz"
LINES = [(l.split("\t") + ["", ""])[:3] for l in open(os.path.join(D, "script.tsv"), encoding="utf-8").read().strip("\n").split("\n")]
os.makedirs(os.path.join(D, "tts"), exist_ok=True)


async def one(n, text):
    mp3 = os.path.join(D, "tts", f"line_{n:02d}.mp3")
    words = []
    com = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH, boundary="WordBoundary")
    with open(mp3, "wb") as fh:
        async for ch in com.stream():
            if ch["type"] == "audio":
                fh.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7, ch["text"]))
    return mp3, words


async def main():
    out = []
    for n, d0, text in LINES:
        n = int(n)
        if not text.strip():
            out.append({"n": n, "text": "", "words": []})
            continue
        mp3, words = await one(n, text)
        out.append({"n": n, "text": text, "mp3": mp3, "words": words})
        print(n, text, len(words))
    # 앞뒤 무음 자르기: 첫 단어 시작 0.03초 전 ~ 마지막 단어 끝 0.05초 뒤
    t = 0.0
    parts = []
    for e in out:
        if not e["words"]:
            continue
        a = max(0.0, e["words"][0][0] - 0.03)
        b = e["words"][-1][1] + 0.05
        wav = e["mp3"].replace(".mp3", ".wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", e["mp3"], "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-ar", "48000", "-ac", "1", wav], check=True)
        e["clip"] = (a, b)
        e["start"] = t
        e["dur"] = b - a
        e["words_abs"] = [(t + w0 - a, t + w1 - a, w) for w0, w1, w in e["words"]]
        t += b - a
        parts.append(wav)
    lst = os.path.join(D, "tts", "concat.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        fh.write("\n".join(f"file '{p}'" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", os.path.join(D, "narration.wav")], check=True)
    json.dump(out, open(os.path.join(D, "tts_lines.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("TOTAL", round(t, 2))


asyncio.run(main())


