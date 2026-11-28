"""불과 물의 마을 본편 컷 목록 (대사 1~94, 127.07초 = 3812프레임 중 1~3811).
(이름, 시작 = 대사 번호(int) 또는 ('f', 프레임), 엔진). 끝 프레임 = 다음 컷 시작 - 1.
엔진: 아주 먼 하늘·구름 컷만 EEVEE, 나머지(가까운 배경·캐릭터) Cycles 64 (사용자 선호 + 실측).
"""
import json
import os

TIMING = r"C:\Users\tmd39\Desktop\haru_short\불과물의마을\audio\timing.json"
# 영어판(2026-11-28): timing.json 이 영어(호흡 없음) -> 끝 프레임은 timing 에서 계산. 한국어판은 shotlist_ko_bak.py
MIN_SHOT = 24                                   # 컷 최소 0.8초
FLASHBACK_LINES = [(12, 13), (53, 62)]          # 옛이야기·회상 구간 (대사 a 시작 ~ 대사 b 시작) -> 인코딩 때 색 바램

RAW = [
    ("sky", 1, "EEVEE"), ("river", 2, "CYCLES"), ("fireroofs", 3, "CYCLES"),
    ("waterroofs", 4, "CYCLES"), ("firestreet", 5, "CYCLES"), ("night", 6, "CYCLES"),
    ("waterfall", 7, "CYCLES"), ("rain", 8, "CYCLES"), ("bridge", 9, "CYCLES"),
    ("sign", 10, "CYCLES"), ("feet", 11, "CYCLES"), ("legend_steam", 12, "CYCLES"), ("moss", 13, "CYCLES"),
    ("banks", 14, "CYCLES"),
    ("haru_plaza", 15, "CYCLES"), ("haru_walk", 16, "CYCLES"), ("hand", 17, "CYCLES"), ("across", 18, "CYCLES"),
    ("reflect", 19, "CYCLES"), ("wave", 20, "CYCLES"), ("orbit21", 21, "CYCLES"), ("kids_point", 22, "CYCLES"),
    ("kids_blow", 23, "CYCLES"), ("water_kids", 24, "CYCLES"), ("room_frames", 25, "CYCLES"), ("frame_in", 26, "CYCLES"),
    ("window", 27, "CYCLES"),
    ("sun", 28, "EEVEE"), ("cracks", 29, "CYCLES"), ("lowriver", 30, "CYCLES"), ("dock_small", 31, "CYCLES"),
    ("shrink", 32, "CYCLES"), ("to_fire", 33, "CYCLES"), ("fire_column", 34, "CYCLES"), ("burning", 35, "CYCLES"),
    ("pullback36", 36, "CYCLES"), ("adults", 37, "CYCLES"), ("smith", 38, "CYCLES"), ("boatman", 39, "CYCLES"),
    ("night_bed", 40, "CYCLES"), ("haru_bed", 41, "CYCLES"), ("under", 42, "CYCLES"), ("mural_all", 43, "CYCLES"),
    ("mural_pan", 44, "CYCLES"), ("mural_hands", 45, "CYCLES"), ("mural_steam", 46, "CYCLES"), ("mural_cloud", 48, "CYCLES"),
    ("mural_rain", 49, "CYCLES"), ("mural_baby", 50, "CYCLES"), ("haru_eyes", 52, "CYCLES"),
    ("fb_mom", 53, "CYCLES"), ("fb_dad", 54, "CYCLES"), ("fb_face", 55, "CYCLES"), ("fb_hands", 56, "CYCLES"),
    ("fb_steam", 57, "CYCLES"), ("steam_rise", 58, "CYCLES"), ("rain_fall", 59, "CYCLES"), ("rain_towns", 60, "CYCLES"),
    ("wet_line", 61, "CYCLES"), ("dry_sky", 62, "CYCLES"), ("last_drop", 63, "CYCLES"),
    ("haru_run", 64, "CYCLES"), ("crowd", 65, "CYCLES"), ("shout_smith", 66, "CYCLES"), ("shout_boat", ("mid", 66), "CYCLES"),
    ("step", 67, "CYCLES"), ("nothing", 68, "CYCLES"), ("look_hands", 69, "CYCLES"), ("decide", 70, "CYCLES"),
    ("arms_out", 71, "CYCLES"), ("kid_fire", 72, "CYCLES"), ("kid_water", 73, "CYCLES"), ("three", 74, "CYCLES"),
    ("flow", 75, "CYCLES"), ("mix", 76, "CYCLES"),
    ("steam_col", 77, "CYCLES"), ("clouds", 78, "EEVEE"), ("under_clouds", 79, "CYCLES"), ("new_rain", 80, "CYCLES"),
    ("fire_calm", 81, "CYCLES"), ("river_rise", 82, "CYCLES"), ("dance", 83, "CYCLES"), ("fire_smile", 84, "CYCLES"),
    ("line_wash", 85, "CYCLES"),
    ("sunset", 86, "CYCLES"), ("gather", 87, "CYCLES"), ("gap", 88, "CYCLES"), ("chain", 89, "CYCLES"),
    ("night_sky", 90, "CYCLES"), ("night_rain", 91, "CYCLES"), ("haru_moved", 92, "CYCLES"), ("haru_smile", 93, "CYCLES"),
    ("final", 94, "CYCLES"),
]


def timing():
    return {x["n"]: x for x in json.load(open(TIMING, encoding="utf-8"))}


def frame_of_line(n, T=None):
    T = T or timing()
    return round(T[n]["start"] * 30) + 1


def shots():
    T = timing()
    starts = []
    for name, st, eng in RAW:
        if isinstance(st, int):
            f = frame_of_line(st, T)
        elif st[0] == "f":
            f = st[1]
        else:                                        # ("mid", n): 대사 n 의 가운데
            f = round((T[st[1]]["start"] + T[st[1]]["dur"] / 2) * 30) + 1
        starts.append((name, f, eng))
    last = round((T[max(T)]["start"] + T[max(T)]["dur"] + 0.25) * 30)
    for i in range(1, len(starts)):                 # 너무 짧은 컷은 뒤 컷 시작을 미룸 (뒤 컷도 최소 길이 남을 때만)
        nm, f, eng = starts[i]
        nxt = starts[i + 1][1] if i + 1 < len(starts) else last + 1
        want = starts[i - 1][1] + MIN_SHOT
        if f < want and nxt - want >= MIN_SHOT:
            starts[i] = (nm, want, eng)
    out = []
    for i, (name, f, eng) in enumerate(starts):
        f1 = starts[i + 1][1] - 1 if i + 1 < len(starts) else last
        out.append((name, f, f1, eng))
    return out


def flashback_ranges():
    T = timing()
    return [(T[a]["start"], T[b]["start"]) for a, b in FLASHBACK_LINES]


if __name__ == "__main__":
    tot = 0
    for s in shots():
        print(s, s[2] - s[1] + 1)
        tot += s[2] - s[1] + 1
    print(len(shots()), "shots", tot, "frames")
