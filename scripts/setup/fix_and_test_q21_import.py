import paramiko
import time
import base64
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

hostname = "hb-a.suanjiayun.com"
port = 2020
username = "18379685528"
password = "980822cyc4435"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print("[1/3] 连接算家云并上传 attention.py 核心支持...", flush=True)
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
            run_cmd(f"echo -n '{chunk}' >> /tmp/up.b64", wait_time=0.4)
        run_cmd(f"base64 -d /tmp/up.b64 > {remote_path} && rm -f /tmp/up.b64", wait_time=0.8)
        print(f"已同步 -> {remote_path}", flush=True)

    # 上传 attention.py、model_base.py、model_detection.py、supported_models.py、latent_formats.py
    upload_file(r"e:\codex\video\scripts\latest_attention.py", "/ComfyUI/comfy/ldm/modules/attention.py")
    upload_file(r"e:\codex\video\scripts\latest_model_base.py", "/ComfyUI/comfy/model_base.py")
    upload_file(r"e:\codex\video\scripts\latest_model_detection.py", "/ComfyUI/comfy/model_detection.py")
    upload_file(r"e:\codex\video\scripts\latest_supported_models.py", "/ComfyUI/comfy/supported_models.py")
    upload_file(r"e:\codex\video\scripts\latest_latent_formats.py", "/ComfyUI/comfy/latent_formats.py")

    print("[2/3] 测试 Python 导入 QwenImage21 模块链...", flush=True)
    test_py = '''/root/miniconda3/envs/comfyui/bin/python -c '
import sys
sys.path.append("/ComfyUI")
try:
    import comfy.ldm.qwen_image21.model
    print("TEST 1: qwen_image21.model -> OK")
except Exception as e:
    print("TEST 1 ERROR:", e)

try:
    import comfy.text_encoders.qwen_image21
    print("TEST 2: text_encoders.qwen_image21 -> OK")
except Exception as e:
    print("TEST 2 ERROR:", e)

try:
    import comfy.supported_models
    print("TEST 3: supported_models -> OK")
except Exception as e:
    print("TEST 3 ERROR:", e)
'
'''
    res = run_cmd(test_py, wait_time=3)
    print(res, flush=True)

finally:
    client.close()
