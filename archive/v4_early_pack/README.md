# 归档说明：早期通用工业化原型包（2026-11-05）

> **状态：已归档（仅供设计参考，勿直接用于当前生产）**

本目录原名为 `AI短剧通用工业化核心包`，是 2026-11-05 设计的早期 v4.0 通用方案原型。后续在算家云实际部署并跑通 `Qwen-Image 2.1`（ComfyUI v0.44.2）后，已固化为新的现役流水线。

## 与现役流水线的核心差异

| 对比项 | 本归档包（早期 v4.0 设计） | 现役已验证流水线（`scripts/render/` + `docs/关键帧生产流程.md`） |
| :--- | :--- | :--- |
| **ComfyUI 生图节点** | `TextEncodeQwenImageEditPlus` + `EmptySD3LatentImage` | `TextEncodeQwenImage21`（`images` 传字典 + 接 `vae`） |
| **画幅与分辨率** | `1056×1584`（2:3） | 定妆 `832×1216`（2:3）；关键帧 `768×1344`（9:16） |
| **采样参数** | `steps=20`, `cfg=2.5`, `ModelSamplingAuraFlow` | `steps=25`, `cfg=1.0`, `euler + simple` |
| **目录约定** | `characters/master_id/`、`storyboard/renders_qwen_epXX/` | `characters/portraits/`、`storyboard/frames/` |
| **提示词结构** | 描述型提示词 + 正/负提示词 | **编辑指令型**（`保持参考图中人物（...）...`） |

## 仍可借鉴的设计思路

- **三分类解耦**：`03_universal_drama_engine.py` 中对 `character` / `prop` / `scene` 镜头的提示词隔离逻辑（避免纯空镜/道具镜头强行带上角色参考图与人物描述）。
- **跨机断点账本**：`progress.json` 记录云端 `prompt_id` 供双机接力回收的设计，可作为后续升级 `run_shots.py` 的参考。
