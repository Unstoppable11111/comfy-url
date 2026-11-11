import json, time, urllib.request

BASE = "http://127.0.0.1:8081"

def post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=120) as r:
        return json.loads(r.read().decode())

g = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_2.1_int8_convrot.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "QwenImage21Cache", "inputs": {"model": ["1", 0], "device": "auto", "dtype": "default"}},
    "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_8b_int8_convrot.safetensors", "type": "qwen_image", "device": "default"}},
    "4": {"class_type": "TextEncodeQwenImage21", "inputs": {"clip": ["3", 0], "prompt": "A vertical photograph of a red apple on a wooden table, soft window light from the left, shallow depth of field.", "negative_prompt": "", "resolution": 1024}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
    "6": {"class_type": "KSampler", "inputs": {"model": ["2", 0], "seed": 12345, "steps": 25, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "positive": ["4", 0], "negative": ["4", 1], "latent_image": ["5", 0], "denoise": 1.0}},
    "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["8", 0]}},
    "8": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"}},
    "9": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "qwen21_smoke"}},
}

try:
    res = post("/prompt", {"prompt": g, "client_id": "smoke"})
    print("submit:", res, flush=True)
except Exception as e:
    body = getattr(e, "read", lambda: b"")()
    print("submit FAILED:", e, body[:2000], flush=True)
    raise SystemExit(1)

pid = res.get("prompt_id")
deadline = time.time() + 900
while time.time() < deadline:
    time.sleep(10)
    h = get("/history/" + pid)
    if pid in h:
        entry = h[pid]
        print("status:", entry.get("status"), flush=True)
        outs = entry.get("outputs", {})
        for k, v in outs.items():
            print("output", k, json.dumps(v)[:500], flush=True)
        print("DONE", flush=True)
        break
    q = get("/queue")
    print("waiting... running=%s pending=%s" % (len(q.get("queue_running", [])), len(q.get("queue_pending", []))), flush=True)
else:
    print("TIMEOUT", flush=True)
