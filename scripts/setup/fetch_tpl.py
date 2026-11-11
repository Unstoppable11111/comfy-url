import base64, json, os, urllib.request

NAMES = [
    "image_qwen_image_2_1_t2i",
    "image_qwen_image_2_1_image_edit",
    "image_qwen_image_2_1_turbo_t2i",
    "image_qwen_image_2_1_turbo_image_edit",
]
DEST = "/ComfyUI/user/default/workflows"
os.makedirs(DEST, exist_ok=True)

for name in NAMES:
    url = ("https://api.github.com/repos/Comfy-Org/workflow_templates/contents/"
           "templates/%s.json?ref=main" % name)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "comfy-setup"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
        raw = base64.b64decode(data["content"])
        path = os.path.join(DEST, name + ".json")
        with open(path, "wb") as f:
            f.write(raw)
        print("OK", name, len(raw), "bytes")
    except Exception as e:
        print("FAIL", name, type(e).__name__, e)
