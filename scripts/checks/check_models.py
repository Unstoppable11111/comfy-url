import json, os, struct, sys, urllib.request

FILES = {
    "diffusion_models/qwen_image_2.1_int8_convrot.safetensors":
        "/ComfyUI/models/diffusion_models/qwen_image_2.1_int8_convrot.safetensors",
    "text_encoders/qwen3vl_8b_int8_convrot.safetensors":
        "/ComfyUI/models/clip/qwen3vl_8b_int8_convrot.safetensors",
}

def check_safetensors(path):
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(8)
        if len(head) < 8:
            return size, "TOO_SHORT"
        n = struct.unpack("<Q", head)[0]
        if n <= 0 or n > 100 * 1024 * 1024:
            return size, "BAD_HEADER_LEN(%d)" % n
        raw = f.read(n)
        if len(raw) < n:
            return size, "HEADER_TRUNCATED"
        try:
            meta = json.loads(raw)
        except Exception as e:
            return size, "HEADER_JSON_ERR(%s)" % e
    max_end = 0
    for k, v in meta.items():
        if k == "__metadata__":
            continue
        try:
            end = v["data_offsets"][1]
        except Exception:
            continue
        max_end = max(max_end, end)
    need = 8 + n + max_end
    if size < need:
        return size, "TRUNCATED need=%.3fGB missing=%.3fGB" % (need / 1e9, (need - size) / 1e9)
    return size, "OK tensor_end=%.3fGB tail_bytes=%d" % (max_end / 1e9, size - (8 + n + max_end))

print("== local files ==")
for key, path in FILES.items():
    if not os.path.exists(path):
        print(key, "MISSING")
        continue
    size, status = check_safetensors(path)
    print("%s\n  size=%.3fGB status=%s" % (key, size / 1e9, status))

print("")
print("== modelscope api ==")
url = "https://modelscope.cn/api/v1/models/Comfy-Org/Qwen-Image-2.1/repo/files?Revision=master"
try:
    req = urllib.request.Request(url, headers={"User-Agent": "python"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    files = data.get("Data", {}).get("Files", [])
    for f in files:
        print(f.get("Path"), f.get("Size"))
except Exception as e:
    print("api error:", type(e).__name__, e)
