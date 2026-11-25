"""스틸 타일 이미지: python film/sheet.py <시작번호> <개수> <출력.png>"""
import os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shotlist as SL
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "film", "stills")
a, n, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
S = SL.shots()[a:a + n]
W, H, C = 216, 384, 6
F = ImageFont.truetype(r"C:\Users\tmd39\Desktop\haru_short\불과물의마을\audio\fonts\Jua-Regular.ttf", 20)
rows = (len(S) + C - 1) // C
im = Image.new("RGB", (W * C, (H + 26) * rows), (20, 20, 20))
d = ImageDraw.Draw(im)
for i, (nm, f0, f1, e) in enumerate(S):
    x, y = (i % C) * W, (i // C) * (H + 26)
    p = os.path.join(R, nm + ".png")
    if os.path.exists(p):
        im.paste(Image.open(p).convert("RGB").resize((W, H)), (x, y + 26))
    d.text((x + 4, y + 2), f"{a + i + 1}. {nm}", fill=(255, 230, 120), font=F)
im.save(out)
