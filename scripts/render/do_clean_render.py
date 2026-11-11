import paramiko
import time
import base64
import os
import re
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

hostname = "hb-a.suanjiayun.com"
port = 2020
username = "18379685528"
password = "980822cyc4435"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print("[阶段 1/4] 连接算家云并确认 32-head 补丁已落盘...", flush=True)
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
    recv_timeout(2)
    shell.send("0\n")
    time.sleep(1.5)
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

    patch_check = run_cmd("grep -n 'num_attention_heads' /ComfyUI/comfy/model_detection.py | tail -n 3", wait_time=1)
    print("磁盘补丁核验:\n", patch_check, flush=True)

    print("[阶段 2/4] 重启 ComfyUI 使新补丁载入内存，并等待 8081 端口就绪...", flush=True)
    run_cmd("pkill -9 -f 'main.py' || true", wait_time=2)
    run_cmd("nohup /root/miniconda3/envs/comfyui/bin/python /ComfyUI/main.py --listen 0.0.0.0 --port 8081 > /ComfyUI/comfyui.log 2>&1 &", wait_time=2)

    for i in range(30):
        res = run_cmd("curl -s http://127.0.0.1:8081/system_stats", wait_time=1)
        if "ram_total" in res:
            print(f"ComfyUI 已加载新补丁并成功启动 (第 {i+1} 次检测)！", flush=True)
            break
        time.sleep(1)

    print("[阶段 3/4] 正在提交红果短剧分镜测试 Prompt 并进行 GPU 25步去噪推理...", flush=True)
    run_cmd("rm -f /tmp/render_done.b64 /tmp/part_done_* /ComfyUI/output/Qwen_Test_Render*.png", wait_time=1)
    shell.send("/root/miniconda3/envs/comfyui/bin/python -u /tmp/do_render.py\n")

    start_wait = time.time()
    while time.time() - start_wait < 95:
        time.sleep(5)
        chunk = recv_timeout(1)
        if chunk.strip():
            clean_chunk = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', chunk).strip()
            print(f"[GPU 实时输出] {clean_chunk}", flush=True)
        if "B64_SAVED_BYTES" in chunk or "NO_IMAGE_FOUND" in chunk:
            break

    tail_log = run_cmd("tail -n 25 /ComfyUI/comfyui.log", wait_time=2)
    print("ComfyUI 引擎日志:\n", tail_log, flush=True)

    print("[阶段 4/4] 正在将生成的图片拉取回本地 E:\\codex\\video\\test_render.png ...", flush=True)
    run_cmd("split -b 50000 /tmp/render_done.b64 /tmp/part_done_", wait_time=1)
    parts_raw = run_cmd("ls /tmp/part_done_* 2>/dev/null", wait_time=1)
    parts = [p.strip() for p in parts_raw.split() if p.strip().startswith('/tmp/part_done_')]
    print(f"Base64 分块数量: {len(parts)}", flush=True)

    if len(parts) > 2:
        full_b64 = ""
        for p in sorted(parts):
            while shell.recv_ready():
                shell.recv(4096)
            shell.send(f"cat {p}\n")
            time.sleep(0.8)
            part_content = recv_timeout(2)
            lines = part_content.strip().splitlines()
            clean_lines = [l.strip() for l in lines if not l.startswith("(base)") and not l.startswith("cat /tmp") and not l.endswith("#")]
            full_b64 += "".join(clean_lines)

        full_b64 = re.sub(r'[^A-Za-z0-9+/=]', '', full_b64)
        missing_padding = len(full_b64) % 4
        if missing_padding:
            full_b64 += '=' * (4 - missing_padding)

        img_bytes = base64.b64decode(full_b64)
        local_path = r"e:\codex\video\test_render.png"
        with open(local_path, "wb") as f:
            f.write(img_bytes)
        print(f"SUCCESS_SAVED: {local_path} ({len(img_bytes)/1024:.2f} KB)", flush=True)
    else:
        print("ERROR_NO_VALID_PARTS", flush=True)

finally:
    client.close()
