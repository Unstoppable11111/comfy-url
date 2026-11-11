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

    print(run_cmd("grep -rn 'in_layer' /ComfyUI/comfy/ /ComfyUI/custom_nodes/ 2>/dev/null | head -n 30", wait_time=2), flush=True)
    print(run_cmd("grep -rn 'text_norm' /ComfyUI/comfy/ /ComfyUI/custom_nodes/ 2>/dev/null | head -n 30", wait_time=2), flush=True)
    print(run_cmd("ls /ComfyUI/comfy/ldm/", wait_time=1), flush=True)

finally:
    client.close()
