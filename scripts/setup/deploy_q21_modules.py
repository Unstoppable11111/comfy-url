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
    print("[1/4] 连接服务器...", flush=True)
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

    def upload_file(local_path, remote_path):
        with open(local_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        run_cmd("rm -f /tmp/up.b64", wait_time=0.3)
        chunk_size = 25000
        for i in range(0, len(b64), chunk_size):
            chunk = b64[i:i+chunk_size]
            run_cmd(f"echo -n '{chunk}' >> /tmp/up.b64", wait_time=0.3)
        dir_name = "/".join(remote_path.split("/")[:-1])
        run_cmd(f"mkdir -p {dir_name}", wait_time=0.3)
        run_cmd(f"base64 -d /tmp/up.b64 > {remote_path} && rm -f /tmp/up.b64", wait_time=0.5)

    print("[2/4] 上传 comfy/ldm/qwen_image21/model.py 与 text_encoders/qwen_image21.py...", flush=True)
    upload_file(r"e:\codex\video\scripts\latest_qwen21_model.py", "/ComfyUI/comfy/ldm/qwen_image21/model.py")
    run_cmd("touch /ComfyUI/comfy/ldm/qwen_image21/__init__.py", wait_time=0.3)
    upload_file(r"e:\codex\video\scripts\latest_te_qwen21.py", "/ComfyUI/comfy/text_encoders/qwen_image21.py")

    print("[3/4] 测试独立模块导入...", flush=True)
    test_code = """/root/miniconda3/envs/comfyui/bin/python -c "
import sys
sys.path.append('/ComfyUI')
import comfy.ldm.qwen_image21.model as m1
import comfy.text_encoders.qwen_image21 as m2
print('>>> SUCCESS_IMPORT_BOTH_QWEN21_MODULES <<<')
"
"""
    res = run_cmd(test_code, wait_time=3)
    print("导入测试结果:\n", res, flush=True)

finally:
    client.close()
