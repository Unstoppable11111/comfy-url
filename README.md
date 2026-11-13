# AI 短剧工业化生产工作区

本仓库用于**小说改编 AI 短剧**的全流程资产管理与关键帧批量生产。当前已完成**前 3 阶段**的工程验证（《乾隆》《凤鸣》均已产出前 10 集分镜资产、定妆照及第 1 集关键帧），**第 4 阶段（视频合成）**在规划与数据结构上已就绪，待接入执行脚本。

## 四阶段生产流程

```text
① 剧作与分镜拆解（本地 0 成本，.agents/skills 6 步流水线）
   小说 ──▶ outline.json ──▶ cast.json ──▶ art.json ──▶ script.json ──▶ staging.json ──▶ storyboard.json
                                                                                              │
② 云端部署与角色定妆（算家云 RTX 4090，ComfyUI v0.44.2 + Qwen-Image 2.1）                      ▼
   scripts/setup/deploy_qwen21.py ──▶ build_cast.py ──▶ characters/portraits/C01..C04.png ──▶ setup_cast.py
                                                                                              │
③ 关键帧批量生成与回传（现役核心入口：scripts/render/make_episode.py）                         ▼
   build_shots.py --ref（编辑指令）──▶ run_shots.py（TextEncodeQwenImage21）──▶ pull_frames.py ──▶ frames/
                                                                                              │
④ 音画同出视频合成（待开发脚本）                                                                ▼
   frames/ + storyboard.json (h3Prompt) ──▶ MiniMax H3 / Wan2.2 + Qwen3-TTS + FFmpeg ──▶ 成片
```

## 目录导航

| 目录 / 文件 | 用途说明 |
| :--- | :--- |
| [docs/关键帧生产流程.md](docs/关键帧生产流程.md) | **核心 SOP**：定妆 ➔ 参考图入库 ➔ 关键帧 ➔ 回传 ➔ 推送的完整操作手册 |
| [docs/Qwen落地流程.md](docs/Qwen落地流程.md) | Qwen3.5 / Qwen-Image 2.1 / Qwen3-TTS 选型与七步云端落地指南 |
| [docs/华南4090使用说明.md](docs/华南4090使用说明.md) | 华南 4090 云实例端口、模型路径与启停说明 |
| [docs/previews/](docs/previews/) | 关键帧、定妆照与参考图对比拼图预览 |
| [projects/](projects/) | 剧集资产目录（目前含 `novel_01_qianlong`、《乾隆》与 `novel_02_fengming`、《凤鸣》） |
| [scripts/remote/](scripts/remote/) | 算家云 SSH/容器连接与无 SFTP 传文件工具（凭据通过 `.env.local` 配置） |
| [scripts/setup/](scripts/setup/) | 裸机部署 `deploy_qwen21.py`、模型下载脚本与 4 个官方工作流 JSON |
| [scripts/render/](scripts/render/) | 现役批量出图流水线（`make_episode.py` 及任务构建/回传/推送脚本） |
| [.agents/skills/](.agents/skills/) | 剧作与分镜拆解技能包（链接至 `shuohao-skills`） |
| [archive/](archive/) | 历史归档（早期 v4.0 原型包 `v4_early_pack/` 与过时文档 `old_docs/`） |
| [GEMINI.md](GEMINI.md) | 项目避坑记录与开发运行规范 |

## 现役常用命令

```powershell
# 1. 验证云端实例连通性（需先在 scripts/remote/.env.local 配好 SJ_PWD）
cd scripts\remote
python selftest.py

# 2. 跑指定剧集的某一集关键帧（建任务 → 上传 → 生成 → 自动下载到 frames/）
cd ..\render
python make_episode.py ..\..\projects\novel_01_qianlong --ep 2 --tag qianlong

# 3. 推送新生成的剧集资产到 GitHub
.\publish.ps1 "乾隆 E02 关键帧"
```
