"""检查本机 ComfyUI 的版本、Qwen 节点与模型是否可见。

    COMFY=http://127.0.0.1:8080 python3 check_remote.py
"""
import json
import os
import urllib.request

BASE = os.environ.get("COMFY", "http://127.0.0.1:8081").rstrip("/")


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read().decode())


oi = get("/object_info")
print("total nodes:", len(oi))
qwen = sorted(k for k in oi if "qwen" in k.lower() and "Image" in k)
print("qwen image nodes:", qwen)

for loader, key, label in [("UNETLoader", "unet_name", "diffusion_models"),
                           ("CLIPLoader", "clip_name", "text_encoders"),
                           ("VAELoader", "vae_name", "vae")]:
    try:
        vals = oi[loader]["input"]["required"][key][0]
        hit = [v for v in vals if "qwen" in v.lower()]
        print(label + ":", hit[:8])
    except Exception as e:
        print(label, "ERR", e)

st = get("/system_stats")
s = st.get("system", {})
print("version:", s.get("comfyui_version"), "| torch:", s.get("pytorch_version"))
dev = st.get("devices", [{}])[0]
print("gpu:", dev.get("name"), "| vram_total:", dev.get("vram_total"))
