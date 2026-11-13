# Qwen-Image 2.1 可用环境说明（2026-11-10 制作）

## 这个镜像里有什么

- **ComfyUI v0.44.2**（`/ComfyUI`，从 v0.33.1 升级而来，原生支持 Qwen-Image 2.1）
- Python 环境：conda `comfyui`，Python 3.12，torch 2.9.0+cu128
- 服务端口：**8081**（ComfyUI），启动脚本 `/sj-run.sh`
- 显卡：RTX 3090 24G（本机）

## 模型文件（都在系统盘 /ComfyUI/models 下，已校验完整）

| 用途 | 路径 | 大小 |
|---|---|---|
| 扩散模型 | `models/diffusion_models/qwen_image_2.1_int8_convrot.safetensors` | 6.8G |
| 文本编码器 | `models/clip/qwen3vl_8b_int8_convrot.safetensors` | 8.8G |
| VAE | `models/vae/qwen_image_2.1_vae_bf16.safetensors` | 645M |

## 工作流

`/ComfyUI/user/default/workflows/` 下已放好 4 个官方工作流，打开 ComfyUI 后左侧工作流列表可见：

- `image_qwen_image_2_1_t2i.json` —— 文生图
- `image_qwen_image_2_1_image_edit.json` —— 图像编辑
- `image_qwen_image_2_1_turbo_t2i.json` —— Turbo 文生图（少步数）
- `image_qwen_image_2_1_turbo_image_edit.json` —— Turbo 图像编辑

## 怎么启动

```bash
/sj-run.sh -s     # 启动（ComfyUI + minimaxh3-web）
/sj-run.sh -t     # 停止
/sj-run.sh -r     # 重启
```

手动启动（前端 8081）：

```bash
cd /ComfyUI
/root/miniconda3/bin/conda run --no-capture-output -n comfyui \
  python main.py --listen 0.0.0.0 --port 8081 --enable-cors-header '*'
```

## 参考参数（官方模板，实测可用）

- 采样：euler / simple，steps 25，cfg 1.0
- 分辨率 1024×1024（3090 上约 1.5 秒/步，25 步连加载约 2.5 分钟）
- `QwenImage21Cache` 节点用 auto/default

## 已知注意事项

1. **提示词增强（PE）节点缺模型**：官方模板里有个 `qwen3.5_9b_qwen_image_2.1_pe_t2i` 文本编码器（约 9G）没有下载。
   打开模板后该节点会标红，**右键 → Bypass（Ctrl+B）** 跳过即可；开关默认就是 False，走原始提示词，不影响出图。
   想启用增强再单独下载该模型，系统盘空间不够，建议放数据盘 `/root/sj-fs` 后软链进 `models/clip/`。
2. **磁盘**：系统盘 30G，已用约 17G（三个模型占 16.2G），剩余 13G。
   数据盘 `/root/sj-fs`（50G，可写）适合放大模型；`/root/sj-data` 是只读公共模型库。
3. **模板库版本**：`comfyui-workflow-templates` 仍是 0.11.41，启动时会有一条黄色提示，不影响使用（需要的 4 个工作流已直接放进 workflows 目录）。
4. 升级/回滚：`cd /ComfyUI && git log`，旧版本 v0.33.1 的 HEAD 记录在 `/root/backup_head.txt`。

## 实测记录

- 冒烟测试：`/ComfyUI/output/qwen21_smoke_00001_.png`（1024×1024，25 步，165 秒）
