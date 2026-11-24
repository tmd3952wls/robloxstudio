"""감정 라이브러리 (Emotion Library) — 얼굴·몸짓·전환 방식을 감정별로 관리. 모든 캐릭터 공용.

EMOTIONS[name] = {
  face:  얼굴 매개변수 (face.NEUTRAL 에서 바뀌는 값만),
  body:  몸 자세 (head_pitch/yaw/roll, lean, armL/armR=(앞뒤, 옆), back: 뒤로 물러남 m, crouch: 움츠림),
  dur:   기본 전환 시간 (초),
  ease:  'smooth' | 'back'(살짝 넘쳤다 돌아옴) | 'snap'(빠르게),
  order: 부위별 시작 지연 (초) — 예) 놀람: 눈썹 → 눈 → 동공 → 입 → 머리 → 몸
  tremble: 미세 떨림 세기, saccade: 시선 이동 빈도(초당), blink: 깜빡임 간격 배율,
  tears_flow: 눈물이 시간이 갈수록 흐름 (초당 증가량)
}
강도(intensity 0~1.3)는 중립에서 목표까지의 비율. 캐릭터별 스타일은 STYLE_OVERRIDES 로 덮어씀.
"""
from face import NEUTRAL

# 부위 묶음 (전환 순서 제어용)
GROUPS = {
    "brow": ["browYL", "browYR", "browAL", "browAR", "browC", "browW"],
    "eye": ["openL", "openR", "lidL", "lidR", "lidAngL", "lidAngR", "lowL", "lowR", "eye_w", "eye_h"],
    "pupil": ["pupil", "lx", "ly"],
    "mouth": ["mw", "my", "mopen", "mcurve", "teeth", "wobble", "skew", "tongue", "mshape"],
    "extra": ["tears", "flow", "sweat", "blush", "gloom"],
}
BODY_KEYS = ["head_pitch", "head_yaw", "head_roll", "lean", "armL_x", "armL_z", "armR_x", "armR_z", "back", "crouch", "legspread"]
BODY_NEUTRAL = {k: 0.0 for k in BODY_KEYS}


def _o(brow=0.0, eye=0.0, pupil=0.0, mouth=0.0, head=0.0, body=0.0, extra=0.0):
    return dict(brow=brow, eye=eye, pupil=pupil, mouth=mouth, head=head, body=body, extra=extra)


