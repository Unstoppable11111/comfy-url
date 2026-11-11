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
    client.connect(hostname, port=port, username=username, password=password, timeout=15, allow_agent=False, look_for_keys=False)
    shell = client.invoke_shell(term='vt100', width=200, height=50)
    time.sleep(1); shell.recv(4096); shell.send("0\r"); time.sleep(1); shell.recv(4096); shell.send("\r"); time.sleep(2); shell.recv(8192)

    def run_cmd(cmd, wait_time=4):
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

    run_cmd("""cat << 'EOF' > /tmp/check_mods.py
import sys
sys.path.append('/ComfyUI')
mods = ['comfy.memory_management', 'comfy.model_management', 'comfy.model_prefetch', 'comfy.ops', 'comfy.patcher_extension', 'comfy.quant_ops', 'comfy.rmsnorm']
for mod in mods:
    try:
        __import__(mod)
        print('OK:', mod)
    except Exception as e:
        print('FAIL:', mod, e)
EOF
/root/miniconda3/envs/comfyui/bin/python /tmp/check_mods.py > /tmp/mod_res.txt 2>&1
""", wait_time=3)

    print("=== RESULT ===")
    print(run_cmd("cat /tmp/mod_res.txt", wait_time=2))

finally:
    client.close()
