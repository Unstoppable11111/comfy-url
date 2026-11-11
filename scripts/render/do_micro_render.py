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
    print("[1/3] 连接容器并应用 Qwen 2.1 微创层适配补丁...", flush=True)
    client.connect(hostname, port=port, username=username, password=password, timeout=10, allow_agent=False, look_for_keys=False)
    shell = client.invoke_shell(term='vt100', width=200, height=50)
    time.sleep(1); shell.recv(4096); shell.send("0\r"); time.sleep(1); shell.recv(4096); shell.send("\r"); time.sleep(2); shell.recv(8192)

    def run_cmd(cmd, wait_time=2):
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

    patch_py = '''cat << 'EOF' > /tmp/apply_micro_patch.py
with open('/ComfyUI/comfy/ldm/qwen_image/model.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. 注入 Qwen21TextProjection 类
if 'class Qwen21TextProjection' not in text:
    target_class = 'class QwenImageTransformer2DModel'
    inject_class = """
class Qwen21TextProjection(nn.Module):
    def __init__(self, dim, operations, dtype, device):
        super().__init__()
        self.text_norm = operations.RMSNorm(dim, eps=1e-6, dtype=dtype, device=device)
        self.in_layer = operations.Linear(dim, dim, bias=False, dtype=dtype, device=device)
        self.out_layer = operations.Linear(dim, dim, bias=False, dtype=dtype, device=device)
    def forward(self, x):
        return self.out_layer(F.gelu(self.in_layer(self.text_norm(x)), approximate="tanh"))

"""
    text = text.replace(target_class, inject_class + target_class)

# 2. 在 __init__ 中支持 txt_in 复合结构
init_target = "self.txt_in = operations.Linear(joint_attention_dim, self.inner_dim, dtype=dtype, device=device)"
init_replace = """self.txt_in = operations.Linear(joint_attention_dim, self.inner_dim, dtype=dtype, device=device)
        self.txt_in_q21 = Qwen21TextProjection(self.inner_dim, operations, dtype, device)"""
if 'txt_in_q21' not in text:
    text = text.replace(init_target, init_replace)

# 3. 在 _forward 中兼容调用
fwd_target = """        hidden_states = self.img_in(hidden_states)
        encoder_hidden_states = self.txt_norm(encoder_hidden_states)
        encoder_hidden_states = self.txt_in(encoder_hidden_states)"""

fwd_replace = """        hidden_states = self.img_in(hidden_states)
        if hasattr(self.txt_in, 'in_layer'):
            encoder_hidden_states = self.txt_in(encoder_hidden_states)
        else:
            try:
                encoder_hidden_states = self.txt_norm(encoder_hidden_states)
                encoder_hidden_states = self.txt_in(encoder_hidden_states)
            except Exception:
                encoder_hidden_states = self.txt_in_q21(encoder_hidden_states)"""

if 'txt_in_q21(encoder_hidden_states)' not in text:
    text = text.replace(fwd_target, fwd_replace)

with open('/ComfyUI/comfy/ldm/qwen_image/model.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("MICRO_PATCH_APPLIED_SUCCESS")
EOF
/root/miniconda3/envs/comfyui/bin/python /tmp/apply_micro_patch.py
'''
    res = run_cmd(patch_py, wait_time=2)
    print("补丁结果:\n", res, flush=True)

    print("[2/3] 重启 ComfyUI 并等待 8081 就绪...", flush=True)
    run_cmd("pkill -9 -f 'main.py' || true")
    run_cmd("nohup /root/miniconda3/envs/comfyui/bin/python /ComfyUI/main.py --listen 0.0.0.0 --port 8081 > /ComfyUI/comfyui.log 2>&1 &")

    is_ready = False
    for i in range(25):
        time.sleep(1)
        res_stats = run_cmd("curl -s http://127.0.0.1:8081/system_stats")
        if "ram_total" in res_stats:
            print(f"ComfyUI 服务在第 {i+1} 秒启动完毕，8081 正常响应！", flush=True)
            is_ready = True
            break

    if is_ready:
        print("[3/3] 正在提交红果短剧出图工作流并进行 GPU 渲染...", flush=True)
        run_cmd("rm -f /tmp/render_done.b64 /tmp/part_done_* /ComfyUI/output/Qwen_Test_Render*.png")
        shell.send("/root/miniconda3/envs/comfyui/bin/python -u /tmp/do_render.py\r")

        start_wait = time.time()
        while time.time() - start_wait < 95:
            time.sleep(5)
            chunk = run_cmd("echo PING", wait_time=0.5)
            # 轮询日志
            log_tail = run_cmd("tail -n 8 /ComfyUI/comfyui.log")
            if "Prompt executed in" in log_tail or "Exception during processing" in log_tail:
                print("ComfyUI 执行状态:\n", log_tail, flush=True)
                break

        # 检查图片并拉取
        run_cmd("split -b 50000 /tmp/render_done.b64 /tmp/part_done_")
        parts_raw = run_cmd("ls /tmp/part_done_* 2>/dev/null")
        parts = [p.strip() for p in parts_raw.split() if p.strip().startswith('/tmp/part_done_')]
        print(f"Base64 分块数量: {len(parts)}", flush=True)

        if len(parts) > 2:
            full_b64 = ""
            for p in sorted(parts):
                shell.send(f"cat {p}\r")
                time.sleep(0.6)
                part_content = run_cmd("", wait_time=0.6)
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
            print(f"\n==========================================")
            print(f"🎉 验证完全成功！图片已成功保存到本地: {local_path}")
            print(f"图片文件大小: {len(img_bytes)/1024:.2f} KB")
            print(f"==========================================")
        else:
            print("未获取到图片分块，查看日志:\n", run_cmd("tail -n 25 /ComfyUI/comfyui.log"))

finally:
    client.close()
