#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 tasks json 批量出关键帧（Qwen-Image 2.1 / ComfyUI）。

    COMFY=http://127.0.0.1:8080 python3 run_shots.py shots_qianlong_ep1.json --tag qianlong

每个镜头一张，存到 ComfyUI/output/drama/<tag>/<id>_*.png，
同时写 <json>.done.json 记录结果，重跑会跳过已完成。
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("COMFY", "http://127.0.0.1:8080").rstrip("/")


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=120) as r:
        return json.loads(r.read().decode())


def graph(prompt, w, h, prefix, seed, steps=25, cfg=1.0, refs=None, cast_tag=""):
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {
            "unet_name": "qwen_image_2.1_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "QwenImage21Cache", "inputs": {
            "model": ["1", 0], "device": "auto", "dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": "qwen3vl_8b_int8_convrot.safetensors", "type": "qwen_image", "device": "default"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {
            "width": w, "height": h, "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["2", 0], "seed": seed, "steps": steps, "cfg": cfg,
            "sampler_name": "euler", "scheduler": "simple",
            "positive": ["4", 0], "negative": ["4", 1],
            "latent_image": ["5", 0], "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["8", 0]}},
        "8": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": prefix}},
    }

    te = {"clip": ["3", 0], "prompt": prompt, "negative_prompt": "", "resolution": 1024}
    if refs:
        te["vae"] = ["8", 0]
        images = {}
        for i, cid in enumerate(refs, 1):
            nid = str(100 + i)
            g[nid] = {"class_type": "LoadImage",
                      "inputs": {"image": "cast/%s/%s.png" % (cast_tag, cid)}}
            images["image_%d" % i] = [nid, 0]
        te["images"] = images
    g["4"] = {"class_type": "TextEncodeQwenImage21", "inputs": te}
    return g


def wait(pid, timeout=600):
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(3)
        h = get("/history/" + pid)
        if pid in h:
            entry = h[pid]
            st = entry.get("status", {}).get("status_str")
            outs = entry.get("outputs", {})
            files = []
            for v in outs.values():
                for img in v.get("images", []):
                    files.append(img.get("filename"))
            return st, files
    return "timeout", []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks")
    ap.add_argument("--tag", required=True, help="输出子目录名，如 qianlong")
    ap.add_argument("--steps", type=int, default=25)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cast-tag", default="", help="参考图目录名，默认同 --tag")
    args = ap.parse_args()

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
        try:
            res = post("/prompt", {"prompt": graph(s["prompt"], s["w"], s["h"], prefix, i,
                                                  refs=s.get("refs"),
                                                  cast_tag=args.cast_tag or args.tag),
                                   "client_id": "batch"})
        except Exception as e:
            print("[失败] %s 提交错误 %s" % (sid, e), flush=True)
            continue
        pid = res.get("prompt_id")
        st, files = wait(pid)
        cost = time.time() - t0
        if st == "success":
            done[sid] = files
            done_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
            print("[%d/%d] %s ok %.1fs %s" % (i, len(shots), sid, cost, files), flush=True)
        else:
            print("[%d/%d] %s 失败: %s %s" % (i, len(shots), sid, st, res.get("node_errors")), flush=True)

    print("DONE 总耗时 %.1f 分钟" % ((time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    main()
