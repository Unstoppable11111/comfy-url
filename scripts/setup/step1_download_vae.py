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
    print("[1/3] 正在建立 SSH 远程连接到算家云实例...")
    client.connect(
        hostname, 
        port=port, 
        username=username, 
        password=password, 
        timeout=15,
        allow_agent=False,
        look_for_keys=False
    )
    shell = client.invoke_shell(term='xterm', width=160, height=50)
    
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

    print("[2/3] 检查云端 ComfyUI 服务状态与磁盘空间...")
    res_ps = run_cmd("ps aux | grep comfyui | grep -v grep")
    print("ComfyUI 运行进程:", "正常运行" if "main.py" in res_ps else "需要启动")
    df_res = run_cmd("df -h /")
    print("系统盘剩余空间:\n", df_res)

    print("[3/3] 准备从 ModelScope 极速下载原生蓝图通用 VAE (250MB)...")
    dl_script = """cat << 'EOF' > /tmp/dl_vae.py
import os
import shutil
from modelscope.hub.file_download import model_file_download

print("开始从 ModelScope 下载 qwen_image_vae.safetensors ...")
target_dir = "/ComfyUI/models/vae"
target_file = os.path.join(target_dir, "qwen_image_vae.safetensors")

if os.path.exists(target_file) and not os.path.islink(target_file) and os.path.getsize(target_file) > 200 * 1024 * 1024:
    print(f"VAE 实体文件已存在，大小: {os.path.getsize(target_file)/1024/1024:.2f} MB")
else:
    if os.path.islink(target_file):
        os.remove(target_file)
    fpath = model_file_download(
        model_id="Comfy-Org/Qwen-Image",
        file_path="split_files/vae/qwen_image_vae.safetensors"
    )
    print("下载完成，移动至目标目录:", fpath)
    shutil.move(fpath, target_file)
    # 清理缓存
    os.system("rm -rf /root/.cache/modelscope")
    print("VAE 就绪，文件大小:", os.path.getsize(target_file) / 1024 / 1024, "MB")
EOF
/root/miniconda3/envs/comfyui/bin/python /tmp/dl_vae.py
"""
    dl_output = run_cmd(dl_script, wait_time=15)
    print(dl_output)

finally:
    client.close()
