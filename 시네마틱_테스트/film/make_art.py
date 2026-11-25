"""그림 텍스처 만들기 (일반 python + PIL): 다리 밑 벽화, 하루 방 액자 2개.
python film/make_art.py -> film/art/mural.png, frame_fire.png, frame_water.png
벽화: 오래된 프레스코 느낌 (빛바랜 색, 굵은 검은 윤곽, 로블록스식 네모 사람). 위에서 아래로 이야기 순서.
"""
import os
import random
from PIL import Image, ImageDraw, ImageFilter

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art")
os.makedirs(D, exist_ok=True)
INK = (38, 30, 26)
FIRE = (196, 74, 44)
FIRE_D = (140, 44, 30)
WATER = (120, 176, 206)
WATER_D = (78, 128, 166)
STONE = (196, 178, 150)
SKIN_F = (226, 196, 160)


def person(d, x, y, s, body, dark, hair, arm=None, skin=None):
    """로블록스식 네모 사람 (x, y = 발 가운데). arm: 'R' 오른팔 옆으로 뻗음, 'L', 'LR'"""
    w = 4
    # 다리
    for sx in (-1, 1):
        d.rectangle([x + sx * 0.02 * s - (0.5 * s if sx < 0 else 0), y - 2 * s, x + sx * 0.02 * s + (0.5 * s if sx > 0 else 0), y], fill=dark, outline=INK, width=w)
    # 몸통
    d.rectangle([x - s, y - 4 * s, x + s, y - 2 * s], fill=body, outline=INK, width=w)
    # 팔 (윗면 = 몸통 윗면)
    for sx, k in ((-1, "L"), (1, "R")):
        if arm and k in arm:
            x0 = x + sx * s
            x1 = x + sx * 3.0 * s
            d.rectangle([min(x0, x1), y - 4 * s, max(x0, x1), y - 3.05 * s], fill=body, outline=INK, width=w)
        else:
            d.rectangle([x + sx * s - (s if sx < 0 else 0), y - 4 * s, x + sx * s + (s if sx > 0 else 0), y - 2 * s], fill=body, outline=INK, width=w)
    # 머리
    hs = 1.2 * s
    d.rounded_rectangle([x - hs / 2, y - 4 * s - hs, x + hs / 2, y - 4 * s], radius=hs * 0.25, fill=skin or body, outline=INK, width=w)
    # 눈
    for sx in (-1, 1):
        d.ellipse([x + sx * hs * 0.2 - 4, y - 4 * s - hs * 0.62 - 6, x + sx * hs * 0.2 + 4, y - 4 * s - hs * 0.62 + 6], fill=INK)
    d.arc([x - hs * 0.22, y - 4 * s - hs * 0.5, x + hs * 0.22, y - 4 * s - hs * 0.2], 20, 160, fill=INK, width=4)
    if hair == "flame":
        top = y - 4 * s - hs
        d.polygon([(x - hs * 0.4, top), (x - hs * 0.2, top - hs * 0.7), (x, top - hs * 0.3), (x + hs * 0.15, top - hs * 0.9),
                   (x + hs * 0.4, top)], fill=(232, 120, 40), outline=INK)
    if hair == "drop":
        top = y - 4 * s - hs
        d.polygon([(x, top - hs * 0.8), (x - hs * 0.25, top - hs * 0.15), (x + hs * 0.25, top - hs * 0.15)], fill=WATER, outline=INK)
        d.ellipse([x - hs * 0.25, top - hs * 0.4, x + hs * 0.25, top + hs * 0.05], fill=WATER, outline=INK, width=3)


def cloud(d, cx, cy, r, col=(232, 230, 222)):
    for dx, dy, k in ((-1.2, 0.2, 0.7), (-0.4, -0.3, 1.0), (0.5, -0.2, 0.9), (1.2, 0.25, 0.65), (0, 0.3, 0.8)):
        d.ellipse([cx + dx * r - k * r, cy + dy * r - k * r, cx + dx * r + k * r, cy + dy * r + k * r], fill=col, outline=INK, width=5)


