#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Qwen-Image 2.1 (ComfyUI) 一键部署脚本

在一台全新的 GPU 云主机上跑完：装环境 → 拉 ComfyUI → 下模型 → 装工作流 → 起服务。
适配算家云 / AutoDL 等国内 GPU 实例，全程走国内镜像源。

用法（root 身份）：
    python3 deploy_qwen21.py                 # 全量部署
    python3 deploy_qwen21.py --check         # 只做环境检查
    python3 deploy_qwen21.py --skip-models   # 跳过 17G 模型下载
    python3 deploy_qwen21.py --start         # 部署完直接起服务

部署位置默认 /root，可用 --dir 改。日志同屏输出并写入 /root/qwen21_deploy.log
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------- 配置
COMFY_TAG = "v0.44.2"
MODEL_REPO = "Comfy-Org/Qwen-Image-2.1"
MS_BASE = "https://modelscope.cn/models/%s/resolve/master/" % MODEL_REPO

# (落盘子目录, 仓库内路径, 期望字节数)
MODELS = [
    ("diffusion_models", "diffusion_models/qwen_image_2.1_int8_convrot.safetensors", 7256783064),
    ("clip", "text_encoders/qwen3vl_8b_int8_convrot.safetensors", 9350798360),
    ("vae", "vae/qwen_image_2.1_vae_bf16.safetensors", 675509688),
]

PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
PIP_MIRROR_2 = "https://mirrors.aliyun.com/pypi/simple/"
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"

WORKFLOW_FILES = [
    "image_qwen_image_2_1_t2i.json",
    "image_qwen_image_2_1_image_edit.json",
    "image_qwen_image_2_1_turbo_t2i.json",
    "image_qwen_image_2_1_turbo_image_edit.json",
]

LOG_PATH = None


# ---------------------------------------------------------------- 基础工具
def log(msg=""):
    line = str(msg)
    print(line, flush=True)
    if LOG_PATH:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def run(cmd, check=True, capture=False, env=None):
    """执行命令，失败抛异常。cmd 可以是字符串或列表。"""
    if isinstance(cmd, str):
        shell_cmd = cmd
    else:
        shell_cmd = " ".join(cmd)
    log("  $ " + shell_cmd)
    kw = dict(shell=isinstance(cmd, str), text=True, env=env)
    if capture:
        kw["stdout"] = subprocess.PIPE
        kw["stderr"] = subprocess.STDOUT
    p = subprocess.run(cmd, **kw)
    if check and p.returncode != 0:
        raise RuntimeError("命令失败(%d): %s" % (p.returncode, shell_cmd))
    return p


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return "%.1f%s" % (n, unit)
        n /= 1024.0
    return "%.1fPB" % n


def free_gb(path):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize / (1024 ** 3)


def step(title):
    log()
    log("=" * 62)
    log("  " + title)
    log("=" * 62)


# ---------------------------------------------------------------- 各阶段
def preflight(args):
    step("0/8 环境检查")
    if os.geteuid() != 0:
        raise RuntimeError("请用 root 运行（当前不是 root）")
    if sys.version_info < (3, 8):
        raise RuntimeError("需要 Python 3.8+，当前 %s" % sys.version.split()[0])
    log("  python  : " + sys.version.split()[0])

    if not shutil.which("nvidia-smi"):
        raise RuntimeError("找不到 nvidia-smi，这台机器没有 GPU 驱动？")
    p = run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", capture=True, check=False)
    gpu = (p.stdout or "").strip().splitlines()
    if p.returncode != 0 or not gpu:
        raise RuntimeError("nvidia-smi 执行失败，GPU 不可用")
    log("  gpu     : " + gpu[0].strip())

    vram_mb = 0
    try:
        vram_mb = int(gpu[0].split(",")[1].strip().split()[0])
    except Exception:
        pass
    if vram_mb and vram_mb < 20000:
        log("  !! 显存只有 %d MB，Qwen-Image 2.1 int8 需要 24G 级显卡" % vram_mb)

    free = free_gb("/")
    log("  磁盘剩余: %.1f GB（%s）" % (free, args.dir))
    need = 3 if args.skip_models else 30
    if free < need:
        raise RuntimeError("磁盘不足：需要至少 %dG，当前只有 %.1fG。换大一点的系统盘，或先 --skip-models" % (need, free))

    env = os.environ.copy()
    p = run("curl -s -o /dev/null -w '%{http_code}' --max-time 20 " + MS_BASE + "vae/qwen_image_2.1_vae_bf16.safetensors",
            capture=True, check=False, env=env)
    code = (p.stdout or "").strip()
    log("  modelscope 连通: %s" % (code or "失败"))
    if code not in ("200", "302", "206"):
        log("  !! 访问 ModelScope 异常，模型下载可能失败")


