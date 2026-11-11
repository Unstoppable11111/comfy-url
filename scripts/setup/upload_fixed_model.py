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
    print("[1/2] 上传解耦后的 qwen_image21/model.py...", flush=True)
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

    time.sleep(0.8)
    recv_timeout(1.5)
    shell.send("0\n")
    time.sleep(1.5)
    recv_timeout(1.5)
    shell.send("\n")
    time.sleep(0.5)
    recv_timeout(1)

    def run_cmd(cmd, wait_time=2):
        while shell.recv_ready():
            shell.recv(4096)
        shell.send(cmd + "\n")
        time.sleep(wait_time)
        res = recv_timeout(wait_time).strip()
        clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', res)
        return clean

    with open(r"e:\codex\video\scripts\latest_qwen21_model.py", "rb") as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    run_cmd("rm -f /tmp/up.b64", wait_time=0.3)
    chunk_size = 25000
    for i in range(0, len(b64), chunk_size):
        chunk = b64[i:i+chunk_size]
        run_cmd(f"echo -n '{chunk}' >> /tmp/up.b64", wait_time=0.3)
    run_cmd("base64 -d /tmp/up.b64 > /ComfyUI/comfy/ldm/qwen_image21/model.py && rm -f /tmp/up.b64", wait_time=0.5)

    print("[2/2] 校验 Python 导入 QwenImage21 模块...", flush=True)
    test_py = '''/root/miniconda3/envs/comfyui/bin/python -c '
import sys
sys.path.append("/ComfyUI")
import comfy.ldm.qwen_image21.model
import comfy.text_encoders.qwen_image21
import comfy.supported_models
import comfy.model_base
print("SUCCESS_QWEN21_ALL_CLEAR")
'
'''
    res = run_cmd(test_py, wait_time=3)
    print("导入结果:\n", res, flush=True)

finally:
    client.close()
