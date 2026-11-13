#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用批量出图执行器（Qwen-Image 2.1 / ComfyUI API）。

    COMFY=http://127.0.0.1:8080 python3 run_shots.py shots.json --tag my_drama

每个镜头输出到 ComfyUI/output/drama/<tag>/<id>_*.png，
同时写 <json>.done.json 记录断点结果，重跑会自动跳过已完成镜头。
"""
import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

DEFAULT_BASE = os.environ.get("COMFY", "http://127.0.0.1:8080").rstrip("/")
DEFAULT_UNET = "qwen_image_2.1_int8_convrot.safetensors"
DEFAULT_CLIP = "qwen3vl_8b_int8_convrot.safetensors"
DEFAULT_VAE = "qwen_image_2.1_vae_bf16.safetensors"


def post(base, path, payload):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=120) as r:
        return json.loads(r.read().decode())


def graph(
    prompt,
    w,
    h,
    prefix,
    seed,
    steps=25,
    cfg=1.0,
    refs=None,
    cast_tag="",
    negative_prompt="",
    sampler="euler",
    scheduler="simple",
    resolution=1024,
    unet_name=DEFAULT_UNET,
    clip_name=DEFAULT_CLIP,
    vae_name=DEFAULT_VAE,
):
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {
            "unet_name": unet_name, "weight_dtype": "default"}},
        "2": {"class_type": "QwenImage21Cache", "inputs": {
            "model": ["1", 0], "device": "auto", "dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": clip_name, "type": "qwen_image", "device": "default"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {
            "width": w, "height": h, "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["2", 0], "seed": seed, "steps": steps, "cfg": cfg,
            "sampler_name": sampler, "scheduler": scheduler,
            "positive": ["4", 0], "negative": ["4", 1],
            "latent_image": ["5", 0], "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["8", 0]}},
        "8": {"class_type": "VAELoader", "inputs": {"vae_name": vae_name}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": prefix}},
    }

    te = {
        "clip": ["3", 0],
        "prompt": prompt,
        "negative_prompt": negative_prompt or "",
        "resolution": resolution,
    }
    if refs:
        te["vae"] = ["8", 0]
        images = {}
        for i, cid in enumerate(refs, 1):
            nid = str(100 + i)
            raw_ref = str(cid)
            fname = raw_ref if raw_ref.endswith(".png") else "%s.png" % raw_ref
            img_path = fname if "/" in fname else "cast/%s/%s" % (cast_tag, fname)
            g[nid] = {"class_type": "LoadImage", "inputs": {"image": img_path}}
            images["image_%d" % i] = [nid, 0]
        te["images"] = images
    g["4"] = {"class_type": "TextEncodeQwenImage21", "inputs": te}
    return g


def wait(base, pid, timeout=600):
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(3)
        h = get(base, "/history/" + pid)
        if pid in h:
            entry = h[pid]
            status_obj = entry.get("status", {})
            st = status_obj.get("status_str")
            outs = entry.get("outputs", {})
            files = []
            for v in outs.values():
                for img in v.get("images", []):
                    files.append(img.get("filename"))
            msgs = status_obj.get("messages", [])
            return st, files, msgs
    return "timeout", [], []


def submit_with_retry(base, payload, retries=2):
    last_err = None
    for attempt in range(retries):
        try:
            return post(base, "/prompt", payload)
        except Exception as e:
            last_err = e
            if attempt + 1 < retries:
                time.sleep(2)
    raise last_err


def main():
    ap = argparse.ArgumentParser(description="按任务 JSON 批量调用 ComfyUI Qwen-Image 2.1 生成关键帧/定妆照")
    ap.add_argument("tasks", help="任务清单 JSON 路径")
    ap.add_argument("--tag", required=True, help="ComfyUI output/drama/<tag> 子目录名")
    ap.add_argument("--cast-tag", default="", help="参考图目录 input/cast/<cast-tag>，默认同 --tag")
    ap.add_argument("--base", default=DEFAULT_BASE, help="ComfyUI API 地址，默认读 COMFY 环境变量")
    ap.add_argument("--steps", type=int, default=25)
    ap.add_argument("--cfg", type=float, default=1.0)
    ap.add_argument("--resolution", type=int, default=1024)
    ap.add_argument("--sampler", default="euler")
    ap.add_argument("--scheduler", default="simple")
    ap.add_argument("--unet", default=DEFAULT_UNET)
    ap.add_argument("--clip", default=DEFAULT_CLIP)
    ap.add_argument("--vae", default=DEFAULT_VAE)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    base = args.base.rstrip("/")
    data = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    shots = data["shots"]
    if args.limit:
        shots = shots[:args.limit]

    done_path = Path(args.tasks + ".done.json")
    done = {}
    if done_path.exists():
        done = json.loads(done_path.read_text(encoding="utf-8"))

    print("共 %d 个镜头，已完成 %d" % (len(shots), len(done)), flush=True)
    t0 = time.time()
    for i, s in enumerate(shots, 1):
        sid = s["id"]
        if sid in done:
            print("[跳过] %s" % sid, flush=True)
            continue
        prefix = "drama/%s/%s" % (args.tag, sid)
        seed = int(s.get("seed") or (100000 + i * 137))
        workflow = graph(
            s["prompt"],
            s["w"],
            s["h"],
            prefix,
            seed,
            steps=args.steps,
            cfg=args.cfg,
            refs=s.get("refs"),
            cast_tag=args.cast_tag or args.tag,
            negative_prompt=s.get("negative_prompt", ""),
            sampler=args.sampler,
            scheduler=args.scheduler,
            resolution=args.resolution,
            unet_name=args.unet,
            clip_name=args.clip,
            vae_name=args.vae,
        )
        try:
            res = submit_with_retry(base, {"prompt": workflow, "client_id": "batch"})
        except Exception as e:
            print("[失败] %s 提交错误 %s" % (sid, e), flush=True)
            continue
        pid = res.get("prompt_id")
        st, files, msgs = wait(base, pid)
        cost = time.time() - t0
        if st == "success":
            done[sid] = files
            done_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
            print("[%d/%d] %s ok %.1fs seed=%d %s" % (i, len(shots), sid, cost, seed, files), flush=True)
        else:
            print("[%d/%d] %s 失败: %s node_err=%s msgs=%s" % (i, len(shots), sid, st, res.get("node_errors"), msgs[-2:] if msgs else []), flush=True)

    print("DONE 总耗时 %.1f 分钟" % ((time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    main()
