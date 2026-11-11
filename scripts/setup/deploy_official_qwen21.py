import paramiko
import time
import base64
import os
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
    print("[1/3] 连接算家云容器，准备同步 ComfyUI 官方最新 QwenImage21 原生模块...", flush=True)
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

    time.sleep(0.8)
    recv_timeout(1.5)
    shell.send("0\n")
    time.sleep(1.2)
    recv_timeout(1.5)
    shell.send("\n")
    time.sleep(0.5)
    recv_timeout(1)

    def run_cmd(cmd, wait_time=1.5):
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
        chunk_size = 30000
        for i in range(0, len(b64), chunk_size):
            chunk = b64[i:i+chunk_size]
            run_cmd(f"echo -n '{chunk}' >> /tmp/up.b64", wait_time=0.5)
        run_cmd(f"base64 -d /tmp/up.b64 > {remote_path} && rm -f /tmp/up.b64", wait_time=0.8)
        print(f"已同步官方文件 -> {remote_path}", flush=True)

    run_cmd("mkdir -p /ComfyUI/comfy/ldm/qwen_image21 && touch /ComfyUI/comfy/ldm/qwen_image21/__init__.py", wait_time=0.5)
    upload_file(r"e:\codex\video\scripts\latest_qwen21_model.py", "/ComfyUI/comfy/ldm/qwen_image21/model.py")
    upload_file(r"e:\codex\video\scripts\latest_te_qwen21.py", "/ComfyUI/comfy/text_encoders/qwen_image21.py")
    upload_file(r"e:\codex\video\scripts\latest_wan_vae22.py", "/ComfyUI/comfy/ldm/wan/vae2_2.py")
    upload_file(r"e:\codex\video\scripts\latest_nodes_qwen.py", "/ComfyUI/comfy_extras/nodes_qwen.py")

    print("[2/3] 正在注册 QwenImage21 到 ComfyUI 核心注册表...", flush=True)
    # 下载 comfy/ops.py 与 comfy/rmsnorm.py 检查 linear_input_act 是否存在
    print(run_cmd("ls -lh /ComfyUI/models/vae/", wait_time=1), flush=True)
    print(run_cmd("/root/miniconda3/envs/comfyui/bin/python -c 'import sys; sys.path.append(\"/ComfyUI\"); import comfy.ldm.qwen_image21.model; import comfy.text_encoders.qwen_image21; print(\"IMPORT_QWEN21_OK\")'", wait_time=3), flush=True)

finally:
    client.close()
