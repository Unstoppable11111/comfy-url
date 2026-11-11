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
    print("[1/3] 上传已完成 aimdo 兼容降级的 model_prefetch.py 并验证...", flush=True)
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

    with open(r"e:\codex\video\scripts\model_prefetch.py", "rb") as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    run_cmd("rm -f /tmp/up.b64", wait_time=0.3)
    chunk_size = 25000
    for i in range(0, len(b64), chunk_size):
        chunk = b64[i:i+chunk_size]
        run_cmd(f"echo -n '{chunk}' >> /tmp/up.b64", wait_time=0.3)
    run_cmd("base64 -d /tmp/up.b64 > /ComfyUI/comfy/model_prefetch.py && rm -f /tmp/up.b64", wait_time=0.5)
    print("已上传 model_prefetch.py", flush=True)

    print("[2/3] 执行全链路导入检测...", flush=True)
    test_py = '''/root/miniconda3/envs/comfyui/bin/python -c '
import sys
sys.path.append("/ComfyUI")
import comfy.ldm.qwen_image21.model
import comfy.text_encoders.qwen_image21
import comfy.supported_models
import comfy.model_base
print(">>> QWEN21_IMPORT_100_PERCENT_SUCCESS <<<")
'
'''
    res = run_cmd(test_py, wait_time=3)
    print("导入测试输出:\n", res, flush=True)

    if "QWEN21_IMPORT_100_PERCENT_SUCCESS" in res:
        print("[3/3] 重启 ComfyUI 服务并提交正式出图...", flush=True)
        run_cmd("pkill -9 -f 'main.py' || true", wait_time=1)
        run_cmd("nohup /root/miniconda3/envs/comfyui/bin/python /ComfyUI/main.py --listen 0.0.0.0 --port 8081 > /ComfyUI/comfyui.log 2>&1 &", wait_time=2)
        for i in range(25):
            res_stats = run_cmd("curl -s http://127.0.0.1:8081/system_stats", wait_time=1)
            if "ram_total" in res_stats:
                print(f"ComfyUI 8081 正常就绪 (第 {i+1} 秒)！", flush=True)
                break
            time.sleep(1)

        print("正在提交出图任务...", flush=True)
        run_cmd("rm -f /tmp/render_done.b64 /tmp/part_done_* /ComfyUI/output/Qwen21_Final_Render*.png", wait_time=0.5)
        shell.send("/root/miniconda3/envs/comfyui/bin/python -u /tmp/do_render.py\n")

        start_wait = time.time()
        while time.time() - start_wait < 95:
            time.sleep(5)
            chunk = recv_timeout(1)
            if chunk.strip():
                clean_chunk = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', chunk).strip()
                print(f"[GPU 去噪进度] {clean_chunk}", flush=True)
            if "B64_SAVED_BYTES" in chunk or "NO_IMAGE_FOUND" in chunk:
                break

        print("正在将生成的图片拉取回本地工作区...", flush=True)
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
            print(f"🎉 成功！图片已落地: {local_path} ({len(img_bytes)/1024:.2f} KB)", flush=True)
        else:
            print("未生成图片分块，查看日志:\n", run_cmd("tail -n 25 /ComfyUI/comfyui.log", wait_time=2), flush=True)

finally:
    client.close()
