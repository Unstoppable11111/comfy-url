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
    shell = client.invoke_shell(term='xterm', width=200, height=50)

    def wait_for(target, timeout=10):
        start = time.time()
        buf = ""
        while time.time() - start < timeout:
            if shell.recv_ready():
                chunk = shell.recv(4096).decode('utf-8', errors='ignore')
                buf += chunk
                if target in buf:
                    return buf
            else:
                time.sleep(0.05)
        return buf

    wait_for("输入服务器序号>")
    shell.send("0\n")
    wait_for("root@")
    print("进入容器成功！")

    def run_cmd(cmd, wait_time=2):
        while shell.recv_ready():
            shell.recv(4096)
        shell.send(cmd + "\n")
        time.sleep(wait_time)
        buf = ""
        while shell.recv_ready():
            buf += shell.recv(4096).decode('utf-8', errors='ignore')
            time.sleep(0.05)
        clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', buf)
        return clean

    test_code = '''cat << 'EOF' > /tmp/test_q21.py
import sys
sys.path.append('/ComfyUI')
import comfy.ldm.qwen_image21.model
import comfy.text_encoders.qwen_image21
import comfy.supported_models
import comfy.model_base
print(">>> QWEN21_ALL_MODULES_100_PERCENT_SUCCESS <<<")
EOF
/root/miniconda3/envs/comfyui/bin/python /tmp/test_q21.py
'''
    print(run_cmd(test_code, wait_time=3))

finally:
    client.close()
