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
    print("[1/3] 上传 configurable.py 并再次验证 QwenImage21 导入...", flush=True)
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

    time.sleep(1)
    recv_timeout(2)
    shell.send("0\n")
    time.sleep(2)
    recv_timeout(2)
    shell.send("\n")
    time.sleep(1)
    recv_timeout(1)

    def run_cmd(cmd, wait_time=2):
        while shell.recv_ready():
            shell.recv(4096)
        shell.send(cmd + "\n")
        time.sleep(wait_time)
        res = recv_timeout(wait_time).strip()
        clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', res)
        return clean

    with open(r"e:\codex\video\scripts\configurable.py", "rb") as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    run_cmd(f"echo '{b64}' | base64 -d > /ComfyUI/comfy/configurable.py", wait_time=1)
    print("已同步 configurable.py", flush=True)

    print("[2/3] 重新验证 Python 导入...", flush=True)
    test_py = '''/root/miniconda3/envs/comfyui/bin/python -c '
import sys
sys.path.append("/ComfyUI")
import comfy.ldm.qwen_image21.model
import comfy.text_encoders.qwen_image21
import comfy.supported_models
import comfy.model_base
print("ALL_QWEN21_MODULES_IMPORTED_SUCCESS")
'
'''
    res = run_cmd(test_py, wait_time=3)
    print(res, flush=True)

    if "ALL_QWEN21_MODULES_IMPORTED_SUCCESS" in res:
        print("[3/3] 重启 ComfyUI 8081 并提交红果短剧出图任务...", flush=True)
        run_cmd("pkill -9 -f 'main.py' || true", wait_time=1)
        run_cmd("nohup /root/miniconda3/envs/comfyui/bin/python /ComfyUI/main.py --listen 0.0.0.0 --port 8081 > /ComfyUI/comfyui.log 2>&1 &", wait_time=2)
        for i in range(25):
            res_stats = run_cmd("curl -s http://127.0.0.1:8081/system_stats", wait_time=1)
            if "ram_total" in res_stats:
                print(f"ComfyUI 8081 就绪 (第 {i+1} 轮)！", flush=True)
                break
            time.sleep(1)

finally:
    client.close()
