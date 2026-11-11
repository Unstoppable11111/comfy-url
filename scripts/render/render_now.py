import paramiko
import time
import base64
import os
import re

hostname = "hb-a.suanjiayun.com"
port = 2020
username = "18379685528"
password = "980822cyc4435"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print("[1/2] 连接已就绪的 ComfyUI 服务...")
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
    
    def recv_timeout(timeout=4):
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

    print("检查 ComfyUI 端口 8081 响应...")
    st = run_cmd("curl -s http://127.0.0.1:8081/system_stats")
    print("状态:", "8081在线" if "system" in st else "离线")

    print("[2/2] 正在运行出图任务（RTX 3090 GPU 推理中，预计 30 秒）...")
    out_run = run_cmd("/root/miniconda3/envs/comfyui/bin/python /tmp/run_final.py", wait_time=40)
    print(out_run)

    log_tail = run_cmd("tail -n 25 /ComfyUI/comfyui.log", wait_time=2)
    print("ComfyUI 推理日志:\n", log_tail)

    # 检查输出文件
    run_cmd("rm -f /tmp/final_part_*")
    run_cmd("split -b 50000 /tmp/final_render.b64 /tmp/final_part_")
    parts_raw = run_cmd("ls /tmp/final_part_*")
    parts = [p.strip() for p in parts_raw.split() if 'final_part_' in p]
    print(f"Base64 分块数量: {len(parts)}")

    full_b64 = ""
    for p in sorted(parts):
        while shell.recv_ready():
            shell.recv(4096)
        shell.send(f"cat {p}\n")
        time.sleep(1)
        part_content = recv_timeout(3)
        lines = part_content.strip().splitlines()
        clean_lines = [l.strip() for l in lines if not l.startswith("(base)") and not l.startswith("cat /tmp")]
        full_b64 += "".join(clean_lines)

    if full_b64:
        img_bytes = base64.b64decode(full_b64)
        local_path = r"e:\codex\video\test_render.png"
        with open(local_path, "wb") as f:
            f.write(img_bytes)
        print(f"\n==========================================")
        print(f"🎉 验证完全成功！图片已成功保存到本地: {local_path}")
        print(f"图片文件大小: {len(img_bytes)/1024:.2f} KB")
        print(f"==========================================")
    else:
        print("未获取到 Base64 数据")

finally:
    client.close()
