"""스토리 -> 감정 자동 연결.

1) 대본 표(대본.md)의 '감정' 열이 있으면 그대로 사용 (Claude 가 대본을 쓸 때 줄마다 감정·강도를 적음: "놀람 1.0")
2) 없으면 키워드 규칙으로 추정 (아래 RULES), 그래도 없으면 이전 감정을 약하게 이어감 (감정이 끊기지 않게)
3) timing.json(대사별 시작·끝 초)과 합쳐 Timeline 키 + 립싱크(say) 생성
   - 감정 전환은 대사 시작 0.15초 전에 시작 -> 단어가 들릴 때 표정이 이미 바뀌어 있음
   - 클로즈업 컷(shots 의 'close')은 강도 +15% (얼굴이 크게 보일 때 확실하게)
"""
import json
import re

import anim as AN
import library as LB

RULES = [
    (r"폭발|터졌|무너|불길이|덮쳤", "공포", 1.0),
    (r"비명|살려|도망|무서", "공포", 0.9),
    (r"갑자기|그 순간|번쩍|어\?|뭐야", "놀람", 1.0),
    (r"배신|훔쳤|거짓말|용서 못|분노|화가", "분노", 1.0),
    (r"울었|눈물|흐느|엉엉", "울음", 1.0),
    (r"떠났|헤어|사라졌|잃었|그리워|외로", "슬픔", 0.9),
    (r"다시 만|돌아왔|만났어|웃었|행복|기뻐", "기쁨", 1.0),
    (r"해냈|이겼|드디어|최고", "흥분", 1.0),
    (r"살았|다행|괜찮아|안심", "안도", 0.9),
    (r"결심|반드시|지킬|건너겠|하기로", "결심", 1.0),
    (r"왜|이상하|수상|정말일까|의심", "의심", 0.8),
    (r"당황|어쩌지|어색|허둥", "당황", 0.9),
]


def guess(text, prev="평온"):
    for pat, emo, k in RULES:
        if re.search(pat, text):
            return emo, k
    return prev, 0.6


def parse_script(md_path):
    """대본.md 표: | n | 대사 | 화면 | 카메라 | (감정) |  -> [(n, 대사, 감정 or None, 강도)]"""
    rows = []
    for line in open(md_path, encoding="utf-8"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0].isdigit():
            emo, k = None, 1.0
            if len(cells) >= 5 and cells[4]:
                m = re.match(r"(\S+)\s*([\d.]+)?", cells[4])
                if m and m.group(1) in LB.EMOTIONS:
                    emo, k = m.group(1), float(m.group(2) or 1.0)
            rows.append((int(cells[0]), cells[1], emo, k))
    return rows


def build_timeline(rows, timing, speaker_lines=None, close_lines=(), style="하루"):
    """timing: {줄번호: (시작, 끝)} . speaker_lines: 이 캐릭터가 직접 말하는 줄 (립싱크)"""
    tl = AN.Timeline(style)
    prev = "평온"
    tl.key(0.0, "평온")
    for n, text, emo, k in rows:
        if n not in timing:
            continue
        t0, t1 = timing[n]
        if emo is None:
            emo, k = guess(text, prev)
        if n in close_lines:
            k *= 1.15
        if emo != prev or k > 0.95:
            tl.key(max(0.0, t0 - 0.15), emo, min(k, 1.3))
        if speaker_lines and n in speaker_lines:
            tl.say(t0, t1, re.sub(r"[\"'“”‘’]", "", text))
        prev = emo
    return tl


def load_timing(path):
    """make_subs/fish_build 의 timing.json -> {줄: (시작초, 끝초)}"""
    d = json.load(open(path, encoding="utf-8"))
    out = {}
    for it in (d if isinstance(d, list) else d.get("lines", [])):    # [{n, text, start, dur, words}]
        out[int(it["n"])] = (float(it["start"]), float(it["start"]) + float(it["dur"]))
    return out
