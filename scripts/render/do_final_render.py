import paramiko
import time
import json
import base64
import os
import re

hostname = "hb-a.suanjiayun.com"
port = 2020
username = "18379685528"
password = "980822cyc4435"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print("[1/4] 连接云端终端并打入单行探测补丁...")
    client.connect(
        hostname, 
        port=port, 
        username=username, 
        password=password, 
        timeout=15,
        allow_agent=False,
        look_for_keys=False
    )
    shell = client.invoke_shell(term='xterm', width=200, height=50)
    
    def recv_timeout(timeout=4):
        start = time.time()
        buf = ""
        while time.time() - start < timeout:
            if shell.recv_ready():
                chunk = shell.recv(4096).decode('utf-8', errors='ignore')
                buf += chunk
            else:
                time.sleep(0.05)
        return buf

    time.sleep(1)
    recv_timeout(3)
    shell.send("0\n")
    time.sleep(2)
    recv_timeout(3)
    shell.send("\n")
    time.sleep(1)
    recv_timeout(2)

    def run_cmd(cmd, wait_time=2):
        while shell.recv_ready():
            shell.recv(4096)
        shell.send(cmd + "\n")
        time.sleep(wait_time)
        res = recv_timeout(wait_time).strip()
        clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', res)
        return clean

    # 1. 补丁 model_detection.py 支持 txt_in.text_norm.weight
    patch_code = """cat << 'EOF' > /tmp/apply_patch.py
with open('/ComfyUI/comfy/model_detection.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = "if '{}txt_norm.weight'.format(key_prefix) in state_dict_keys:  # Qwen Image"
replacement = "if ('{}txt_norm.weight'.format(key_prefix) in state_dict_keys or '{}txt_in.text_norm.weight'.format(key_prefix) in state_dict_keys):  # Qwen Image"

if target in content:
    content = content.replace(target, replacement)
    with open('/ComfyUI/comfy/model_detection.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("PATCH_APPLIED_SUCCESS")
else:
    print("TARGET_ALREADY_PATCHED_OR_NOT_FOUND")
EOF
/root/miniconda3/envs/comfyui/bin/python /tmp/apply_patch.py
"""
    p_out = run_cmd(patch_code, wait_time=2)
    print("补丁应用结果:", p_out)

    # 2. 重启 ComfyUI
    print("[2/4] 重启 ComfyUI 进程以应用更新...")
    run_cmd("pkill -9 -f 'main.py' || true", wait_time=2)
    run_cmd("nohup /root/miniconda3/envs/comfyui/bin/python /ComfyUI/main.py --listen 0.0.0.0 --port 8081 > /ComfyUI/comfyui.log 2>&1 &", wait_time=3)
    
    # 等待服务就绪
    for _ in range(15):
        res = run_cmd("curl -s http://127.0.0.1:8081/system_stats")
        if "system" in res:
            print("ComfyUI 已成功启动并就绪！")
            break
        time.sleep(1)

    # 3. 提交生图任务
    print("[3/4] 提交 Qwen-Image 官方测试任务（25步渲染）...")
    gen_script = """cat << 'EOF' > /tmp/run_final.py
import urllib.request
import json
import time
import os
import base64

prompt = {
    "1": {
        "class_type": "UNETLoader",
        "inputs": {
            "unet_name": "qwen_image_2.1_int8_convrot.safetensors",
            "weight_dtype": "default"
        }
    },
    "2": {
        "class_type": "CLIPLoader",
        "inputs": {
            "clip_name": "qwen3vl_8b_int8_convrot.safetensors",
            "type": "qwen_image",
            "device": "default"
        }
    },
    "3": {
        "class_type": "VAELoader",
        "inputs": {
            "vae_name": "qwen_image_vae.safetensors"
        }
    },
    "4": {
        "class_type": "ModelSamplingAuraFlow",
        "inputs": {
            "model": ["1", 0],
            "shift": 3.1
        }
    },
    "5": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["2", 0],
            "text": "A cinematic close-up portrait of a handsome modern East Asian young man, standing under warm ambient street lights at night, wearing a stylish dark jacket, authentic 35mm film photography, highly detailed, realistic skin texture, sharp focus, 8k resolution"
        }
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["2", 0],
            "text": "low quality, blurry, deformed fingers, extra limbs, bad anatomy, ugly, oversaturated, plastic look"
        }
    },
    "7": {
        "class_type": "EmptySD3LatentImage",
        "inputs": {
            "width": 1024,
            "height": 1024,
            "batch_size": 1
        }
    },
    "8": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["4", 0],
            "positive": ["5", 0],
            "negative": ["6", 0],
            "latent_image": ["7", 0],
            "seed": 20261110,
            "steps": 25,
            "cfg": 4.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1.0
        }
    },
    "9": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["8", 0],
            "vae": ["3", 0]
        }
    },
    "10": {
        "class_type": "SaveImage",
        "inputs": {
            "images": ["9", 0],
            "filename_prefix": "Qwen_Final_OK"
        }
    }
}

req_data = json.dumps({"prompt": prompt}).encode('utf-8')
req = urllib.request.Request("http://127.0.0.1:8081/prompt", data=req_data, headers={'Content-Type': 'application/json'})

with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode('utf-8'))
pid = res['prompt_id']
print(f"PROMPT_STARTED:{pid}")

for i in range(120):
    time.sleep(2)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8081/history/{pid}") as hresp:
            hdata = json.loads(hresp.read().decode('utf-8'))
        if pid in hdata:
            entry = hdata[pid]
            if "status" in entry and entry["status"].get("status_str") == "error":
                print("FAILED_IN_HISTORY:", entry["status"])
                break
            outputs = entry.get('outputs', {})
            if '10' in outputs and 'images' in outputs['10']:
                img_info = outputs['10']['images'][0]
                fpath = os.path.join('/ComfyUI/output', img_info.get('subfolder', ''), img_info['filename'])
                print(f"RENDER_FILE_SUCCESS:{fpath}")
                with open(fpath, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode('utf-8')
                with open('/tmp/final_render.b64', 'w') as bf:
                    bf.write(b64)
                print("B64_DUMPED_DONE")
                break
    except Exception as e:
        pass
EOF"""
    run_cmd(gen_script, wait_time=2)
    print("开始在 RTX 3090 GPU 上全流程推理（耗时约 35 秒）...")
    out_run = run_cmd("/root/miniconda3/envs/comfyui/bin/python /tmp/run_final.py", wait_time=45)
    print(out_run)

    # 4. 回传图片
    print("[4/4] 正在拉取生成的图片到本地工作区...")
    tail_l = run_cmd("tail -n 20 /ComfyUI/comfyui.log", wait_time=2)
    print("ComfyUI 最新日志:\n", tail_l)

    run_cmd("split -b 60000 /tmp/final_render.b64 /tmp/final_part_")
    parts_raw = run_cmd("ls /tmp/final_part_*")
    parts = [p.strip() for p in parts_raw.split() if 'final_part_' in p]
    
    full_b64 = ""
    for p in sorted(parts):
        while shell.recv_ready():
            shell.recv(4096)
        shell.send(f"cat {p}\n")
        time.sleep(1)
        part_content = recv_timeout(3)
        lines = part_content.strip().splitlines()
        clean_lines = [l.strip() for l in lines if not l.startswith("(base)") and not l.startswith("cat /tmp")]
        full_b64 += "".join(clean_lines)

    if full_b64:
        img_bytes = base64.b64decode(full_b64)
        local_path = r"e:\codex\video\test_render.png"
        with open(local_path, "wb") as f:
            f.write(img_bytes)
        print(f"\n==========================================")
        print(f"SUCCESS: 已成功回传本地: {local_path}, 大小: {len(img_bytes)/1024:.2f} KB")
        print(f"==========================================")

finally:
    client.close()
