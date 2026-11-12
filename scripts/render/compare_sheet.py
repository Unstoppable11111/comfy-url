"""把若干张图拼成一张对比图，输出 base64。

    python compare_sheet.py 640 "参考图=/ComfyUI/input/ref_C01.png" "A=/ComfyUI/output/xxx.png"
"""
import base64
import io
import os
import shutil
import sys

from PIL import Image, ImageDraw

out_w = int(sys.argv[1])
pairs = [a.split("=", 1) for a in sys.argv[2:]]
tmp = "/tmp/_cmp"
shutil.rmtree(tmp, ignore_errors=True)
os.makedirs(tmp, exist_ok=True)

files = []
for label, path in pairs:
    if not os.path.exists(path):
        continue
    dest = os.path.join(tmp, "%s.png" % label)
    shutil.copy(path, dest)
    files.append(dest)

cols = min(4, len(files)) or 1
cell_w = out_w // cols
sample = Image.open(files[0])
cell_h = int(cell_w * sample.height / sample.width)
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (out_w, rows * (cell_h + 16)), (18, 18, 18))
draw = ImageDraw.Draw(sheet)
for i, path in enumerate(files):
    im = Image.open(path).convert("RGB").resize((cell_w, cell_h))
    x, y = (i % cols) * cell_w, (i // cols) * (cell_h + 16)
    sheet.paste(im, (x, y + 16))
    draw.text((x + 4, y + 2), os.path.basename(path).replace(".png", ""), fill=(235, 235, 235))

buf = io.BytesIO()
sheet.save(buf, "JPEG", quality=70)
data = buf.getvalue()
b64 = base64.b64encode(data).decode()
print("SIZE %d %d %d" % (len(data), sheet.width, len(files)))
for i in range(0, len(b64), 1000):
    print("B64" + b64[i:i + 1000])
print("END")
