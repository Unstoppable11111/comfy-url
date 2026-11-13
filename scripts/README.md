# scripts 目录

算家云实例 + ComfyUI 相关的全部脚本，按用途分层。

```
scripts/
├── remote/       SSH 连接工具（登录 → 选实例 → 进容器 → 跑命令 / 传文件）
├── setup/        部署脚本与工作流（一键装 ComfyUI v0.44.2 + Qwen-Image 2.1）
└── render/       出图与验证：建任务、提交工作流、轮询结果、HTTP 回传、拼图预览
    └── tasks/    运行产生的中间任务 JSON（已在 .gitignore 忽略）
```

## 相关文档

- [关键帧生产流程](../docs/关键帧生产流程.md) —— 定妆照 → 参考图 → 关键帧的完整 SOP、提示词模板、换机清单
- [Qwen 落地流程](../docs/Qwen落地流程.md) —— 模型选型与七步落地

## 常用入口

### 0. 换区 / 新机器从零部署

自定义镜像不能跨区（华北做的镜像华南用不了），在新区开一台空机器后：

```bash
# 把 scripts/setup 整个目录传上去，然后
python3 deploy_qwen21.py --check    # 先体检
python3 deploy_qwen21.py --start    # 全量部署 + 起服务，约 30~50 分钟
```

详见 `setup/README.md`。装完得到 `/root/start_comfy.sh`（8081 端口）。

### 1. 连上机器

```powershell
cd scripts\remote
set SJ_PWD=你的密码          # 或者用 .env.local
python selftest.py
```

登录后是「算家计算OS」的选实例菜单，工具会自动输 `0` 进容器，不用手动点。

### 2. 远程执行命令

```powershell
cd scripts\remote
python -c "from term import Term; t=Term(); print(t.cmd('nvidia-smi')); t.close()"
```

### 3. 传脚本上去并执行

```powershell
cd scripts\remote
python push.py ..\render\smoke.py /tmp/smoke.py "python3 /tmp/smoke.py"
```

> 实例禁用了 SFTP，所以 `push.py` 是把文件 base64 分块写进远端，已验证可用。

### 4. 验证出图链路

```powershell
cd scripts\render
python smoke.py
```

提交一次 1024×1024 / 25 步的 Qwen-Image 2.1 生成，轮询到结束并打印输出文件名。

### 5. 跑一集短剧（自动下载到本地）

```powershell
cd scripts\render
python make_episode.py ..\..\projects\novel_01_qianlong --ep 1 --tag qianlong
```

一条命令走完：建任务（双 Skill 融合编译）→ 自动 HTTP 上传本地定妆照 → 推送执行脚本 → 带角色参考图生成 → **自动下载 PNG 到 `projects/<项目>/storyboard/frames/` 并生成联系表预览图至 `docs/previews/`**。

- 默认走图生图（带定妆照参考），`--no-ref` 切纯文生图（下载到 `frames_textonly/`）
- 前提：该项目的 `characters/portraits/` 里已有定妆照（无需提前手工传服务器，脚本会自动同步上传）
- 单集约 13 个镜头，5~6 分钟

单独补下载已有批次：

```powershell
python pull_frames.py --base http://xn-b.suanjiayun.com:61146 `
  --tag ref_qianlong --ids tasks\shots_novel_01_qianlong_ep1_ref.json `
  --dest ..\..\projects\novel_01_qianlong\storyboard\frames
```

## 凭据说明

密码**不写在代码里**：`scripts/remote/sjconfig.py` 先读环境变量 `SJ_PWD`，读不到再读同目录的 `.env.local`（已在 `.gitignore` 里忽略）。换机器/换密码只改这一处。

## 说明

早期的排障探针与临时调试脚本已清理（历史留档见 Git 提交记录）；当前目录下保留的均为长期生产与运维工具。
