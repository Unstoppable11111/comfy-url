"""测试参考图（image_1）传参格式：LoadImage → TextEncodeQwenImage21.images"""
import json
import shutil
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8080"

def post(p, payload):
    req = urllib.request.Request(BASE + p, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"HTTP_ERROR": e.code, "body": e.read().decode()[:1500]}

def get(p):
    with urllib.request.urlopen(BASE + p, timeout=120) as r:
        return json.loads(r.read().decode())

# 把参考图放进 input 目录
shutil.copy("/ComfyUI/output/drama/cast_qianlong/C01_00001_.png", "/ComfyUI/input/ref_C01.png")

graph = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_2.1_int8_convrot.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "QwenImage21Cache", "inputs": {"model": ["1", 0], "device": "auto", "dtype": "default"}},
    "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_8b_int8_convrot.safetensors", "type": "qwen_image", "device": "default"}},
    "10": {"class_type": "LoadImage", "inputs": {"image": "ref_C01.png"}},
    "4": {"class_type": "TextEncodeQwenImage21", "inputs": {
        "clip": ["3", 0],
        "prompt": "同一个角色站在豪华客厅中，中景，神情冷峻，电影感写实摄影",
        "negative_prompt": "",
        "resolution": 1024,
        "images": {"image_1": ["10", 0]},
    }},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 768, "height": 1344, "batch_size": 1}},
    "6": {"class_type": "KSampler", "inputs": {"model": ["2", 0], "seed": 7, "steps": 25, "cfg": 1.0,
                                               "sampler_name": "euler", "scheduler": "simple",
                                               "positive": ["4", 0], "negative": ["4", 1],
                                               "latent_image": ["5", 0], "denoise": 1.0}},
    "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["8", 0]}},
    "8": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"}},
    "9": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "test_ref"}},
}

res = post("/prompt", {"prompt": graph})
print("RESP:", json.dumps(res, ensure_ascii=False)[:1200])
pid = res.get("prompt_id")
if pid:
    for _ in range(60):
        time.sleep(4)
        h = get("/history/" + pid)
        if pid in h:
            print("STATUS:", h[pid]["status"]["status_str"])
            print("OUT:", json.dumps(h[pid].get("outputs", {}))[:300])
            break
