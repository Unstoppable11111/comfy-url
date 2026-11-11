import paramiko
import time
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

    def run_cmd(cmd, wait_time=2):
        while shell.recv_ready():
            shell.recv(4096)
        shell.send(cmd + "\n")
        time.sleep(wait_time)
        res = recv_timeout(wait_time).strip()
        clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', res)
        return clean

    py_check = '''cat << 'EOF' > /tmp/check_q21_diff.py
from safetensors import safe_open
with safe_open('/ComfyUI/models/diffusion_models/qwen_image_2.1_int8_convrot.safetensors', framework='pt', device='cpu') as f:
    top_keys = [k for k in f.keys() if not k.startswith('transformer_blocks.')]
    for k in sorted(top_keys):
        print(k, f.get_tensor(k).shape)
    b0_keys = [k for k in f.keys() if k.startswith('transformer_blocks.0.')]
    print("--- BLOCK 0 ---")
    for k in sorted(b0_keys):
        print(k, f.get_tensor(k).shape)
EOF
/root/miniconda3/envs/comfyui/bin/python /tmp/check_q21_diff.py
'''
    print(run_cmd(py_check, wait_time=3), flush=True)
    print("=== MODEL.PY ===", flush=True)
    print(run_cmd("tail -n 140 /ComfyUI/comfy/ldm/qwen_image/model.py", wait_time=2), flush=True)

finally:
    client.close()
