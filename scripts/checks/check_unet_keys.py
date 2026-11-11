import paramiko
import time
import re

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
    shell = client.invoke_shell(term='xterm', width=160, height=50)
    
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
        print(f"\n>>> {cmd} <<<\n{clean}")
        return clean

    py_script = """cat << 'EOF' > /tmp/check_unet_keys.py
from safetensors import safe_open
with safe_open('/ComfyUI/models/diffusion_models/qwen_image_2.1_int8_convrot.safetensors', framework='pt', device='cpu') as f:
    keys = list(f.keys())
    print("Total keys:", len(keys))
    print("First 20 keys:", keys[:20])
    print("txt_norm in keys?", any("txt_norm" in k for k in keys))
    for k in keys[:5]:
        t = f.get_slice(k)
        print("Slice:", k, t.get_shape())
EOF
/root/miniconda3/envs/comfyui/bin/python /tmp/check_unet_keys.py
"""
    run_cmd(py_script, wait_time=4)

finally:
    client.close()
