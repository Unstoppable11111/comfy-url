import base64, io
from PIL import Image

im = Image.open("/ComfyUI/output/qwen21_smoke_00001_.png").convert("RGB")
im.thumbnail((560, 560))
buf = io.BytesIO()
im.save(buf, "JPEG", quality=72)
data = buf.getvalue()
print("B64START" + base64.b64encode(data).decode() + "B64END")
print("SIZE", len(data))
