import json, urllib.request

with urllib.request.urlopen("http://127.0.0.1:8081/object_info", timeout=60) as r:
    oi = json.loads(r.read().decode())

for name in ["UNETLoader", "CLIPLoader", "VAELoader", "TextEncodeQwenImage21",
             "QwenImage21Cache", "EmptyLatentImage", "KSampler", "VAEDecode",
             "SaveImage", "ModelSamplingAuraFlow", "CLIPTextEncode"]:
    if name not in oi:
        print(name, "MISSING")
        continue
    n = oi[name]
    req = n.get("input", {}).get("required", {})
    print("==", name, "->", n.get("output"))
    for k, v in req.items():
        t = v[0]
        if isinstance(t, list):
            t = "ENUM" + str(t[:8]) + ("..." if len(t) > 8 else "")
        print("   ", k, ":", t, "opts=", v[1] if len(v) > 1 else "")
