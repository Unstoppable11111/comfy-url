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
    print("[1/3] 写入动态自适应 head 规则并重启 ComfyUI 服务...")
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

    patch_py = """cat << 'EOF' > /tmp/patch_heads.py
with open('/ComfyUI/comfy/model_detection.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = 'dit_config["num_layers"] = count_blocks(state_dict_keys, \'{}\' + \'transformer_blocks.\'.format(key_prefix) + \'{}.\')'
# 兼容不同写法
if 'dit_config["num_layers"]' in text:
    old_block = '''dit_config["in_channels"] = state_dict['{}img_in.weight'.format(key_prefix)].shape[1]
        dit_config["num_layers"] = count_blocks(state_dict_keys, '{}transformer_blocks.'.format(key_prefix) + '{}.')'''
    new_block = '''dit_config["in_channels"] = state_dict['{}img_in.weight'.format(key_prefix)].shape[1]
        dit_config["num_layers"] = count_blocks(state_dict_keys, '{}transformer_blocks.'.format(key_prefix) + '{}.')
        dit_config["num_attention_heads"] = state_dict['{}img_in.weight'.format(key_prefix)].shape[0] // 128'''
    text = text.replace(old_block, new_block)
    with open('/ComfyUI/comfy/model_detection.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("PATCH_HEADS_SUCCESS")
else:
    print("CANNOT_FIND_BLOCK")
EOF
/root/miniconda3/envs/comfyui/bin/python /tmp/patch_heads.py
"""
    p_res = run_cmd(patch_py, wait_time=2)
    print("补丁结果:", p_res)

    # 重启并等待就绪
    run_cmd("pkill -9 -f 'main.py' || true", wait_time=2)
    run_cmd("nohup /root/miniconda3/envs/comfyui/bin/python /ComfyUI/main.py --listen 0.0.0.0 --port 8081 > /ComfyUI/comfyui.log 2>&1 &", wait_time=2)
    for _ in range(25):
        time.sleep(1)
        res = run_cmd("curl -s http://127.0.0.1:8081/system_stats")
        if "system" in res:
            print("ComfyUI 已重启完毕，8081 就绪！")
            break

    print("[2/3] 正在启动 RTX 3090 GPU 全流程出图推理（约 35 秒）...")
    run_cmd("rm -f /tmp/final_render.b64 /tmp/final_part_*")
    out_run = run_cmd("/root/miniconda3/envs/comfyui/bin/python /tmp/run_final.py", wait_time=50)
    print(out_run)

    # 查看日志
    log_tail = run_cmd("tail -n 25 /ComfyUI/comfyui.log", wait_time=2)
    print("ComfyUI 执行日志:\n", log_tail)

    print("[3/3] 正在拉取高清渲染图并保存到本地工作区...")
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

finally:
    client.close()
