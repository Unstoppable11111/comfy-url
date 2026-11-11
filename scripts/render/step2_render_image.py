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
    print("[1/3] 正在连接实例终端...")
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

    print("[2/3] 正在向 ComfyUI 提交原生标准工作流生图任务...")
    render_script = """cat << 'EOF' > /tmp/do_generate.py
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
            "filename_prefix": "Qwen_Verify"
        }
    }
}

req_data = json.dumps({"prompt": prompt}).encode('utf-8')
req = urllib.request.Request("http://127.0.0.1:8081/prompt", data=req_data, headers={'Content-Type': 'application/json'})

with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode('utf-8'))
pid = res['prompt_id']
print(f"PROMPT_SUBMITTED:{pid}")

# 轮询直到出图完成
for sec in range(90):
    time.sleep(2)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8081/history/{pid}") as hresp:
            hdata = json.loads(hresp.read().decode('utf-8'))
        if pid in hdata:
            outputs = hdata[pid].get('outputs', {})
            img_info = outputs['10']['images'][0]
            fpath = os.path.join('/ComfyUI/output', img_info.get('subfolder', ''), img_info['filename'])
            print(f"RENDER_SUCCESS_PATH:{fpath}")
            # 保存 base64 准备回传
            with open(fpath, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            with open('/tmp/final_render.b64', 'w') as bf:
                bf.write(b64)
            print("BASE64_SAVED")
            break
    except Exception as e:
        pass
EOF"""
    run_cmd(render_script, wait_time=2)
    print("正在 GPU 上执行 25 步去噪渲染与 VAE 解码（预计 25~35 秒）...")
    gen_out = run_cmd("/root/miniconda3/envs/comfyui/bin/python /tmp/do_generate.py", wait_time=45)
    print(gen_out)

    print("[3/3] 检查生成结果并回传至本地工作区...")
    tail_log = run_cmd("tail -n 20 /ComfyUI/comfyui.log", wait_time=2)
    print("ComfyUI 日志:\n", tail_log)

    b64_check = run_cmd("ls -lh /tmp/final_render.b64", wait_time=1)
    print("生成的 Base64 文件:", b64_check)

    # 分块读取 base64
    run_cmd("split -b 60000 /tmp/final_render.b64 /tmp/render_part_")
    parts_raw = run_cmd("ls /tmp/render_part_*")
    parts = [p.strip() for p in parts_raw.split() if 'render_part_' in p]
    
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
        print(f"🎉 验证大获全胜！图片已成功保存到本地: {local_path}")
        print(f"图片体积: {len(img_bytes)/1024:.2f} KB")
        print(f"==========================================")
    else:
        print("未获取到图片数据")

finally:
    client.close()
