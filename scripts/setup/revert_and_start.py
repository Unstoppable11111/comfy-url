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
    client.connect(hostname, port=port, username=username, password=password, timeout=10, allow_agent=False, look_for_keys=False)
    shell = client.invoke_shell(term='vt100', width=200, height=50)
    time.sleep(1); shell.recv(4096); shell.send("0\r"); time.sleep(1); shell.recv(4096); shell.send("\r"); time.sleep(2); shell.recv(8192)

    def run_cmd(cmd, wait_time=2):
        while shell.recv_ready():
            shell.recv(4096)
        shell.send(cmd + "\r")
        time.sleep(wait_time)
        buf = ""
        while shell.recv_ready():
            buf += shell.recv(4096).decode('utf-8', errors='ignore')
            time.sleep(0.05)
        clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', buf)
        return clean

    print("=== GIT CHECKOUT REVERT ===")
    print(run_cmd("cd /ComfyUI && git checkout comfy/model_base.py comfy/supported_models.py comfy/latent_formats.py comfy/ldm/modules/attention.py"))
    
    print("=== RESTART COMFYUI ===")
    run_cmd("pkill -9 -f 'main.py' || true")
    run_cmd("nohup /root/miniconda3/envs/comfyui/bin/python /ComfyUI/main.py --listen 0.0.0.0 --port 8081 > /ComfyUI/comfyui.log 2>&1 &")
    
    for i in range(20):
        time.sleep(1)
        res = run_cmd("curl -s http://127.0.0.1:8081/system_stats")
        if "ram_total" in res:
            print(f"ComfyUI 在第 {i+1} 秒完全启动成功，8081 在线！")
            break

finally:
    client.close()
