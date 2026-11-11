# setup —— 从零部署 Qwen-Image 2.1

## 这是什么

`deploy_qwen21.py`：在一台**全新的 GPU 云主机**上，一条命令装出能跑的 Qwen-Image 2.1 + ComfyUI。
用于「自定义镜像不能跨区」的情况（比如华北做的镜像不能在华南用）。

## 前置条件

- root 权限
- NVIDIA 显卡（≥ 20G 显存，推荐 4090/3090 24G）
- 系统盘 ≥ 30G 可用（模型 17G + 环境 ~10G）
- 能访问 ModelScope（下载模型）

## 三步走

**1. 把整个 setup 目录传到新机器**（算家云「项目网盘」上传后拉取，或任意方式）

```
setup/
├── deploy_qwen21.py
└── qwen21_workflows/      # 4 个官方工作流，脚本会优先用本地的
```

**2. 先体检**

```bash
python3 deploy_qwen21.py --check
```

会检查 root、GPU、显存、磁盘、ModelScope 连通性，不装任何东西。

**3. 正式部署**

```bash
python3 deploy_qwen21.py --start
```

`--start` 表示装完直接起服务并跑一张冒烟图。

## 时间表（按 10~20MB/s 估算）

| 阶段 | 内容 | 耗时 |
|---|---|---|
| 0-1 | 体检 + 补 curl/git/venv | 1~2 分钟 |
| 2-3 | 建 venv + 装 torch(cu128) | 5~10 分钟 |
| 4-5 | 拉 ComfyUI v0.44.2 + 装依赖 | 4~8 分钟 |
| 6 | 下 17G 模型（断点续传） | 15~30 分钟 |
| 7-8 | 装工作流 + 生成启动脚本 | 秒级 |
| **合计** | | **约 30~50 分钟** |

中途断了可以直接重跑，脚本会跳过已完成的部分（模型按字节数校验）。

## 下载速度说明

云主机的公网出口通常限在 **100 Mbps**（≈12.5 MB/s），16G 模型要 20 分钟上下 —— 这不是魔搭慢，是带宽上限。

脚本会优先用 **aria2c 16 线程分段下载**，如果平台是按单连接限速，速度能翻倍；如果按实例总带宽限，则没有提升。没有 aria2c 时自动退回 curl 单线程续传。

实测参考：单线程 12.5 MB/s ≈ 100M 带宽跑满；16G 在 12.5 MB/s 下约 21 分钟，25 MB/s 约 11 分钟，100 MB/s 约 3 分钟。

想要更快，只有三条路：开机器时选大带宽、挂平台公共模型库（0 下载）、或分多台机器并行下再合并。

## 装完怎么用

```bash
/root/start_comfy.sh      # 启动（默认 8081）
/root/stop_comfy.sh       # 停止
```

浏览器打开 `http://<公网IP>:8081` → 左侧工作流 → `image_qwen_image_2_1_t2i`。

> 模板里「提示词增强(PE)」节点需要额外 9G 模型，没装；右键 **Bypass (Ctrl+B)** 跳过即可。

## 常用参数

```bash
--dir /root          # 安装目录，默认 /root
--port 8081          # ComfyUI 端口
--skip-models        # 只装环境不下模型（省 17G / 半小时）
--check              # 只体检
--start              # 装完自动启动 + 冒烟测试
```

## 内置的容错

| 情况 | 处理 |
|---|---|
| GitHub clone 失败 | 自动改用 codeload 压缩包，再不行用 ghproxy |
| pip 清华源缺 `comfyui-workflow-templates` 子包 | 自动过滤该依赖重装，再用 `--no-deps` 单独补包本体 |
| 模型下载中断 | `curl -C -` 断点续传，按字节数校验，最多重试 3 次 |
| 系统里已有可用 torch | venv 带 `--system-site-packages`，跳过 torch 安装 |
| 裸 Ubuntu 缺 git/curl/venv | 自动 apt 安装 |

## 说明

同目录下其余脚本（`deploy_official_qwen21.py`、`step1_*.py`、`fix_and_test_q21_import.py` 等）是上次在华北那台机器上手工排障的过程记录，留档用；新机器部署只需要 `deploy_qwen21.py`。
