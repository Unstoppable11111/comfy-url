import json, urllib.request

def get(path):
    with urllib.request.urlopen("http://127.0.0.1:8081" + path, timeout=60) as r:
        return json.loads(r.read().decode())

oi = get("/object_info")
print("total nodes:", len(oi))
qwen = sorted(k for k in oi if "qwen" in k.lower())
print("qwen nodes:", qwen)
for loader, key, label in [("UNETLoader", "unet_name", "diffusion_models"),
                           ("CLIPLoader", "clip_name", "text_encoders"),
                           ("VAELoader", "vae_name", "vae")]:
    try:
        vals = oi[loader]["input"]["required"][key][0]
        print(label + ":", [v for v in vals if "qwen" in v.lower()])
    except Exception as e:
        print(label, "ERR", e)

st = get("/system_stats")
print("comfyui version:", st.get("system", {}).get("comfyui_version"))
print("vram:", st.get("devices"))
