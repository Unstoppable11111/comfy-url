# -*- coding: utf-8 -*-
"""
通用 AI 短剧工业级分镜生图引擎 (Universal AI Drama Storyboard Production Engine - Qwen v4.0)
100% 题材解耦 + 云端算力远程执行 + 跨双机进度同步版：
1. 两台电脑均无需本地显卡：通过 --comfy-url 连接云端 GPU (AutoDL / 算家云 ComfyUI)。
2. 跨电脑进度同步与云端任务接管 (progress.json)：
   - 电脑 A 提交云端任务后可随时关机；
   - 电脑 B 同步目录后运行同一命令，自动跳过已完成镜头，并凭 prompt_id 从云端回收电脑 A 投递的已渲染图片。
3. 支持 --style realistic (写实国剧风) 与 --style anime (精品2D漫剧风) 一键切换。
4. 基于通义千问 Qwen-Image 2.1 & Qwen-Image-Edit (TextEncodeQwenImageEditPlus)：
   - 角色动作镜头挂载 master_id/<角色ID>.png 锁死五官骨相，EmptySD3LatentImage (denoise=1.0) 释放动作与景别。
   - 纯道具特写与纯场景空镜自动剥离人像参考图与人像词。
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path

try:
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# 通用画质后缀库（对齐 02_通用Prompt标准库.md）
STYLE_SUFFIXES = {
    "realistic": (
        "，院线电影胶片质感，35mm电影镜头，真实细腻皮肤质感，自然光影层次，"
        "清爽哑光肤质，无油腻反光，深邃光学景深，大片级构图调色，大师级实拍RAW质感，单帧满画幅无边框无字幕。"
    ),
    "anime": (
        "，剧场版高定2D动画电影质感，精湛作画线条，细腻赛璐璐光影层次，"
        "电影级大景深构图，色彩饱满通透，单帧满画幅无边框无字幕。"
    )
}

NEGATIVE_PROMPT = (
    "低画质，模糊，磨皮塑料脸，满脸油光，猪油反光，畸变，多手多脚，手指畸形，"
    "欧美混血面孔，分格边框，多视图拼图，字幕，水印，文字，签名"
)


class UniversalDramaEngineQwen:
    def __init__(self, project_dir, comfy_url="http://127.0.0.1:8188", queue_depth=4, ep=1, style="realistic", force=False):
        self.project_dir = Path(project_dir).resolve()
        self.comfy_url = comfy_url.rstrip("/")
        self.queue_depth = queue_depth
        self.target_ep = ep
        self.style = style if style in STYLE_SUFFIXES else "realistic"
        self.suffix = STYLE_SUFFIXES[self.style]
        self.force = force

        # 通用项目目录结构
        self.characters_dir = self.project_dir / "characters"
        self.master_id_dir = self.characters_dir / "master_id"
        self.cast_json = self.characters_dir / "cast.json"
        self.storyboard_json = self.project_dir / "storyboard" / "storyboard.json"
        self.renders_dir = self.project_dir / "storyboard" / f"renders_qwen_ep{self.target_ep:02d}"
        self.progress_json = self.renders_dir / "progress.json"
        self.gallery_html = self.renders_dir / "gallery.html"

        self.renders_dir.mkdir(parents=True, exist_ok=True)
        self.master_id_dir.mkdir(parents=True, exist_ok=True)

        self.characters_data = {}
        self.progress_data = self.load_progress()
        self.load_characters()

    def load_progress(self):
        """加载跨电脑同步的进度账本 progress.json"""
        if not self.force and self.progress_json.exists():
            try:
                with open(self.progress_json, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"ep": self.target_ep, "style": self.style, "comfy_url": self.comfy_url, "shots": {}}

    def save_progress(self):
        """实时落盘进度账本，供另一台电脑无缝接力"""
        self.progress_data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        self.progress_data["comfy_url"] = self.comfy_url
        with open(self.progress_json, "w", encoding="utf-8") as f:
            json.dump(self.progress_data, f, ensure_ascii=False, indent=2)

    def load_characters(self):
        """解析任意项目的 cast.json，构建角色母版映射与通用中文描述"""
        if not self.cast_json.exists():
            print(f"⚠️ 未找到角色设定文件: {self.cast_json}，将使用通用角色描述")
            return

        try:
            with open(self.cast_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            chars = data.get("characters", [])
            for c in chars:
                cid = c.get("id")
                name = c.get("name", "")
                persona = c.get("persona", {})
                img_conf = c.get("image", {})

                zh_prompt = img_conf.get("promptLocal", "")
                if not zh_prompt:
                    gender = persona.get("gender", "青年")
                    age = persona.get("ageRange", "25岁")
                    identity = persona.get("identity", "")
                    appearance = persona.get("appearance", "")
                    zh_prompt = f"{age}中国{gender}，{identity}，{appearance}"

                self.characters_data[cid] = {
                    "name": name,
                    "prompt": zh_prompt,
                    "master_img": self.find_master_image(cid)
                }
            print(f"✅ 成功加载 {len(self.characters_data)} 位角色设定: {list(self.characters_data.keys())}")
        except Exception as e:
            print(f"❌ 解析角色设定异常: {e}")

    def find_master_image(self, cid):
        """查找角色唯一正脸母版图"""
        for ext in [".png", ".jpg", ".webp"]:
            p = self.master_id_dir / f"{cid}{ext}"
            if p.exists():
                return p.name
        anchors_dir = self.characters_dir / "anchors"
        if anchors_dir.exists():
            for f in anchors_dir.glob(f"*{cid}*.*"):
                return f.name
        return None

    def classify_cut(self, cut):
        """通用三分类器：prop (纯道具特写) / scene (纯场景空镜) / character (角色动作分镜)"""
        chars = cut.get("characters", [])
        size = cut.get("size", "中景").lower()
        shot = cut.get("shot", "")
        frame = cut.get("frame", "")

        prop_cues = ["特写", "微距", "close", "macro", "大特写"]
        if not chars and any(c in size or c in frame or c in shot for c in prop_cues):
            return "prop"

        if not chars:
            return "scene"

        return "character"

    def build_prompt_for_cut(self, cut, cut_id):
        """严格按 02_通用Prompt标准库.md 组装三分类提示词与动态种子"""
        cat = self.classify_cut(cut)
        size = cut.get("size", "中景")
        camera = cut.get("camera", "固定镜头")
        lens = cut.get("lens", "50mm镜头")
        shot = cut.get("shot", "")
        frame = cut.get("frame", "")
        chars = cut.get("characters", [])

        numeric_tail = "".join(ch for ch in cut_id if ch.isdigit())[-4:] or "1"
        cut_num = int(numeric_tail)

        if cat == "prop":
            prompt = (
                f"微距电影摄影特写，100mm微距镜头，焦点极清晰对准物体本身，景深自然柔和，真实物理材质与细节纹理。"
                f"无人物面孔，无人物肢体，纯道具特写。"
                f"具体物体状态与细节：{shot}。环境背景：{frame}{self.suffix}"
            )
            seed = 90000000 + (cut_num * 137)
            master_img = None
        elif cat == "scene":
            prompt = (
                f"电影宽画幅全景空镜，24mm变形广角镜头，宏大空间纵深与建筑透视，大气磅礴的自然光影与空间纵深感，空镜头，无人物肖像。"
                f"场景与氛围：{shot}。环境参考：{frame}{self.suffix}"
            )
            seed = 80000000 + (cut_num * 137)
            master_img = None
        else:
            char_descs = []
            main_master = None
            for c in chars:
                if c in self.characters_data:
                    c_info = self.characters_data[c]
                    char_descs.append(f"{c_info['prompt']}")
                    if not main_master and c_info["master_img"]:
                        main_master = c_info["master_img"]
                else:
                    char_descs.append("剧中核心角色")

            chars_str = "；".join(char_descs)
            style_head = "电影实拍级剧照，8K超高清画质" if self.style == "realistic" else "高定2D动画剧场版分镜，8K超清作画"
            prompt = (
                f"{style_head}，景别：{size}，运镜视角：{camera}，{lens}拍摄。"
                f"出镜人物角色：{chars_str}（严格保持参考图中的人物面部五官骨相、发型与服装完全一致）。"
                f"人物动作与剧情走位：{shot}。"
                f"场景环境与光影：{frame}{self.suffix}"
            )
            seed = 10000000 + (cut_num * 137)
            master_img = main_master

        return prompt, seed, cat, master_img

    def build_qwen_workflow(self, prompt_text, seed, ref_image=None, width=1056, height=1584, filename_prefix="qwen_drama/shot"):
        """构建通义千问 Qwen-Image-Edit 标准 ComfyUI 工作流"""
        wf = {
            "unet": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "qwen_image_2.1_int8_convrot.safetensors",
                    "weight_dtype": "default"
                }
            },
            "clip": {
                "class_type": "CLIPLoader",
                "inputs": {
                    "clip_name": "qwen3vl_8b_int8_convrot.safetensors",
                    "type": "qwen_image",
                    "device": "default"
                }
            },
            "vae": {
                "class_type": "VAELoader",
                "inputs": {
                    "vae_name": "qwen_image_2.1_vae_bf16.safetensors"
                }
            },
            "ms": {
                "class_type": "ModelSamplingAuraFlow",
                "inputs": {
                    "model": ["unet", 0],
                    "shift": 3.1,
                    "sampling": "flow"
                }
            },
            "neg": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["clip", 0],
                    "text": NEGATIVE_PROMPT
                }
            },
            "lat": {
                "class_type": "EmptySD3LatentImage",
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1
                }
            },
            "ks": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["ms", 0],
                    "positive": ["pos", 0],
                    "negative": ["neg", 0],
                    "latent_image": ["lat", 0],
                    "seed": seed,
                    "steps": 20,
                    "cfg": 2.5,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1.0
                }
            },
            "dec": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["ks", 0],
                    "vae": ["vae", 0]
                }
            },
            "save": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": filename_prefix,
                    "images": ["dec", 0]
                }
            }
        }

        if ref_image:
            wf["ref1"] = {
                "class_type": "LoadImage",
                "inputs": {"image": ref_image}
            }
            wf["pos"] = {
                "class_type": "TextEncodeQwenImageEditPlus",
                "inputs": {
                    "clip": ["clip", 0],
                    "vae": ["vae", 0],
                    "prompt": prompt_text,
                    "image1": ["ref1", 0]
                }
            }
        else:
            wf["pos"] = {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["clip", 0],
                    "text": prompt_text
                }
            }

        return wf

    def upload_image_if_needed(self, img_name):
        """将角色母版图上传至云端 ComfyUI input 目录"""
        for p in [self.master_id_dir / img_name, self.characters_dir / "anchors" / img_name]:
            if p.exists():
                try:
                    with open(p, "rb") as f:
                        r = requests.post(
                            f"{self.comfy_url}/upload/image",
                            files={"image": f},
                            proxies={"http": None, "https": None},
                            timeout=15
                        )
                    return r.status_code == 200
                except Exception:
                    pass
        return False

    def try_fetch_from_cloud_history(self, pid, local_path):
        """根据 prompt_id 尝试从云端 ComfyUI 回收已渲染完成的图片（支持跨电脑接力）"""
        try:
            h = requests.get(f"{self.comfy_url}/history/{pid}", proxies={"http": None, "https": None}, timeout=8).json()
            if pid in h:
                img_info = h[pid]["outputs"]["save"]["images"][0]
                fn = img_info["filename"]
                sub = img_info.get("subfolder", "")
                t = img_info.get("type", "output")
                v_resp = requests.get(
                    f"{self.comfy_url}/view?filename={fn}&subfolder={sub}&type={t}",
                    proxies={"http": None, "https": None},
                    timeout=30
                )
                if v_resp.status_code == 200 and len(v_resp.content) > 10240:
                    with open(local_path, "wb") as f:
                        f.write(v_resp.content)
                    return True
        except Exception:
            pass
        return False

    def run_production(self):
        print("=" * 80)
        print("🎬 通用 AI 短剧工业级分镜生图引擎 - 云端算力 & 双机同步版 (v4.0)")
        print(f"📁 项目路径: {self.project_dir}")
        print(f"☁️ 云端算力: {self.comfy_url}")
        print(f"🎬 目标剧集: 第 {self.target_ep} 集 | 视觉风格: {self.style}")
        print(f"🔄 进度账本: {self.progress_json}")
        print("=" * 80)

        try:
            r = requests.get(f"{self.comfy_url}/system_stats", timeout=5)
            if r.status_code != 200:
                print(f"❌ 无法连接到云端 ComfyUI: {self.comfy_url} (HTTP {r.status_code})")
                return False
            print(f"✅ 云端 ComfyUI 状态正常: {r.json().get('system', {}).get('os', 'unknown')}")
        except Exception as e:
            print(f"❌ 连接云端 ComfyUI 失败 ({self.comfy_url}): {e}")
            return False

        if not self.storyboard_json.exists():
            print(f"❌ 故事板文件不存在: {self.storyboard_json}")
            return False

        with open(self.storyboard_json, "r", encoding="utf-8") as f:
            sb = json.load(f)

        ep_data = None
        for ep_item in sb.get("episodes", []):
            if ep_item.get("ep") == self.target_ep:
                ep_data = ep_item
                break
        if not ep_data and sb.get("episodes"):
            ep_data = sb["episodes"][0]

        if not ep_data:
            print(f"❌ 未找到第 {self.target_ep} 集故事板数据")
            return False

        cuts_to_render = []
        for seg in ep_data.get("segments", []):
            seg_id = seg.get("id")
            for idx, cut in enumerate(seg.get("cuts", [])):
                cid = f"{seg_id}_{idx+1:02d}"
                prompt, seed, cat, master_img = self.build_prompt_for_cut(cut, cid)
                cuts_to_render.append({
                    "cid": cid,
                    "seg_id": seg_id,
                    "cut": cut,
                    "cat": cat,
                    "prompt": prompt,
                    "seed": seed,
                    "master_img": master_img,
                    "local_path": self.renders_dir / f"{cid}.png",
                    "filename": f"{cid}.png"
                })

        masters = set(c["master_img"] for c in cuts_to_render if c["master_img"])
        for m in masters:
            self.upload_image_if_needed(m)

        status_map = {}
        in_flight = {}
        queue = []
        done_count = 0
        total = len(cuts_to_render)

        # 检查跨电脑同步进度与云端已算完任务
        shots_record = self.progress_data.setdefault("shots", {})
        for c in cuts_to_render:
            cid = c["cid"]
            rec = shots_record.get(cid, {})
            # 1. 本地已有合格图片，直接跳过
            if not self.force and c["local_path"].exists() and c["local_path"].stat().st_size > 10240:
                status_map[cid] = {"status": "done", "cut": c}
                shots_record[cid] = {"status": "done", "prompt_id": rec.get("prompt_id"), "file": c["filename"]}
                done_count += 1
                print(f"⏭️ [断点跳过] 镜头 {cid} 本地已就绪")
                continue

            # 2. 另一台电脑曾提交过云端任务，尝试直接凭 prompt_id 从云端拉取结果
            prev_pid = rec.get("prompt_id")
            if not self.force and prev_pid:
                if self.try_fetch_from_cloud_history(prev_pid, c["local_path"]):
                    status_map[cid] = {"status": "done", "cut": c}
                    shots_record[cid]["status"] = "done"
                    done_count += 1
                    print(f"☁️ [云端接力回收] 镜头 {cid} 已从云端 History 直接取回 (PID: {prev_pid[:8]})")
                    continue

            status_map[cid] = {"status": "pending", "cut": c}
            queue.append(c)

        self.save_progress()
        print(f"\n📋 总计 {total} 镜 | 已完成 {done_count} 镜 | 待渲染 {len(queue)} 镜\n")

        def push_next(c):
            prefix = f"qwen_drama/{c['cid']}"
            wf = self.build_qwen_workflow(c["prompt"], c["seed"], ref_image=c["master_img"], filename_prefix=prefix)
            payload = json.dumps({"prompt": wf}, ensure_ascii=False).encode("utf-8")
            try:
                resp = requests.post(
                    f"{self.comfy_url}/prompt",
                    data=payload,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                    proxies={"http": None, "https": None},
                    timeout=15
                )
                pid = resp.json().get("prompt_id")
                if pid:
                    in_flight[pid] = c
                    shots_record[c["cid"]] = {"status": "running", "prompt_id": pid, "file": c["filename"]}
                    self.save_progress()
                    ref_tag = f"⚓ 母版参考: {c['master_img']}" if c['master_img'] else "无参考"
                    print(f"🚀 [云端推流] 镜头 {c['cid']} [{c['cat']} | {ref_tag}] -> PID: {pid[:8]}...")
                    return True
            except Exception as e:
                print(f"❌ 提交镜头失败 {c['cid']}: {e}")
            return False

        while len(in_flight) < self.queue_depth and queue:
            push_next(queue.pop(0))

        t0 = time.time()

        while in_flight:
            time.sleep(2)
            done_pids = []
            for pid, cut_item in list(in_flight.items()):
                if self.try_fetch_from_cloud_history(pid, cut_item["local_path"]):
                    done_pids.append(pid)
                    done_count += 1
                    sz_kb = os.path.getsize(cut_item["local_path"]) / 1024
                    status_map[cut_item["cid"]]["status"] = "done"
                    shots_record[cut_item["cid"]]["status"] = "done"
                    self.save_progress()
                    print(f"✅ [{done_count}/{total}] 镜头 {cut_item['cid']} 渲染完成! ({sz_kb:.1f} KB)")

            for pid in done_pids:
                del in_flight[pid]
                if queue:
                    push_next(queue.pop(0))

        total_time = time.time() - t0
        print("\n" + "=" * 80)
        print(f"🎉 分镜渲染完成！本次耗时: {total_time:.1f}s | 产物目录: {self.renders_dir}")
        print("=" * 80)

        self.generate_html_report(status_map, total_time)
        return True

    def generate_html_report(self, status_map, total_time):
        cards = []
        for cid, info in sorted(status_map.items()):
            cut = info["cut"]["cut"]
            cat = info["cut"]["cat"]
            fn = info["cut"]["filename"]
            stat = info.get("status", "unknown")
            master = info["cut"].get("master_img", "")
            badge_color = "#10b981" if stat == "done" else "#f59e0b"

            cards.append(f"""
            <div style="background:#1e293b; border-radius:12px; overflow:hidden; border:1px solid #334155; display:flex; flex-direction:column;">
                <div style="position:relative; width:100%; aspect-ratio:2/3; background:#0f172a;">
                    <img src="{fn}" alt="{cid}" style="width:100%; height:100%; object-fit:cover;" loading="lazy" />
                    <span style="position:absolute; top:8px; left:8px; background:rgba(0,0,0,0.7); color:#38bdf8; padding:3px 8px; border-radius:6px; font-size:12px; font-weight:bold;">{cid} [{cat}]</span>
                    <span style="position:absolute; top:8px; right:8px; background:{badge_color}; color:#fff; padding:3px 8px; border-radius:6px; font-size:12px; font-weight:bold;">{stat.upper()}</span>
                    {f'<span style="position:absolute; bottom:8px; left:8px; background:rgba(16,185,129,0.85); color:#fff; padding:2px 6px; border-radius:4px; font-size:11px;">🎭 母版: {master}</span>' if master else ''}
                </div>
                <div style="padding:12px; font-size:13px; color:#cbd5e1; flex:1;">
                    <div style="color:#f8fafc; font-weight:bold; margin-bottom:4px;">{cut.get('size', '中景')} | {cut.get('camera', '')}</div>
                    <div style="color:#94a3b8; font-size:12px;">{cut.get('shot', '')}</div>
                </div>
            </div>
            """)

        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>千问 Qwen-Image AI 短剧工业分镜画廊 - 第 {self.target_ep} 集</title>
    <style>
        body {{ background: #0f172a; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 24px; }}
        .header {{ max-width: 1600px; margin: 0 auto 24px auto; background: #1e293b; padding: 20px 28px; border-radius: 14px; border: 1px solid #334155; display:flex; justify-content:space-between; align-items:center; }}
        .grid {{ max-width: 1600px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1 style="margin:0 0 6px 0; font-size:22px; color:#38bdf8;">🎬 通用 AI 短剧分镜画廊 (第 {self.target_ep} 集 | 风格: {self.style})</h1>
            <p style="margin:0; font-size:14px; color:#94a3b8;">执行标准：Qwen-Image-Edit 原生多图参考 | TextEncodeQwenImageEditPlus 锁脸 | 云端跨电脑同步</p>
        </div>
        <div style="text-align:right;">
            <div style="font-size:24px; font-weight:bold; color:#10b981;">{len(status_map)} 镜全部就绪</div>
            <div style="font-size:13px; color:#94a3b8;">本次耗时: {total_time:.1f}s</div>
        </div>
    </div>
    <div class="grid">
        {"".join(cards)}
    </div>
</body>
</html>"""
        with open(self.gallery_html, "w", encoding="utf-8") as f:
            f.write(full_html)
        print(f"📄 画廊报告已生成: {self.gallery_html}")


def main():
    parser = argparse.ArgumentParser(description="通用 AI 短剧工业级生图引擎 (云端算力 & 双机同步版 v4.0)")
    parser.add_argument("--project", type=str, required=True, help="短剧项目根目录绝对路径")
    parser.add_argument("--comfy-url", type=str, default="http://127.0.0.1:8188", help="云端 ComfyUI 服务地址 (如 http://region.autodl.pro:xxxx)")
    parser.add_argument("--ep", type=int, default=1, help="目标生产集数 (默认 1)")
    parser.add_argument("--queue-depth", type=int, default=4, help="云端 ComfyUI 维持队列深度 (默认 4)")
    parser.add_argument("--style", type=str, default="realistic", choices=["realistic", "anime"], help="画风预设: realistic(写实国剧) / anime(精品漫剧)")
    parser.add_argument("--force", action="store_true", help="强制忽略断点缓存重新生成全部镜头")

    args = parser.parse_args()
    engine = UniversalDramaEngineQwen(
        project_dir=args.project,
        comfy_url=args.comfy_url,
        queue_depth=args.queue_depth,
        ep=args.ep,
        style=args.style,
        force=args.force
    )
    engine.run_production()


if __name__ == "__main__":
    main()
