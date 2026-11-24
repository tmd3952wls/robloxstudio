"""한 번에 한 단어(어절)만 나오는 자막 (ASS). 목소리 시각(timing.json)에 맞춤.

출력: subs.ass  (1080x1920, 화면 가운데보다 조금 아래, 쇼츠 버튼 영역을 피함)
"""
import json
import os

D = os.path.dirname(os.path.abspath(__file__))
lines = json.load(open(os.path.join(D, "timing.json"), encoding="utf-8"))


def ts(t):
    t = max(0.0, t)
    h, m = int(t // 3600), int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,Jua,120,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,3.5,0,5,80,80,0,1
Style: Shadow,Jua,120,&H1A000000,&H1A000000,&H1A000000,&H00000000,0,0,0,0,100,100,0,0,1,3.5,0,5,80,80,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
# 문법 덩어리(주어·목적어·부사어·서술어 단위)로 묶기: sub_chunks.txt
CH = {}
for l in open(os.path.join(D, "sub_chunks.txt"), encoding="utf-8"):
    if l.strip() and not l.startswith("#"):
        n, s = l.rstrip("\n").split("\t")
        CH[int(n)] = s.split("|")
# 강조 자막: 크게 + 노랑(신비·발견·희망) / 빨강(금지·충격·슬픔)
HL = {
    (2, "딱 하룻밤"): "y", (3, "떨어져"): "y", (10, "등불이"): "y", (14, "딱 하나야"): "y",
    (15, "절대"): "r", (15, "열지 말 것"): "r", (17, "이상한 게"): "y", (19, "같은 쪽 벽에"): "y",
    (20, "전부"): "r", (22, "하루야"): "y", (27, "제일 쓸모없는"): "r", (30, "아니야"): "y",
    (31, "잃은 거지"): "y", (38, "울고 있었어"): "r", (42, "비어 있었어"): "r", (44, "온 거였어"): "y",
    (48, "가뒀던 거야"): "r", (49, "안 남았어"): "r", (52, "깼어"): "r", (54, "열었어"): "y",
    (60, "빛나는"): "y", (66, "강처럼"): "y", (68, "켜졌어"): "y", (76, "알려주면 돼"): "y",
}
COL = {"y": r"\c&H0000E1FF&", "r": r"\c&H002E2EFF&"}
BIG = 138
words = []
for e in lines:
    ws = [w for w in e["words"] if w[2]]
    if not ws:
        continue
    i = 0
    for c in CH[e["n"]]:
        k = len(c.split())
        part = ws[i:i + k]
        got = " ".join(w[2] for w in part)
        assert got.replace(" ", "") == c.replace(" ", ""), (e["n"], got, c)
        words.append((part[0][0], part[-1][1], c, HL.get((e["n"], c))))
        i += k
    assert i == len(ws), (e["n"], i, len(ws))

SH, BL = 6, 4      # 그림자 거리(px, 대각선 각 축), 번짐
ev = []
for i, (t0, t1, w, hl) in enumerate(words):
    nxt = words[i + 1][0] if i + 1 < len(words) else t1 + 0.3
    end = nxt if nxt - t1 < 0.25 else t1 + 0.12
    # 캡컷 설정: 흰 글자 + 검은 외곽선, 그림자 불투명 90%·부드럽게·오른쪽 아래(-45°)
    # 작게 시작해 커지는 짧은 팝 (0.08초). 강조는 더 크게 튀어나옴
    if hl:
        pop = rf"\fs{BIG}\fscx70\fscy70\t(0,70,\fscx112\fscy112)\t(70,140,\fscx100\fscy100)"
        sh, col = SH + 2, COL[hl]
    else:
        pop, sh, col = r"\fscx80\fscy80\t(0,80,\fscx100\fscy100)", SH, ""
    ev.append(f"Dialogue: 0,{ts(t0)},{ts(end)},Shadow,,0,0,0,,{{\\pos({540 + sh},{1180 + sh})\\blur{BL}{pop}}}{w}")
    ev.append(f"Dialogue: 1,{ts(t0)},{ts(end)},Word,,0,0,0,,{{\\pos(540,1180){pop}{col}}}{w}")
open(os.path.join(D, "subs.ass"), "w", encoding="utf-8-sig").write(head + "\n".join(ev) + "\n")
print("words", len(ev) // 2)
