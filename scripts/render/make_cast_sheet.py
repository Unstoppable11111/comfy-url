"""汇总定妆照 + 参考图测试结果，拼一张预览图并输出 base64。"""
import base64
import io
import os
import shutil

from PIL import Image, ImageDraw

SRC = [
    ("/ComfyUI/output/drama/cast_qianlong", ""),
    ("/ComfyUI/output/drama/cast_fengming", "F_"),
]
EXTRA = ["/ComfyUI/output/test_ref_00001_.png"]
TMP = "/tmp/cast_all"

shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP, exist_ok=True)
for d, prefix in SRC:
    if not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        if f.endswith(".png"):
            shutil.copy(os.path.join(d, f), os.path.join(TMP, prefix + f))
for f in EXTRA:
    if os.path.exists(f):
        shutil.copy(f, os.path.join(TMP, "REF_" + os.path.basename(f)))

files = sorted(f for f in os.listdir(TMP) if f.endswith(".png"))
cols, out_w = 4, 640
cell_w = out_w // cols
sample = Image.open(os.path.join(TMP, files[0]))
cell_h = int(cell_w * sample.height / sample.width)
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (out_w, rows * (cell_h + 16)), (18, 18, 18))
draw = ImageDraw.Draw(sheet)
for i, name in enumerate(files):
    im = Image.open(os.path.join(TMP, name)).convert("RGB").resize((cell_w, cell_h))
    x, y = (i % cols) * cell_w, (i // cols) * (cell_h + 16)
    sheet.paste(im, (x, y + 16))
    draw.text((x + 4, y + 2), name.replace(".png", ""), fill=(235, 235, 235))

buf = io.BytesIO()
sheet.save(buf, "JPEG", quality=70)
data = buf.getvalue()
b64 = base64.b64encode(data).decode()
print("SIZE %d %d %d" % (len(data), sheet.width, len(files)))
for i in range(0, len(b64), 1000):
    print("B64" + b64[i:i + 1000])
print("END")