EMOTIONS = {
    "평온": dict(face={}, body={}, dur=0.6, ease="smooth", order=_o(), tremble=0, saccade=0.4, blink=1.0),
    "기쁨": dict(face=dict(lowL=0.95, lowR=0.95, browYL=0.03, browYR=0.03, browC=0.6, mcurve=1.0, mopen=0.45, mw=0.15,
                          teeth=0.35, tongue=0.4, blush=0.7),
                 body=dict(head_pitch=-6, head_roll=5, lean=-4, armL_z=18, armR_z=18, armL_x=-10, armR_x=-10),
                 dur=0.45, ease="back", order=_o(brow=0.0, eye=0.05, mouth=0.03, head=0.08, body=0.1), tremble=0, saccade=0.3, blink=1.2),
    "놀람": dict(face=dict(openL=1.35, openR=1.35, pupil=0.32, browYL=0.075, browYR=0.075, browC=0.8, mopen=1.0, mw=0.1,
                          mcurve=-0.1, mshape=0.6),
                 body=dict(head_pitch=-12, lean=-9, back=0.12, armL_x=-25, armR_x=-25, armL_z=22, armR_z=22),
                 dur=0.28, ease="back", order=_o(brow=0.0, eye=0.04, pupil=0.08, mouth=0.1, head=0.12, body=0.15),
                 tremble=0.0, saccade=0.2, blink=3.0),
    "공포": dict(face=dict(openL=1.3, openR=1.3, pupil=0.2, browYL=0.05, browYR=0.05, browAL=-0.55, browAR=-0.55, browC=-0.3,
                          mopen=0.3, mw=0.13, mcurve=-0.6, wobble=1.0, teeth=0.4, gloom=1.0, sweat=1.0),
                 body=dict(head_pitch=8, lean=6, back=0.35, crouch=0.12, armL_x=-70, armR_x=-70, armL_z=-10, armR_z=-10),
                 dur=0.35, ease="snap", order=_o(eye=0.0, pupil=0.05, brow=0.05, mouth=0.12, head=0.15, body=0.2, extra=0.3),
                 tremble=1.0, saccade=3.0, blink=2.5),
    "슬픔": dict(face=dict(browAL=-0.75, browAR=-0.75, browYL=0.025, browYR=0.025, lidL=0.55, lidR=0.55, lidAngL=-0.45, lidAngR=-0.45,
                          ly=-0.6, pupil=0.55, mcurve=-0.9, mw=0.1, wobble=0.45, tears=0.8, flow=0.0),
                 body=dict(head_pitch=16, head_roll=-4, lean=8, armL_z=-4, armR_z=-4, crouch=0.05),
                 dur=0.9, ease="smooth", order=_o(brow=0.0, pupil=0.15, eye=0.2, mouth=0.35, head=0.3, body=0.4, extra=0.6),
                 tremble=0.25, saccade=0.15, blink=0.7, tears_flow=0.25),
    "분노": dict(face=dict(browAL=0.9, browAR=0.9, browYL=-0.03, browYR=-0.03, browW=1.25, lidL=0.4, lidR=0.4, lidAngL=0.7, lidAngR=0.7,
                          pupil=0.38, mopen=0.35, mw=0.14, mcurve=-0.5, teeth=1.0),
                 body=dict(head_pitch=10, lean=10, armL_x=-15, armR_x=-15, armL_z=-12, armR_z=-12, legspread=6),
                 dur=0.4, ease="snap", order=_o(brow=0.0, eye=0.06, mouth=0.14, head=0.18, body=0.24),
                 tremble=0.35, saccade=0.2, blink=1.5),
    "당황": dict(face=dict(openL=1.2, openR=1.05, browYL=0.06, browYR=0.0, browAL=-0.3, browAR=0.25, pupil=0.4, mopen=0.15,
                          mcurve=-0.2, wobble=0.6, skew=0.5, sweat=1.0, blush=0.5),
                 body=dict(head_roll=8, head_yaw=-10, lean=-3, armR_x=-120, armR_z=10, armL_z=8),
                 dur=0.3, ease="back", order=_o(brow=0.0, eye=0.03, pupil=0.0, mouth=0.08, head=0.1, body=0.12, extra=0.2),
                 tremble=0.15, saccade=4.0, blink=1.5),
    "울음": dict(face=dict(browAL=-0.9, browAR=-0.9, browYL=0.03, browYR=0.03, lowL=0.9, lowR=0.9, lidL=0.5, lidR=0.5,
                          mopen=0.9, mw=0.15, mcurve=-1.0, wobble=0.6, teeth=0.25, tears=1.0, flow=0.6),
                 body=dict(head_pitch=-14, lean=-2, armL_x=-140, armR_x=-140, armL_z=-14, armR_z=-14),
                 dur=0.6, ease="smooth", order=_o(brow=0.0, eye=0.08, mouth=0.15, head=0.2, body=0.22, extra=0.25),
                 tremble=0.8, saccade=0.0, blink=0.4, tears_flow=0.4),
    "결심": dict(face=dict(browAL=0.45, browAR=0.45, browYL=-0.015, browYR=-0.015, browW=1.15, lidL=0.75, lidR=0.75, lidAngL=0.25, lidAngR=0.25,
                          pupil=0.5, mcurve=-0.15, mw=0.09),
                 body=dict(head_pitch=-4, lean=4, armL_x=-8, armR_x=-8, armL_z=-6, armR_z=-6, legspread=5),
                 dur=0.5, ease="smooth", order=_o(eye=0.0, brow=0.05, mouth=0.15, head=0.1, body=0.2),
                 tremble=0, saccade=0.05, blink=1.8),
    "흥분": dict(face=dict(openL=1.3, openR=1.3, pupil=0.6, browYL=0.06, browYR=0.06, browC=0.7, mcurve=1.2, mopen=0.85, mw=0.16,
                          teeth=0.4, tongue=0.6, blush=1.0),
                 body=dict(head_pitch=-10, lean=-6, armL_x=-160, armR_x=-160, armL_z=25, armR_z=25),
                 dur=0.3, ease="back", order=_o(eye=0.0, brow=0.02, mouth=0.05, head=0.08, body=0.1),
                 tremble=0.1, saccade=0.6, blink=1.2),
    "의심": dict(face=dict(browYL=0.055, browYR=-0.02, browAL=-0.2, browAR=0.55, lidL=0.9, lidR=0.45, lidAngR=0.35, lx=0.6,
                          mcurve=-0.3, skew=-0.6, mw=0.08),
                 body=dict(head_roll=-6, head_yaw=14, head_pitch=4, lean=2, armL_x=-40, armL_z=-30, armR_x=-60, armR_z=-25),
                 dur=0.55, ease="smooth", order=_o(pupil=0.0, brow=0.05, eye=0.1, mouth=0.2, head=0.15, body=0.25),
                 tremble=0, saccade=0.2, blink=1.5),
    "안도": dict(face=dict(lowL=0.92, lowR=0.92, browAL=-0.25, browAR=-0.25, browYL=0.02, browYR=0.02,
                          mcurve=0.75, mopen=0.12, mw=0.12, sweat=0.6),
                 body=dict(head_pitch=-5, lean=-3, crouch=0.04, armL_z=-6, armR_z=-6),
                 dur=0.8, ease="smooth", order=_o(eye=0.0, brow=0.05, mouth=0.15, head=0.2, body=0.25),
                 tremble=0, saccade=0.2, blink=1.0),
}

# 사건 -> 감정 (스토리 자동 연결 기본 규칙)
EVENT_TO_EMOTION = {
    "위험 발견": "놀람", "폭발": "공포", "이별": "슬픔", "배신": "분노", "위기 극복": "안도", "재회": "기쁨",
    "대치": "결심", "예상 못한 사건": "당황", "의문": "의심", "승리": "흥분", "상실": "울음", "평상": "평온",
}

# 캐릭터별 표정 스타일 (같은 감정이라도 사람마다 다르게)
STYLE_OVERRIDES = {
    "하루": dict(scale=1.0, face=dict(eye_w=0.085, eye_h=0.11)),          # 크고 동그란 눈
    "불마을": dict(scale=1.15, face=dict(browW=1.2, eye_h=0.095)),         # 굵은 눈썹, 과장된 감정
    "물마을": dict(scale=0.85, face=dict(eye_h=0.115, browW=0.85)),        # 차분, 큰 눈
}


def target(name, intensity=1.0, style=None):
    """감정 이름 + 강도 -> (얼굴 dict, 몸 dict)"""
    e = EMOTIONS[name]
    st = STYLE_OVERRIDES.get(style or "", {})
    k = intensity * st.get("scale", 1.0)
    base = dict(NEUTRAL)
    base.update(st.get("face", {}))
    f = {kk: base[kk] + (e["face"].get(kk, base[kk]) - base[kk]) * k for kk in base}
    b = {kk: BODY_NEUTRAL[kk] + e["body"].get(kk, 0.0) * k for kk in BODY_KEYS}
    return f, b
