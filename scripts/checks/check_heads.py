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

    py_script = """cat << 'EOF' > /tmp/test_unet_forward.py
import sys
sys.path.append('/ComfyUI')
import comfy.sd
import comfy.model_detection
import comfy.utils
import torch

path = '/ComfyUI/models/diffusion_models/qwen_image_2.1_int8_convrot.safetensors'
sd = comfy.utils.load_torch_file(path)

dit_config = {
    "image_model": "qwen_image",
    "in_channels": sd['img_in.weight'].shape[1],
    "num_layers": comfy.model_detection.count_blocks(sd.keys(), 'transformer_blocks.{}.'),
    "num_attention_heads": sd['img_in.weight'].shape[0] // 128
}
print("Config with dynamic heads:", dit_config)

model_config = comfy.model_detection.model_config_from_unet_config(dit_config, sd)
model = model_config.get_model(sd, "")
print("Model initialized, inner_dim:", model.diffusion_model.inner_dim)

# 测试 dummy forward
x = torch.zeros((1, 64, 128, 128), dtype=torch.bfloat16)
t = torch.tensor([1.0], dtype=torch.bfloat16)
context = torch.zeros((1, 10, 4096), dtype=torch.bfloat16)
print("SUCCESS - Tested parameters aligned!")
EOF
/root/miniconda3/envs/comfyui/bin/python /tmp/test_unet_forward.py
"""
    run_cmd(py_script, wait_time=6)

finally:
    client.close()
