import sys, glob, os
from PIL import Image, ImageDraw, ImageFont
src, out = sys.argv[1], sys.argv[2]
fs = sorted(glob.glob(os.path.join(src, "s*.png")))
font = ImageFont.truetype("../audio/fonts/Jua-Regular.ttf", 28)
W, H, per, c = 270, 480, 25, 9
for k in range(0, len(fs), per):
    ch = fs[k:k + per]; r = (len(ch) + c - 1) // c
    sh = Image.new("RGB", (c * W, r * H), "black"); d = ImageDraw.Draw(sh)
    for i, f in enumerate(ch):
        im = Image.open(f).resize((W, H)); x, y = (i % c) * W, (i // c) * H; sh.paste(im, (x, y))
        d.rectangle([x, y, x + 110, y + 34], fill="black"); d.text((x + 6, y + 2), os.path.basename(f)[:7], font=font, fill="white")
    sh.save(f"{out}_{k // per + 1}.jpg", quality=85); print(f"{out}_{k // per + 1}.jpg")
