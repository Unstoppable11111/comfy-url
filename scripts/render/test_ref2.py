"""对比参考图传参写法：找出真正能锁住角色的一种。"""
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8080"

def post(p, payload):
    req = urllib.request.Request(BASE + p, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"HTTP_ERROR": e.code, "body": e.read().decode()[:800]}

def get(p):
    with urllib.request.urlopen(BASE + p, timeout=120) as r:
        return json.loads(r.read().decode())

def build(te_inputs, prefix, seed=11):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_2.1_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "QwenImage21Cache", "inputs": {"model": ["1", 0], "device": "auto", "dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_8b_int8_convrot.safetensors", "type": "qwen_image", "device": "default"}},
        "8": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"}},
        "10": {"class_type": "LoadImage", "inputs": {"image": "ref_C01.png"}},
        "4": {"class_type": "TextEncodeQwenImage21", "inputs": te_inputs},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 768, "height": 1344, "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {"model": ["2", 0], "seed": seed, "steps": 25, "cfg": 1.0,
                                                   "sampler_name": "euler", "scheduler": "simple",
                                                   "positive": ["4", 0], "negative": ["4", 1],
                                                   "latent_image": ["5", 0], "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["8", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": prefix}},
    }

PROMPT = "把画面中这个人物放到豪华现代客厅里，中景，保持长相和服装完全一致，电影感写实摄影"
BASE_IN = {"clip": ["3", 0], "prompt": PROMPT, "negative_prompt": "", "resolution": 1024}

variants = {
    "A_nested_vae": dict(BASE_IN, vae=["8", 0], images={"image_1": ["10", 0]}),
    "B_flat_vae": dict(BASE_IN, vae=["8", 0], image_1=["10", 0]),
    "C_nested_novae": dict(BASE_IN, images={"image_1": ["10", 0]}),
}

for name, te in variants.items():
    res = post("/prompt", {"prompt": build(te, "ref_test_" + name)})
    if "prompt_id" not in res:
        print(name, "FAILED", json.dumps(res, ensure_ascii=False)[:400], flush=True)
        continue
    pid = res["prompt_id"]
    st = "?"
    for _ in range(40):
        time.sleep(3)
        h = get("/history/" + pid)
        if pid in h:
            st = h[pid]["status"]["status_str"]
            break
    print(name, "->", st, flush=True)
