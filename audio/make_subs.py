"""한 덩어리씩 나오는 자막 (ASS, 지난 영상과 같은 Jua 스타일). timing.json 단어 시각에 맞춤.
덩어리: 어절 하나, 단 2글자 이하 어절(관형사·수사 등)은 다음 어절과 붙이고, 1글자 의존명사(수·척)는 앞에 붙임.
출력: subs.ass
"""
import json
import os

D = os.path.dirname(os.path.abspath(__file__))
lines = json.load(open(os.path.join(D, "timing.json"), encoding="utf-8"))


def ts(t):
    t = max(0.0, t)
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h}:{m:02d}:{t % 60:05.2f}"


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
# 강조: 노랑(신비·발견·희망) / 빨강(충격·슬픔·멈춤)
HL = {
    (1, "숫자가"): "y", (2, "수명이야"): "r", (3, "멈춰"): "r", (5, "사고팔 수"): "y", (6, "한 시간"): "y", (7, "세 시간"): "y",
    (8, "하루"): "y", (9, "건너가"): "y", (10, "끝까지"): "y", (13, "큰 실례거든"): "r", (15, "이십사"): "y", (16, "딱 하루"): "y",
    (18, "돌아온다는"): "y", (22, "차오르는"): "y", (25, "전부"): "r", (26, "백 년을"): "y", (30, "시간을"): "y", (31, "전부"): "r",
    (33, "열두 번"): "y", (35, "손목에"): "y", (37, "올라가기"): "y", (39, "할머니가"): "y", (44, "오 분"): "r", (46, "들켰네"): "r",
    (49, "영"): "r", (50, "멈출"): "r", (55, "십이 년"): "y", (60, "멈추잖니"): "r", (61, "멈춰야"): "r", (68, "소매를"): "y",
    (70, "일 분"): "y", (72, "일 분"): "y", (74, "일 분씩"): "y", (75, "끝까지"): "y", (76, "그 부자가"): "y", (78, "끝까지"): "y",
    (81, "나눌"): "y", (84, "일 분을"): "y",
}
COL = {"y": r"\c&H0000E1FF&", "r": r"\c&H002E2EFF&"}
BIG = 138


MOD = {"이", "그", "일", "한", "세", "네", "백", "오", "딱", "큰", "긴", "왜", "십이", "열두", "남의", "그날", "매일", "몰래", "그때", "둘"}


def chunks(ws):
    out = []
    i = 0
    while i < len(ws):
        cur = [ws[i]]
        i += 1
        while i < len(ws):
            txt = "".join(w[2] for w in cur)
            nxt = ws[i][2]
            if txt in MOD and len(txt + nxt) <= 8:
                cur.append(ws[i]); i += 1
            elif len(nxt) == 1 and nxt in ("수", "척", "건", "줄"):
                cur.append(ws[i]); i += 1
            else:
                break
        out.append(cur)
    return out


words, used = [], set()
for e in lines:
    ws = [w for w in e["words"] if w[2]]
    for part in chunks(ws):
        c = " ".join(w[2] for w in part)
        key = (e["n"], c)
        hl = HL.get(key)
        if hl:
            used.add(key)
        words.append((part[0][0], max(part[-1][1], part[0][0] + 0.12), c, hl))
for k in HL:
    if k not in used:
        print("강조 못 찾음", k)

SH, BL = 6, 4
ev = []
for i, (t0, t1, w, hl) in enumerate(words):
    nxt = words[i + 1][0] if i + 1 < len(words) else t1 + 0.4
    end = nxt if nxt - t1 < 0.25 else t1 + 0.15
    if hl:
        pop = rf"\fs{BIG}\fscx70\fscy70\t(0,70,\fscx112\fscy112)\t(70,140,\fscx100\fscy100)"
        sh, col = SH + 2, COL[hl]
    else:
        pop, sh, col = r"\fscx80\fscy80\t(0,80,\fscx100\fscy100)", SH, ""
    ev.append(f"Dialogue: 0,{ts(t0)},{ts(end)},Shadow,,0,0,0,,{{\\pos({540 + sh},{1180 + sh})\\blur{BL}{pop}}}{w}")
    ev.append(f"Dialogue: 1,{ts(t0)},{ts(end)},Word,,0,0,0,,{{\\pos(540,1180){pop}{col}}}{w}")
open(os.path.join(D, "subs.ass"), "w", encoding="utf-8-sig").write(head + "\n".join(ev) + "\n")
print("chunks", len(words))
