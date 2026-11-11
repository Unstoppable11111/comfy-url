import paramiko
import time
import base64
import re
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

hostname = "hb-a.suanjiayun.com"
port = 2020
username = "18379685528"
password = "980822cyc4435"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print("[1/4] 连接算家云并同步剩余 4 个核心依赖库...", flush=True)
    client.connect(hostname, port=port, username=username, password=password, timeout=15, allow_agent=False, look_for_keys=False)
    shell = client.invoke_shell(term='xterm', width=200, height=50)
    
    def recv_timeout(timeout=2):
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
    recv_timeout(2)
    shell.send("0\n")
    time.sleep(2)
    recv_timeout(2)
    shell.send("\n")
    time.sleep(1)
    recv_timeout(1)

    def run_cmd(cmd, wait_time=2):
        while shell.recv_ready():
            shell.recv(4096)
        shell.send(cmd + "\n")
        time.sleep(wait_time)
        res = recv_timeout(wait_time).strip()
        clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', res)
        return clean

    def upload_file(local_path, remote_path):
        with open(local_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        run_cmd(f"mkdir -p $(dirname {remote_path}) && rm -f /tmp/up.b64", wait_time=0.5)
        chunk_size = 25000
        for i in range(0, len(b64), chunk_size):
            chunk = b64[i:i+chunk_size]
            run_cmd(f"echo -n '{chunk}' >> /tmp/up.b64", wait_time=0.3)
        run_cmd(f"base64 -d /tmp/up.b64 > {remote_path} && rm -f /tmp/up.b64", wait_time=0.5)
        print(f"已同步 -> {remote_path}", flush=True)

    upload_file(r"e:\codex\video\scripts\rmsnorm.py", "/ComfyUI/comfy/rmsnorm.py")
    upload_file(r"e:\codex\video\scripts\model_prefetch.py", "/ComfyUI/comfy/model_prefetch.py")
    upload_file(r"e:\codex\video\scripts\quant_ops.py", "/ComfyUI/comfy/quant_ops.py")
    upload_file(r"e:\codex\video\scripts\model_animate2.py", "/ComfyUI/comfy/ldm/wan/model_animate2.py")

    print("[2/4] 验证 QwenImage21 模块导入与模型加载兼容性...", flush=True)
    test_py = '''/root/miniconda3/envs/comfyui/bin/python -c '
import sys
sys.path.append("/ComfyUI")
try:
    import comfy.ldm.qwen_image21.model
    import comfy.text_encoders.qwen_image21
    import comfy.supported_models
    import comfy.model_base
    print("ALL_QWEN21_COMPAT_OK")
except Exception as e:
    import traceback
    traceback.print_exc()
'
'''
    res = run_cmd(test_py, wait_time=3)
    print("兼容性验证结果:\n", res, flush=True)

    print("[3/4] 重启 ComfyUI 服务并等待 8081 就绪...", flush=True)
    run_cmd("pkill -9 -f 'main.py' || true", wait_time=1)
    run_cmd("nohup /root/miniconda3/envs/comfyui/bin/python /ComfyUI/main.py --listen 0.0.0.0 --port 8081 > /ComfyUI/comfyui.log 2>&1 &", wait_time=2)

    for i in range(25):
        res_stats = run_cmd("curl -s http://127.0.0.1:8081/system_stats", wait_time=1)
        if "ram_total" in res_stats:
            print(f"ComfyUI 服务在第 {i+1} 秒完全就绪，8081 正常监听！", flush=True)
            break
        time.sleep(1)

    print("[4/4] 提交红果短剧出图工作流并进行 GPU 渲染与回传...", flush=True)
    render_script = '''
import urllib.request
import json
import time
import glob
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
            "type": "sd3"
        }
    },
    "3": {
        "class_type": "VAELoader",
        "inputs": {
            "vae_name": "qwen_image_vae.safetensors"
        }
    },
    "4": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["2", 0],
            "text": "中国现代都市短剧剧照，年轻英俊的中国豪门总裁男主，身穿高定黑色西装，站在落地窗前俯瞰城市夜景，眼神凌厉冷峻，五官立体真实，电影级光影，35mm胶片质感，高清8k"
        }
    },
    "5": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["2", 0],
            "text": "模糊，低画质，变形，欧美面孔，油腻皮肤"
        }
    },
    "6": {
        "class_type": "EmptySD3LatentImage",
        "inputs": {
            "width": 1024,
            "height": 1024,
            "batch_size": 1
        }
    },
    "7": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["1", 0],
            "positive": ["4", 0],
            "negative": ["5", 0],
            "latent_image": ["6", 0],
            "seed": 88888,
            "steps": 25,
            "cfg": 3.5,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1.0
        }
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["7", 0],
            "vae": ["3", 0]
        }
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": "Qwen21_Final_Render",
            "images": ["8", 0]
        }
    }
}

req_data = json.dumps({"prompt": prompt}).encode('utf-8')
req = urllib.request.Request("http://127.0.0.1:8081/prompt", data=req_data, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as resp:
    res_json = json.loads(resp.read().decode('utf-8'))
    prompt_id = res_json['prompt_id']
    print(f"PROMPT_SUBMITTED: {prompt_id}", flush=True)

start_time = time.time()
while time.time() - start_time < 120:
    time.sleep(3)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8081/history/" + prompt_id) as h_resp:
            h_data = json.loads(h_resp.read().decode('utf-8'))
            if prompt_id in h_data:
                print("RENDER_COMPLETED_IN_HISTORY", flush=True)
                break
    except Exception as e:
        pass

files = glob.glob("/ComfyUI/output/Qwen21_Final_Render*.png")
if files:
    latest = max(files, key=os.path.getmtime)
    print("FOUND_IMAGE:", latest, flush=True)
    with open(latest, "rb") as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
    with open("/tmp/render_done.b64", "w") as f:
        f.write(b64)
    print("B64_SAVED_BYTES:", len(b64), flush=True)
else:
    print("NO_IMAGE_FOUND", flush=True)
'''
    run_cmd("rm -f /tmp/render_done.b64 /tmp/part_done_* /ComfyUI/output/Qwen21_Final_Render*.png", wait_time=1)
    run_cmd("cat << 'EOF' > /tmp/do_render.py" + render_script + "\nEOF", wait_time=1)
    shell.send("/root/miniconda3/envs/comfyui/bin/python -u /tmp/do_render.py\n")

    start_wait = time.time()
    while time.time() - start_wait < 95:
        time.sleep(5)
        chunk = recv_timeout(1)
        if chunk.strip():
            clean_chunk = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', chunk).strip()
            print(f"[GPU 实时输出] {clean_chunk}", flush=True)
        if "B64_SAVED_BYTES" in chunk or "NO_IMAGE_FOUND" in chunk:
            break

    tail_log = run_cmd("tail -n 25 /ComfyUI/comfyui.log", wait_time=2)
    print("ComfyUI 引擎日志:\n", tail_log, flush=True)

    print("正在拉取图片回传本地...", flush=True)
    run_cmd("split -b 50000 /tmp/render_done.b64 /tmp/part_done_", wait_time=1)
    parts_raw = run_cmd("ls /tmp/part_done_* 2>/dev/null", wait_time=1)
    parts = [p.strip() for p in parts_raw.split() if p.strip().startswith('/tmp/part_done_')]
    print(f"Base64 分块数量: {len(parts)}", flush=True)

    if len(parts) > 2:
        full_b64 = ""
        for p in sorted(parts):
            while shell.recv_ready():
                shell.recv(4096)
            shell.send(f"cat {p}\n")
            time.sleep(0.8)
            part_content = recv_timeout(2)
            lines = part_content.strip().splitlines()
            clean_lines = [l.strip() for l in lines if not l.startswith("(base)") and not l.startswith("cat /tmp") and not l.endswith("#")]
            full_b64 += "".join(clean_lines)

        full_b64 = re.sub(r'[^A-Za-z0-9+/=]', '', full_b64)
        missing_padding = len(full_b64) % 4
        if missing_padding:
            full_b64 += '=' * (4 - missing_padding)

        img_bytes = base64.b64decode(full_b64)
        local_path = r"e:\codex\video\test_render.png"
        with open(local_path, "wb") as f:
            f.write(img_bytes)
        print(f"🎉 SUCCESS_SAVED: {local_path} ({len(img_bytes)/1024:.2f} KB)", flush=True)
    else:
        print("未获取到图片文件分块", flush=True)

finally:
    client.close()
