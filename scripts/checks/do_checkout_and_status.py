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
    time.sleep(1)
    if shell.recv_ready():
        shell.recv(4096)
    shell.send("0\r")
    time.sleep(1)
    if shell.recv_ready():
        shell.recv(4096)
    shell.send("\r")
    time.sleep(2)
    if shell.recv_ready():
        shell.recv(8192)

    def run_cmd(cmd, wait_time=3):
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

    print("=== GIT CHECKOUT ALL ===")
    print(run_cmd("cd /ComfyUI && git checkout . && git clean -fd", wait_time=2))

    print("=== GIT STATUS AFTER CLEAN ===")
    print(run_cmd("cd /ComfyUI && git status", wait_time=2))

    print("=== TEST BASELINE COMFYUI IMPORT ===")
    test_import = "/root/miniconda3/envs/comfyui/bin/python -c \"import sys; sys.path.append('/ComfyUI'); import main; print('BASELINE COMFYUI IMPORT SUCCESS')\""
    print(run_cmd(test_import, wait_time=4))

finally:
    client.close()