def ensure_tools():
    """极简镜像可能没有 git / curl / tar / venv，先补齐。"""
    step("1/8 补齐系统工具")
    missing = [b for b in ("curl", "git", "tar") if not shutil.which(b)]
    if missing:
        log("  缺少 %s，apt 安装" % ", ".join(missing))
        run("apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq curl git tar ca-certificates aria2", check=False)
    p = subprocess.run([sys.executable, "-m", "venv", "--help"], capture_output=True)
    if p.returncode != 0:
        log("  python3-venv 不可用，apt 安装")
        run("DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv", check=False)
    for b in ("curl", "git", "tar"):
        if not shutil.which(b):
            raise RuntimeError("仍然找不到 %s，请先手动安装" % b)


def ensure_venv(args):
    step("2/8 准备 Python 环境")
    venv_dir = args.dir / "qwen21-venv"
    py = venv_dir / "bin" / "python"

    system_torch = subprocess.run([sys.executable, "-c", "import torch;assert torch.cuda.is_available()"],
                                  capture_output=True).returncode == 0
    if system_torch:
        log("  系统里已有可用 CUDA 版 torch，venv 直接复用（--system-site-packages）")

    if not py.exists():
        cmd = [sys.executable, "-m", "venv"]
        if system_torch:
            cmd.append("--system-site-packages")
        cmd.append(str(venv_dir))
        run(cmd)
    else:
        log("  venv 已存在，跳过创建")

    p = run([str(py), "-m", "pip", "--version"], capture=True, check=False)
    if p.returncode != 0:
        run([str(py), "-m", "ensurepip", "--upgrade"])
    run([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip", "-i", PIP_MIRROR], check=False)
    return py, system_torch


def install_torch(py, system_torch):
    step("3/8 安装 PyTorch")
    if system_torch:
        p = run([str(py), "-c", "import torch;print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"],
                capture=True, check=False)
        log("  沿用系统 torch: " + (p.stdout or "").strip())
        return
    p = run([str(py), "-c", "import torch;print(torch.__version__)"], capture=True, check=False)
    if p.returncode == 0:
        log("  已安装 torch " + (p.stdout or "").strip() + "，检查 CUDA 可用性")
        p = run([str(py), "-c", "import torch;print(torch.cuda.is_available())"], capture=True, check=False)
        if "True" in (p.stdout or ""):
            log("  torch 可用，跳过")
            return
        log("  torch 无 CUDA，重装 CUDA 版")

    ok = False
    for idx in (PIP_MIRROR, PIP_MIRROR_2):
        p = run([str(py), "-m", "pip", "install", "torch", "torchvision", "-i", idx], check=False)
        if p.returncode == 0:
            ok = True
            break
        log("  源 %s 安装失败，换源重试" % idx)
    if not ok:
        log("  国内源都失败，改用 PyTorch 官方 cu128 源（较慢）")
        run([str(py), "-m", "pip", "install", "torch", "torchvision", "--index-url", TORCH_INDEX])

    p = run([str(py), "-c", "import torch;print(torch.__version__, torch.cuda.is_available())"],
            capture=True, check=False)
    log("  torch: " + (p.stdout or "").strip())
    if "True" not in (p.stdout or ""):
        raise RuntimeError("torch 装好了但 CUDA 不可用，检查驱动版本（需要支持 cu128 的驱动）")


def clone_comfy(args):
    step("4/8 拉取 ComfyUI %s" % COMFY_TAG)
    comfy = args.dir / "ComfyUI"
    if (comfy / "main.py").exists():
        log("  %s 已存在，跳过克隆" % comfy)
        return comfy

    p = run("git clone --depth 1 --branch %s https://github.com/Comfy-Org/ComfyUI.git %s"
            % (COMFY_TAG, comfy), check=False)
    if p.returncode != 0:
        log("  git clone 失败，改用压缩包下载")
        tar_path = args.dir / "comfyui.tar.gz"
        urls = [
            "https://codeload.github.com/Comfy-Org/ComfyUI/tar.gz/refs/tags/" + COMFY_TAG,
            "https://ghproxy.net/https://github.com/Comfy-Org/ComfyUI/archive/refs/tags/%s.tar.gz" % COMFY_TAG,
        ]
        ok = False
        for u in urls:
            run("curl -fL --retry 3 --connect-timeout 20 -o '%s' '%s'" % (tar_path, u), check=False)
            if tar_path.exists() and tar_path.stat().st_size > 1_000_000:
                comfy.mkdir(parents=True, exist_ok=True)
                run("tar -xzf '%s' -C '%s' --strip-components=1" % (tar_path, comfy))
                ok = True
                break
        if not ok:
            raise RuntimeError("ComfyUI 下载失败（GitHub 和镜像都不通）")
    run("cd %s && (git describe --tags 2>/dev/null || echo '压缩包安装')" % comfy, check=False)
    return comfy


def install_requirements(py, comfy):
    step("5/8 安装 ComfyUI 依赖")
    req = comfy / "requirements.txt"
    p = run([str(py), "-m", "pip", "install", "-r", str(req), "-i", PIP_MIRROR], check=False)
    if p.returncode == 0:
        return
    log("  完整依赖安装失败（多半是 comfyui-workflow-templates 的子包源里没有）")
    log("  退回：跳过模板包，其余照装")
    filtered = args_globals["dir"] / "requirements_no_tpl.txt"
    keep = [ln for ln in req.read_text(encoding="utf-8").splitlines()
            if not ln.strip().startswith("comfyui-workflow-templates")]
    filtered.write_text("\n".join(keep) + "\n", encoding="utf-8")
    run([str(py), "-m", "pip", "install", "-r", str(filtered), "-i", PIP_MIRROR])
    log("  模板包缺失只影响「浏览模板」页面，不影响出图（工作流已单独放好）")
    p = run([str(py), "-m", "pip", "install", "--no-deps", "comfyui-workflow-templates", "-i", PIP_MIRROR], check=False)
    if p.returncode == 0:
        log("  已装上模板包本体（不带图片资源），启动告警可忽略")
    else:
        log("  模板包本体也装不上，启动时可能有一条告警，不影响出图")


def fetch_file(url, dest):
    """优先 aria2c 多线程分段，其次 curl 单线程续传。"""
    if shutil.which("aria2c"):
        log("    用 aria2c 16 线程下载")
        run("aria2c -x16 -s16 -k1M -c --auto-file-renaming=false --allow-overwrite=true "
            "--console-log-level=warn --summary-interval=10 -d '%s' -o '%s' '%s'"
            % (dest.parent, dest.name, url), check=False)
        if dest.exists() and dest.stat().st_size > 0:
            return
        log("    aria2c 失败，退回 curl")
    run("curl -L -C - --retry 3 --retry-delay 5 --connect-timeout 20 -o '%s' '%s'" % (dest, url), check=False)


def download_models(args, comfy):
    step("6/8 下载模型（约 17G，可断点续传）")
    if args.skip_models:
        log("  --skip-models，跳过")
        return

    for sub, repo_path, expect in MODELS:
        dest_dir = comfy / "models" / sub
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / Path(repo_path).name

        if dest.exists() and dest.stat().st_size == expect:
            log("  [跳过] %s 已完整（%s）" % (dest.name, human(expect)))
            continue
        if dest.exists():
            log("  [续传] %s 当前 %s / %s" % (dest.name, human(dest.stat().st_size), human(expect)))

        url = MS_BASE + repo_path
        log("  [下载] %s  (%s)" % (dest.name, human(expect)))
        started = time.time()
        for attempt in (1, 2, 3):
            fetch_file(url, dest)
            if dest.exists() and dest.stat().st_size == expect:
                break
            log("  第 %d 次校验失败，重试" % attempt)
            time.sleep(3)
        if not dest.exists() or dest.stat().st_size != expect:
            got = dest.stat().st_size if dest.exists() else 0
            raise RuntimeError("%s 大小不对：%s / %s" % (dest.name, human(got), human(expect)))
        speed = expect / 1048576.0 / max(time.time() - started, 0.1)
        log("  [完成] %s  平均 %.1f MB/s" % (dest.name, speed))

    # 兼容 models/text_encoders 目录名
    te = comfy / "models" / "text_encoders"
    te.mkdir(parents=True, exist_ok=True)
    link = te / "qwen3vl_8b_int8_convrot.safetensors"
    target = comfy / "models" / "clip" / "qwen3vl_8b_int8_convrot.safetensors"
    if not link.exists() and target.exists():
        os.symlink("../clip/" + target.name, link)
        log("  已建立 text_encoders 兼容软链")


def install_workflows(args, comfy):
    step("7/8 安装工作流")
    dest_dir = comfy / "user" / "default" / "workflows"
    dest_dir.mkdir(parents=True, exist_ok=True)
    local_dir = Path(__file__).resolve().parent / "qwen21_workflows"

    for name in WORKFLOW_FILES:
        dest = dest_dir / name
        if dest.exists():
            log("  [跳过] %s" % name)
            continue
        src = local_dir / name
        if src.exists():
            shutil.copy2(src, dest)
            log("  [本地] %s" % name)
            continue
        url = "https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/" + name
        p = run("curl -fsSL --max-time 60 -o '%s' '%s'" % (dest, url), check=False)
        if p.returncode == 0 and dest.stat().st_size > 1000:
            log("  [下载] %s" % name)
        else:
            dest.unlink(missing_ok=True)
            log("  [失败] %s —— 稍后可手动拖进 ComfyUI 界面" % name)


def write_launcher(args):
    step("8/8 生成启动脚本与说明")
    start = args.dir / "start_comfy.sh"
    stop = args.dir / "stop_comfy.sh"
    py = args.dir / "qwen21-venv" / "bin" / "python"
    comfy = args.dir / "ComfyUI"

    start.write_text(
        "#!/bin/bash\n"
        "# 启动 ComfyUI（Qwen-Image 2.1）\n"
        "pkill -f 'ComfyUI/main.py' 2>/dev/null; sleep 1\n"
        "cd %s\n"
        "nohup %s main.py --listen 0.0.0.0 --port %d --enable-cors-header '*' \\\n"
        "  > %s/comfyui.log 2>&1 &\n"
        "echo \"启动中，日志: %s/comfyui.log\"\n"
        "for i in $(seq 1 60); do\n"
        "  if curl -s -o /dev/null http://127.0.0.1:%d/; then echo \"服务已就绪: http://<IP>:%d\"; exit 0; fi\n"
        "  sleep 2\n"
        "done\n"
        "echo \"等待超时，看日志: tail -50 %s/comfyui.log\"\n"
        % (comfy, py, args.port, comfy, comfy, args.port, args.port, comfy),
        encoding="utf-8")
    start.chmod(0o755)

    stop.write_text("#!/bin/bash\npkill -f 'ComfyUI/main.py'\necho stopped\n", encoding="utf-8")
    stop.chmod(0o755)

    readme = args.dir / "使用说明.md"
    readme.write_text(
        "# Qwen-Image 2.1 环境\n\n"
        "## 启动 / 停止\n```bash\n%s/start_comfy.sh   # 启动（端口 %d）\n%s/stop_comfy.sh    # 停止\n```\n\n"
        "## 模型\n- `%s/models/diffusion_models/qwen_image_2.1_int8_convrot.safetensors`\n"
        "- `%s/models/clip/qwen3vl_8b_int8_convrot.safetensors`\n"
        "- `%s/models/vae/qwen_image_2.1_vae_bf16.safetensors`\n\n"
        "## 工作流\n`%s/user/default/workflows/` 下 4 个官方工作流，界面左侧可见。\n\n"
        "## 参数\n采样 euler / simple，25 步，cfg 1.0，1024×1024（3090 约 2.5 分钟/张，4090 更快）。\n\n"
        "## 提示词增强(PE)节点\n官方模板带一个 9G 的 `qwen3.5_9b_..._pe_t2i` 编码器，没装。\n"
        "打开模板后该节点标红，**右键 → Bypass（Ctrl+B）** 跳过即可，不影响出图。\n"
        % (args.dir, args.port, args.dir, comfy, comfy, comfy, comfy),
        encoding="utf-8")
    log("  %s" % start)
    log("  %s" % stop)
    log("  %s" % readme)


def smoke_test(args, py):
    step("冒烟测试：提交一张 1024×1024 / 25 步")
    script = args.dir / "_smoke.py"
    script.write_text(
        "import json,time,urllib.request\n"
        "B='http://127.0.0.1:%d'\n"
        "g={'1':{'class_type':'UNETLoader','inputs':{'unet_name':'qwen_image_2.1_int8_convrot.safetensors','weight_dtype':'default'}},\n"
        "   '2':{'class_type':'QwenImage21Cache','inputs':{'model':['1',0],'device':'auto','dtype':'default'}},\n"
        "   '3':{'class_type':'CLIPLoader','inputs':{'clip_name':'qwen3vl_8b_int8_convrot.safetensors','type':'qwen_image','device':'default'}},\n"
        "   '4':{'class_type':'TextEncodeQwenImage21','inputs':{'clip':['3',0],'prompt':'a red apple on a wooden table, soft window light','negative_prompt':'','resolution':1024}},\n"
        "   '5':{'class_type':'EmptyLatentImage','inputs':{'width':1024,'height':1024,'batch_size':1}},\n"
        "   '6':{'class_type':'KSampler','inputs':{'model':['2',0],'seed':1,'steps':25,'cfg':1.0,'sampler_name':'euler','scheduler':'simple','positive':['4',0],'negative':['4',1],'latent_image':['5',0],'denoise':1.0}},\n"
        "   '7':{'class_type':'VAEDecode','inputs':{'samples':['6',0],'vae':['8',0]}},\n"
        "   '8':{'class_type':'VAELoader','inputs':{'vae_name':'qwen_image_2.1_vae_bf16.safetensors'}},\n"
        "   '9':{'class_type':'SaveImage','inputs':{'images':['7',0],'filename_prefix':'qwen21_smoke'}}}\n"
        "req=urllib.request.Request(B+'/prompt',data=json.dumps({'prompt':g}).encode(),headers={'Content-Type':'application/json'})\n"
        "pid=json.loads(urllib.request.urlopen(req,timeout=60).read())['prompt_id']\n"
        "print('submitted',pid,flush=True)\n"
        "for _ in range(120):\n"
        "    time.sleep(5)\n"
        "    h=json.loads(urllib.request.urlopen(B+'/history/'+pid,timeout=30).read())\n"
        "    if pid in h:\n"
        "        print('status',h[pid]['status']['status_str'],flush=True)\n"
        "        print(json.dumps(h[pid].get('outputs',{}))[:400],flush=True)\n"
        "        raise SystemExit(0)\n"
        "print('timeout',flush=True)\n" % args.port,
        encoding="utf-8")
    run([str(py), str(script)], check=False)


# ---------------------------------------------------------------- 主流程
args_globals = {}


def main():
    global LOG_PATH
    ap = argparse.ArgumentParser(description="Qwen-Image 2.1 + ComfyUI 一键部署")
    ap.add_argument("--dir", default="/root", help="安装根目录（默认 /root）")
    ap.add_argument("--port", type=int, default=8081, help="ComfyUI 端口（默认 8081）")
    ap.add_argument("--skip-models", action="store_true", help="跳过 17G 模型下载")
    ap.add_argument("--start", action="store_true", help="部署完自动启动并做冒烟测试")
    ap.add_argument("--check", action="store_true", help="只做环境检查")
    args = ap.parse_args()
    args.dir = Path(args.dir).expanduser().resolve()
    args.dir.mkdir(parents=True, exist_ok=True)
    args_globals["dir"] = args.dir

    LOG_PATH = str(args.dir / "qwen21_deploy.log")
    open(LOG_PATH, "w", encoding="utf-8").close()

    t0 = time.time()
    log("Qwen-Image 2.1 部署开始  %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    log("目标目录: %s   端口: %d" % (args.dir, args.port))

    preflight(args)
    if args.check:
        log("\n检查通过，去掉 --check 即可开始部署")
        return

    ensure_tools()
    py, system_torch = ensure_venv(args)
    install_torch(py, system_torch)
    comfy = clone_comfy(args)
    install_requirements(py, comfy)
    download_models(args, comfy)
    install_workflows(args, comfy)
    write_launcher(args)

    log()
    log("耗时 %.1f 分钟" % ((time.time() - t0) / 60))
    log("完成！下一步：")
    log("  %s/start_comfy.sh" % args.dir)
    log("  然后浏览器打开 http://<公网IP>:%d" % args.port)

    if args.start:
        run("%s/start_comfy.sh" % args.dir, check=False)
        time.sleep(20)
        smoke_test(args, py)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print("\n[失败] %s" % e, file=sys.stderr)
        print("日志: %s" % LOG_PATH, file=sys.stderr)
        sys.exit(1)