def house(d, x, y, w, h, wall, roof):
    d.rectangle([x - w / 2, y - h, x + w / 2, y], fill=wall, outline=INK, width=4)
    d.polygon([(x - w / 2 - 8, y - h), (x, y - h - w * 0.55), (x + w / 2 + 8, y - h)], fill=roof, outline=INK)
    d.rectangle([x - w * 0.12, y - h * 0.5, x + w * 0.12, y], fill=INK)


def mural():
    W, H = 2800, 2000
    im = Image.new("RGB", (W, H), STONE)
    d = ImageDraw.Draw(im)
    rnd = random.Random(7)
    # 테두리 띠
    d.rectangle([30, 30, W - 30, H - 30], outline=(120, 70, 50), width=22)
    # 1) 위쪽 가운데: 다리 위에서 손잡은 두 사람 (불 왼쪽, 물 오른쪽)
    by = 820
    d.rectangle([700, by, 2100, by + 70], fill=(150, 140, 125), outline=INK, width=6)          # 다리 상판
    for ax in (820, 1400, 1980):
        d.arc([ax - 260, by + 40, ax + 260, by + 520], 180, 360, fill=INK, width=8)
    d.rectangle([1392, by - 4, 1408, by + 66], fill=(190, 40, 30))                              # 붉은 선
    person(d, 1260, by, 70, FIRE, FIRE_D, "flame", arm="R", skin=SKIN_F)
    person(d, 1540, by, 70, WATER, WATER_D, "drop", arm="L")
    # 2) 손 닿은 곳에서 김 -> 구름 (위로)
    for k in range(7):
        yy = by - 330 - k * 50
        r = 26 + k * 9
        d.ellipse([1400 - r + rnd.randint(-12, 12), yy - r, 1400 + r + rnd.randint(-12, 12), yy + r], fill=(240, 238, 230), outline=INK, width=4)
    cloud(d, 1400, 170, 120)
    # 3) 구름에서 양쪽 마을로 비 (대각선 빗줄기)
    for side in (-1, 1):
        cx = 1400 + side * 820
        cloud(d, cx, 260, 95)
        for k in range(70):
            x0 = cx - 170 + rnd.randint(0, 340)
            y0 = 330 + rnd.randint(0, 680)
            d.line([x0, y0, x0 - 14, y0 + 70], fill=WATER_D, width=6)
    # 4) 아래 양쪽: 불꽃이 작아진 불 마을 (왼쪽), 차오른 강과 물 마을 (오른쪽)
    for i in range(5):
        x = 260 + i * 120
        house(d, x, 1250, 90, 110, (168, 120, 100), FIRE_D)
        d.polygon([(x - 10, 1250 - 110 - 70), (x, 1250 - 110 - 105), (x + 10, 1250 - 110 - 70)], fill=(230, 140, 60), outline=INK)   # 작은 불꽃
    for i in range(5):
        x = 2060 + i * 120
        house(d, x, 1250, 90, 110, (180, 196, 204), WATER_D)
    d.rectangle([60, 1280, W - 60, 1380], fill=WATER, outline=INK, width=6)                     # 차오른 강
    for k in range(18):
        x = 120 + k * 150
        d.arc([x, 1300, x + 90, 1350], 200, 340, fill=WATER_D, width=5)
    # 5) 맨 아래 가운데: 작은 아기 (하얀 몸, 노란 신발) — 빛나지도 투명하지도 않음
    bx, byy = 1400, 1800
    d.ellipse([bx - 260, byy - 330, bx + 260, byy + 40], outline=(150, 110, 70), width=8)       # 둥근 테
    s = 46
    d.rectangle([bx - s, byy - 3.2 * s, bx + s, byy - 1.4 * s], fill=(244, 242, 236), outline=INK, width=5)     # 몸
    for sx in (-1, 1):
        d.rectangle([bx + sx * 0.05 * s - (0.9 * s if sx < 0 else 0), byy - 1.4 * s, bx + sx * 0.05 * s + (0.9 * s if sx > 0 else 0), byy - 0.35 * s],
                    fill=(244, 242, 236), outline=INK, width=5)
        d.rectangle([bx + sx * 0.05 * s - (0.95 * s if sx < 0 else 0), byy - 0.4 * s, bx + sx * 0.05 * s + (0.95 * s if sx > 0 else 0), byy],
                    fill=(240, 200, 50), outline=INK, width=5)                                  # 노란 신발
        d.rectangle([bx + sx * s - (0.8 * s if sx < 0 else 0), byy - 3.2 * s, bx + sx * s + (0.8 * s if sx > 0 else 0), byy - 1.7 * s],
                    fill=(244, 242, 236), outline=INK, width=5)
    hs = 1.5 * s
    d.rounded_rectangle([bx - hs / 2, byy - 3.2 * s - hs, bx + hs / 2, byy - 3.2 * s], radius=hs * 0.3, fill=(244, 242, 236), outline=INK, width=5)
    for sx in (-1, 1):
        d.ellipse([bx + sx * hs * 0.2 - 5, byy - 3.2 * s - hs * 0.6 - 7, bx + sx * hs * 0.2 + 5, byy - 3.2 * s - hs * 0.6 + 7], fill=INK)
    d.arc([bx - hs * 0.18, byy - 3.2 * s - hs * 0.48, bx + hs * 0.18, byy - 3.2 * s - hs * 0.22], 20, 160, fill=INK, width=4)
    # 왼쪽 주황 손자국 반쪽, 오른쪽 파랑 반쪽 (아기 양옆 작은 표시)
    d.ellipse([bx - 330, byy - 200, bx - 280, byy - 150], fill=FIRE, outline=INK, width=3)
    d.ellipse([bx + 280, byy - 200, bx + 330, byy - 150], fill=WATER, outline=INK, width=3)
    # 낡은 느낌: 얼룩·갈라짐·바램
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    dd = ImageDraw.Draw(im, "RGBA")
    for _ in range(900):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        r = rnd.randint(4, 60)
        c = rnd.randint(150, 215)
        dd.ellipse([x - r, y - r, x + r, y + r], fill=(c, c - 12, c - 30, rnd.randint(10, 45)))
    for _ in range(40):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        pts = [(x, y)]
        for _ in range(rnd.randint(4, 10)):
            x += rnd.randint(-40, 40)
            y += rnd.randint(10, 50)
            pts.append((x, y))
        dd.line(pts, fill=(70, 60, 50, 120), width=2)
    im.save(os.path.join(D, "mural.png"))


def frame_pic(name, col):
    """흐릿한 실루엣 하나 (액자 속, 거의 지워진 그림)"""
    W, H = 600, 800
    im = Image.new("RGB", (W, H), (214, 204, 186))
    d = ImageDraw.Draw(im)
    s = 70
    x, y = W / 2, H - 120
    d.rectangle([x - s, y - 4 * s, x + s, y - 2 * s], fill=col)
    for sx in (-1, 1):
        d.rectangle([x + sx * s - (s if sx < 0 else 0), y - 4 * s, x + sx * s + (s if sx > 0 else 0), y - 2 * s], fill=col)
        d.rectangle([x + sx * 2 - (s if sx < 0 else 0), y - 2 * s, x + sx * 2 + (s if sx > 0 else 0), y], fill=col)
    d.rounded_rectangle([x - 0.6 * s, y - 5.2 * s, x + 0.6 * s, y - 4 * s], radius=20, fill=col)
    im = im.filter(ImageFilter.GaussianBlur(22))
    im.save(os.path.join(D, name))


if __name__ == "__main__":
    mural()
    frame_pic("frame_fire.png", (205, 110, 70))
    frame_pic("frame_water.png", (110, 160, 205))
    print("ok", D)
