import json

path = "/ComfyUI/user/default/workflows/image_qwen_image_2_1_t2i.json"
wf = json.load(open(path))
print("top keys:", list(wf.keys()))

WANT = {"UNETLoader", "CLIPLoader", "VAELoader", "KSampler", "ModelSamplingAuraFlow",
        "TextEncodeQwenImage21", "EmptyLatentImage", "EmptySD3LatentImage", "QwenImage21Cache",
        "CLIPTextEncode", "VAEDecode", "SaveImage", "ModelSamplingSD3"}

def walk(obj, depth=0):
    if isinstance(obj, dict):
        if "type" in obj and isinstance(obj["type"], str) and obj["type"] in WANT:
            print("  " * depth + obj["type"], "widgets=", obj.get("widgets_values"))
        for v in obj.values():
            walk(v, depth)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, depth)

walk(wf)

print("\n--- subgraph definitions ---")
sg = wf.get("definitions", {}).get("subgraphs", [])
for s in sg:
    print("subgraph:", s.get("name"), s.get("id"))
    for n in s.get("nodes", []):
        if n.get("type") in WANT:
            print("   ", n["type"], n.get("widgets_values"))
