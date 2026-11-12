import base64
import io
import os
import sys

from PIL import Image, ImageDraw

# 拼图预览：把一个目录里的图按网格拼接，缩小后输出 base64
d = sys.argv[1]
out_w = int(sys.argv[2]) if len(sys.argv) > 2 else 560
cols = 4
files = sorted(f for f in os.listdir(d) if f.endswith(".png"))
if not files:
    print("NO_FILES")
    raise SystemExit(0)

cell_w = out_w // cols
sample = Image.open(os.path.join(d, files[0]))
cell_h = int(cell_w * sample.height / sample.width)
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (out_w, rows * (cell_h + 18)), (18, 18, 18))
draw = ImageDraw.Draw(sheet)

for i, name in enumerate(files):
    im = Image.open(os.path.join(d, name)).convert("RGB").resize((cell_w, cell_h))
    x = (i % cols) * cell_w
    y = (i // cols) * (cell_h + 18)
    sheet.paste(im, (x, y + 18))
    draw.text((x + 4, y + 3), name.split("_")[0], fill=(230, 230, 230))

buf = io.BytesIO()
sheet.save(buf, "JPEG", quality=68)
data = buf.getvalue()

b64 = base64.b64encode(data).decode()
print("SIZE %d %d" % (len(data), sheet.width))
for i in range(0, len(b64), 1000):
    print("B64" + b64[i:i + 1000])
print("END")
