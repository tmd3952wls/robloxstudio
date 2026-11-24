"""컷별 효과음 큐 (컷 번호, 연출 시각(초, 그 컷 기준·원래 연출 시간), 소리 id, 렌더 옵션, 음량 dB, 정렬)

정렬: "onset" = 소리 시작을 시각에, "peak" = 가장 큰 순간을 시각에 (휙 소리·차오름)
오프닝(1~4컷)은 한 번의 비행이라 컷 1 기준 전체 시각 g 를 씀.
"""
CUES = [
    # 오프닝 비행: 산에서 하루까지 빨려 들어감
    (1, 0.00, "whoosh_big/gust", {"dur": 3.0, "apex": 1.3}, -10, "onset"),
    (1, 2.75, "swish/soft", {}, -14, "peak"),            # 광장 깃발 줄이 스침
    (1, 3.20, "swish/bright", {}, -18, "peak"),          # 별등 기둥이 스침
    (1, 3.55, "pro_shimmer/m1", {}, -16, "onset"),       # 별이 하루 옆을 지나감
    (1, 3.82, "mallet/celesta", {"pitch": "E6"}, -15, "onset"),  # 미소
    (5, 0.05, "swish/cane", {}, -16, "peak"),
    (6, 0.30, "whoosh_fast/tight", {}, -15, "peak"),     # 지붕으로 급밀기
    (6, 0.40, "knock/wood", {}, -18, "onset"),
    (7, 0.00, "pro_shimmer/m1", {}, -17, "onset"),
    (8, 0.42, "mallet/glock", {"pitch": "G6"}, -13, "onset"),   # 별이 손에 닿음
    (9, 0.75, "knock/snap", {}, -14, "onset"),           # 병 뚜껑 닫힘
    (10, 0.10, "pro_shimmer/m0", {}, -19, "onset"),
    (11, 0.10, "pro_whoosh_big/windy", {}, -20, "peak"),
    (12, 0.20, "pro_shimmer/m1", {}, -16, "onset"),      # 빛나는 빵
    (13, 0.55, "ui_pop/fall", {}, -14, "onset"),         # 실망
    (14, 0.32, "notify/mid_wood", {}, -15, "onset"),     # 손가락 하나
    (15, 0.40, "cut_hit/punch", {}, -12, "onset"),       # 표지판 급밀기
    (15, 0.30, "whoosh_fast/heavy", {}, -16, "peak"),
    (16, 0.30, "mallet/up4", {}, -14, "onset"),          # 별이 날아감
    (17, 0.50, "ui_pop/soft", {}, -18, "onset"),
    (18, 0.05, "swipe/glide", {}, -20, "peak"),
    (19, 0.30, "drip/plink", {}, -17, "onset"),
    (20, 0.00, "cut_hit/sub", {}, -13, "onset"),         # 전부,
    (21, 0.10, "whoosh_big/deep", {}, -18, "peak"),
    (22, 0.40, "ui_pop/wide", {}, -16, "onset"),         # 손 흔들기
    (24, 0.10, "swipe/cloth", {}, -15, "peak"),          # 병 닦기
    (25, 0.10, "tap/glass", {}, -15, "onset"),           # 귀에 댐
    (26, 0.00, "pro_shimmer/m2", {}, -16, "onset"),      # 별 소리
    (27, 0.30, "ui_pop/boop", {}, -16, "onset"),
    (27, 0.60, "ui_pop/boop", {}, -17, "onset"),
    (28, 0.40, "swish/flick", {}, -17, "peak"),          # 으쓱
    (31, 0.10, "mallet/marimba", {"pitch": "C5"}, -17, "onset"),
    (32, 0.00, "shimmer/m4", {}, -18, "onset"),          # 별이 내림
    (33, 0.00, "pro_shimmer/m4", {}, -17, "onset"),
    (34, 0.40, "swish/stick", {}, -16, "peak"),
    (35, 0.30, "swish/stick", {}, -15, "peak"),
    (35, 0.45, "swish/blade", {}, -17, "peak"),
    (35, 0.55, "swish/stick", {}, -16, "peak"),
    (36, 0.30, "knock/snap", {}, -15, "onset"),          # 하나 잡음
    (37, 0.20, "tap/glass", {}, -16, "onset"),           # 귀에 댐
    (38, 0.30, "reverse_swell/dark", {}, -15, "peak"),   # 울음을 들음 -> 충격
    (38, 0.52, "cut_hit/sub", {}, -12, "onset"),
    (39, 0.05, "cut_hit/air", {}, -16, "onset"),
    (40, 0.18, "cut_hit/punch", {}, -15, "onset"),       # 움찔
    (41, 0.30, "whoosh_fast/reverse", {}, -16, "peak"),  # 하늘을 올려다봄
    (42, 0.10, "downlifter/air_fall", {}, -16, "onset"), # 빈 하늘
    (43, 0.00, "pro_shimmer/m1", {}, -17, "onset"),
    (44, 0.30, "swish/soft", {}, -18, "peak"),
    (45, 0.30, "shutter/film", {}, -16, "onset"),        # 봉우리 급밀기
    (45, 0.32, "cut_hit/punch", {}, -14, "onset"),
    (46, 0.00, "riser/swell", {"dur": 1.6}, -18, "onset"),
    (47, 0.05, "swipe/glide", {}, -18, "peak"),
    (48, 0.10, "reverse_swell/ring", {}, -17, "onset"),
    (49, 0.10, "downlifter/sub_sink", {}, -16, "onset"),
    (50, 0.32, "cut_hit/kick", {}, -12, "onset"),        # 소리침
    (51, 0.30, "swish/flick", {}, -17, "peak"),
    (52, 0.20, "tap/table", {}, -14, "onset"),           # 달리는 발소리
    (52, 0.40, "tap/table", {}, -14, "onset"),
    (52, 0.60, "tap/table", {}, -14, "onset"),
    (52, 0.80, "tap/table", {}, -14, "onset"),
    (52, 1.00, "tap/table", {}, -14, "onset"),
    (53, 0.10, "pro_shimmer/m0", {}, -18, "onset"),
    (54, 0.10, "toggle/on", {}, -12, "onset"),           # 뚜껑 셋
    (55, 0.10, "toggle/on", {}, -12, "onset"),
    (56, 0.10, "toggle/on", {}, -12, "onset"),
    (57, 0.00, "whoosh_big/gust", {"dur": 1.8, "apex": 0.6}, -14, "onset"),   # 별이 창밖으로
    (57, 0.10, "pro_shimmer/m4", {}, -17, "onset"),
    (58, 0.10, "swish/zing", {}, -16, "peak"),
    (59, 0.00, "pro_whoosh_big/long", {}, -14, "onset"), # 산으로 날아감
    (60, 0.00, "riser/air", {"dur": 1.6}, -18, "onset"),
    (61, 0.10, "reverse_swell/breath", {}, -17, "onset"),
    (62, 0.90, "toggle/latch", {}, -13, "onset"),        # 빵집 아저씨가 병을 엶
    (62, 0.95, "mallet/up4", {}, -15, "onset"),
    (63, 0.00, "pro_pop/boop", {}, -15, "onset"),
    (63, 0.05, "mallet/up4", {}, -16, "onset"),
    (64, 0.00, "riser/rush", {"dur": 1.4}, -15, "onset"),  # 온 마을의 별이 떠오름
    (65, 0.00, "whoosh_big/swell", {}, -14, "onset"),
    (66, 0.00, "whoosh_big/jet", {"dur": 1.8, "apex": 0.8}, -13, "onset"),  # 별의 강
    (67, 0.00, "riser/swell", {"dur": 0.95}, -14, "onset"),
    (68, 0.15, "impact/swell", {}, -12, "onset"),        # 하늘이 다시 켜짐
    (68, 0.15, "logo_sting/soft_bloom", {}, -14, "onset"),
    (69, 0.10, "shimmer/m5", {}, -21, "onset"),
    (70, 0.10, "drip/tiny", {}, -18, "onset"),
    (71, 0.10, "mallet/marimba", {"pitch": "G4"}, -18, "onset"),
    (72, 0.00, "pro_shimmer/m1", {}, -17, "onset"),
    (73, 0.50, "mallet/celesta", {"pitch": "C6"}, -14, "onset"),   # 어깨에 앉음
    (74, 0.00, "mallet/up4", {}, -16, "onset"),       # 다시 올라감
    (75, 0.30, "ui_pop/soft", {}, -19, "onset"),
    (76, 0.40, "logo_sting/soft_bloom", {}, -14, "onset"),
    (76, 0.50, "whoosh_big/swell", {}, -16, "onset"),    # 등 뒤로 물러남
]
