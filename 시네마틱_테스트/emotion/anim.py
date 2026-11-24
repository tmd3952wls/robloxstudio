"""감정 타임라인 -> 프레임별 얼굴·몸 매개변수.

Timeline(style).key(t, '놀람', 1.0, dur=None)  : t 초에 놀람으로 전환 시작 (이전 상태에서 이어짐 -> 감정이 끊기지 않음)
           .say(t0, t1, '대사')                : 말하는 동안 입 모양 (음절 수에 맞춰 열림/닫힘)
           .look(t, lx, ly)                     : 시선 목표
eval(t) -> (face_params, body_params)
자동 레이어: 눈 깜빡임(불규칙), 시선 흔들림(saccade), 미세 떨림(공포·울음), 호흡, 눈물 흐름 증가.
"""
import math
import random

import face as F
import library as LB


def ease(x, kind):
    x = min(max(x, 0.0), 1.0)
    if kind == "back":                      # 살짝 넘쳤다 돌아옴 (놀람·기쁨)
        c1 = 1.70158 * 0.8
        c3 = c1 + 1
        return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
    if kind == "snap":                      # 빠르게 들어가서 부드럽게 멈춤
        return 1 - (1 - x) ** 4
    return x * x * (3 - 2 * x)              # smooth


class Timeline:
    def __init__(self, style=None, seed=1, fps=30):
        self.style, self.fps = style, fps
        self.keys = []                       # (t, name, intensity, dur)
        self.speech = []                     # (t0, t1, n_syllables)
        self.looks = []                      # (t, lx, ly)
        self.rnd = random.Random(seed)
        self._cache = None
        self._blinks = None

    def key(self, t, name, intensity=1.0, dur=None):
        self.keys.append((t, name, intensity, dur if dur is not None else LB.EMOTIONS[name]["dur"]))
        self.keys.sort(key=lambda k: k[0])
        self._cache = None
        return self

    def say(self, t0, t1, text):
        n = sum(1 for ch in text if "가" <= ch <= "힣") or max(1, len(text.split()) * 2)
        self.speech.append((t0, t1, n))
        return self

    def look(self, t, lx, ly):
        self.looks.append((t, lx, ly))
        self.looks.sort()
        return self

    # ---------------------------------------------------------- 감정 상태 (전환 이어 붙이기)
    def _target(self, k):
        t, name, inten, dur = self.keys[k]
        return LB.target(name, inten, self.style)

    def _starts(self):
        if self._cache is None:
            f0, b0 = LB.target("평온", 1.0, self.style)
            starts = []
            cur = (f0, b0)
            for i in range(len(self.keys)):
                starts.append(cur)
                if i + 1 < len(self.keys):
                    cur = self._blend_at(i, cur, self.keys[i + 1][0])
            self._cache = starts
        return self._cache

    def _blend_at(self, i, start, t):
        tk, name, inten, dur = self.keys[i]
        e = LB.EMOTIONS[name]
        ft, bt = self._target(i)
        fs, bs = start
        f = {}
        for g, keys in LB.GROUPS.items():
            d = e["order"].get(g, 0.0)
            x = ease((t - tk - d) / max(dur, 1e-3), e["ease"])
            for k in keys:
                if k in fs:
                    f[k] = fs[k] + (ft[k] - fs[k]) * x
        for k in fs:
            f.setdefault(k, fs[k] + (ft[k] - fs[k]) * ease((t - tk) / max(dur, 1e-3), e["ease"]))
        b = {}
        for k in bs:
            g = "head" if k.startswith("head") else "body"
            d = e["order"].get(g, 0.0)
            x = ease((t - tk - d) / max(dur * 1.2, 1e-3), e["ease"])
            b[k] = bs[k] + (bt[k] - bs[k]) * x
        return f, b

    def current(self, t):
        if not self.keys:
            return LB.target("평온", 1.0, self.style) + ("평온",)
        st = self._starts()
        i = max([j for j, k in enumerate(self.keys) if k[0] <= t] or [0])
        f, b = self._blend_at(i, st[i], t) if t >= self.keys[0][0] else st[0]
        return f, b, self.keys[i][1]

    # ---------------------------------------------------------- 자동 레이어
    def _blink_times(self, T=600.0):
        if self._blinks is None:
            r = random.Random(7)
            out, t = [], r.uniform(0.5, 2.0)
            while t < T:
                out.append(t)
                t += r.uniform(1.8, 4.5)
                if r.random() < 0.15:          # 가끔 두 번 연속
                    out.append(t)
                    t += 0.25
            self._blinks = out
        return self._blinks

    def eval(self, t):
        f, b, name = self.current(t)
        e = LB.EMOTIONS[name]
        f, b = dict(f), dict(b)
        # 깜빡임 (감정별 간격 배율), 웃는 눈/감은 눈이면 생략
        bl = 0.0
        scale = e.get("blink", 1.0)
        for tb in self._blink_times():
            tb2 = tb * scale
            dt = t - tb2
            if -0.07 < dt < 0.11:
                bl = max(bl, 1 - abs(dt - 0.0) / (0.07 if dt < 0 else 0.11))
        if bl > 0:
            for s in ("L", "R"):
                f[f"lid{s}"] = f[f"lid{s}"] + (-1.1 - f[f"lid{s}"]) * bl
        # 시선: 목표 + 작은 흔들림 (공포는 빠르게 두리번)
        if self.looks:
            prev = [l for l in self.looks if l[0] <= t]
            if prev:
                lt, lx, ly = prev[-1]
                x = ease((t - lt) / 0.18, "snap")
                bx, by = (self.looks[self.looks.index(prev[-1]) - 1][1:] if self.looks.index(prev[-1]) > 0 else (0.0, 0.0))
                f["lx"] = f["lx"] + bx + (lx - bx) * x
                f["ly"] = f["ly"] + by + (ly - by) * x
        sac = e.get("saccade", 0.3)
        if sac > 0:
            seg = int(t * sac * 2)
            r = random.Random(seg * 31 + 5)
            jx, jy = r.uniform(-1, 1) * (0.35 if sac > 1 else 0.12), r.uniform(-1, 1) * (0.25 if sac > 1 else 0.08)
            f["lx"] = max(-1, min(1, f["lx"] + jx))
            f["ly"] = max(-1, min(1, f["ly"] + jy))
        # 떨림
        tr = e.get("tremble", 0.0)
        if tr:
            b["head_roll"] += tr * 1.4 * math.sin(t * 37) * math.sin(t * 11.3)
            b["head_pitch"] += tr * 1.0 * math.sin(t * 29 + 1)
            b["lean"] += tr * 0.6 * math.sin(t * 23)
        # 호흡
        b["breath"] = math.sin(t * 2 * math.pi / 3.6)
        # 눈물 흐름: 감정이 이어질수록 길어짐
        tf = e.get("tears_flow", 0.0)
        if tf:
            ks = [k for k in self.keys if k[0] <= t]
            since = t - ks[-1][0] if ks else 0
            f["flow"] = min(1.0, f["flow"] + max(0, since - 0.6) * tf)
        # 말하기 (입 열림 펄스)
        for t0, t1, n in self.speech:
            if t0 <= t <= t1:
                ph = (t - t0) / (t1 - t0) * n
                o = abs(math.sin(math.pi * ph)) ** 0.8
                r = random.Random(int(ph) * 13 + 3)
                f["mopen"] = max(f["mopen"], o * r.uniform(0.3, 0.65))
                f["mshape"] = f["mshape"] * 0.5 + r.choice((0.0, 0.0, 0.5, 0.8)) * o * 0.5
                b["head_pitch"] += 1.2 * math.sin(ph * 1.7)
        return f, b
