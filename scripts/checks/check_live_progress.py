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
    shell = client.invoke_shell(term='xterm', width=200, height=50)
    
    def recv_timeout(timeout=3):
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

    print("=== COMFYUI LOG TAIL ===")
    print(run_cmd("tail -n 40 /ComfyUI/comfyui.log", wait_time=2))

    print("\n=== COMFYUI OUTPUT DIR ===")
    print(run_cmd("ls -lh /ComfyUI/output", wait_time=2))

    print("\n=== SYSTEM_STATS ===")
    print(run_cmd("curl -s http://127.0.0.1:8081/system_stats", wait_time=2))

    print("\n=== CHECK MODEL DETECTION PATCH ===")
    print(run_cmd("grep -n -C 3 'num_attention_heads' /ComfyUI/comfy/model_detection.py", wait_time=2))

finally:
    client.close()
