import sys, glob, os
from PIL import Image, ImageDraw
src, out, per = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv)>3 else 25
fs = sorted(glob.glob(os.path.join(src, "*.png")))
cols = 5
for k in range(0, len(fs), per):
    grp = fs[k:k+per]
    w, h = 216, 384
    rows = (len(grp)+cols-1)//cols
    S = Image.new("RGB", (cols*w, rows*h), (0,0,0))
    d = ImageDraw.Draw(S)
    for i, f in enumerate(grp):
        im = Image.open(f).convert("RGB").resize((w, h))
        S.paste(im, ((i%cols)*w, (i//cols)*h))
        d.rectangle([(i%cols)*w, (i//cols)*h, (i%cols)*w+70, (i//cols)*h+18], fill=(0,0,0))
        d.text(((i%cols)*w+3, (i//cols)*h+3), os.path.basename(f)[:9], fill=(255,255,0))
    S.save(f"{out}_{k//per+1}.jpg", quality=85)
    print(f"{out}_{k//per+1}.jpg")
