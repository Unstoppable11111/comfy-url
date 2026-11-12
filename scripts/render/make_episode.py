#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令跑完一集：建任务 → 上传 → 生成 → 自动下载到本地。

    python make_episode.py ../../projects/novel_01_qianlong --ep 1 --tag qianlong
    python make_episode.py ../../projects/novel_02_fengming --ep 3 --tag fengming --no-ref

默认带角色参考图（图生图），跑完把 PNG 下载到
<project>/storyboard/frames/；--no-ref 时下载到 frames_textonly/ 并走纯文生图。
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "remote"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from term import Term  # noqa: E402
import push as pushmod  # noqa: E402

BASE = os.environ.get("DRAMA_BASE", "http://xn-b.suanjiayun.com:61146")
OUT_ROOT = "/ComfyUI/output/drama"


def sh(cmd):
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(HERE))


def pull(tag, ids_file, dest):
    shots = json.loads(Path(ids_file).read_text(encoding="utf-8"))["shots"]
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    ok = 0
    for s in shots:
        sid = s["id"]
        url = BASE.rstrip("/") + "/view?" + urllib.parse.urlencode(
            {"filename": sid + "_00001_.png", "subfolder": "drama/" + tag, "type": "output"})
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                (dest / (sid + ".png")).write_bytes(r.read())
            ok += 1
        except Exception as e:
            print("  FAIL", sid, e)
    print("下载 %d/%d 张 -> %s" % (ok, len(shots), dest))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--ep", type=int, default=1)
    ap.add_argument("--tag", required=True, help="服务器输出目录名，如 qianlong")
    ap.add_argument("--no-ref", action="store_true", help="纯文生图")
    ap.add_argument("--steps", type=int, default=25)
    args = ap.parse_args()

    proj = Path(args.project).resolve()
    name = proj.name
    ref = not args.no_ref
    task = HERE / ("shots_%s_ep%d%s.json" % (name, args.ep, "_ref" if ref else ""))
    dest = proj / "storyboard" / ("frames" if ref else "frames_textonly")

    # 1) 建任务
    cmd = [sys.executable, str(HERE / "build_shots.py"), str(proj),
           "-o", str(task), "--ep", str(args.ep)]
    if ref:
        cmd.append("--ref")
    sh(cmd)

    # 2) 上传并启动
    t = Term()
    try:
        if ref:
            casts = proj / "characters" / "portraits"
            if not casts.exists() or not any(casts.glob("*.png")):
                raise SystemExit("缺少定妆照：%s\n先跑 build_cast.py + 出图" % casts)
            print(t.cmd("python3 /root/setup_cast.py %s %s" % (args.tag, OUT_ROOT + "/cast_" + args.tag), wait=60))

        pushmod.upload(t, str(task), "/root/" + task.name)
        out_tag = ("ref_" if ref else "") + args.tag
        log = "/root/run_%s_ep%d.log" % (args.tag, args.ep)
        start = ("cd /root && COMFY=http://127.0.0.1:8080 nohup python3 run_shots.py %s "
                 "--tag %s --cast-tag %s --steps %d > %s 2>&1 & echo started"
                 % (task.name, out_tag, args.tag, args.steps, log))
        print(t.cmd(start, wait=30))

        # 3) 轮询
        t0 = time.time()
        for _ in range(240):
            time.sleep(20)
            line = t.cmd("tail -1 %s" % log, wait=30).strip()
            if line:
                print("  [%4.1f 分] %s" % ((time.time() - t0) / 60, line), flush=True)
            if "DONE" in line:
                break
            if "No such file" in line:
                break
    finally:
        t.close()

    # 4) 下载
    pull(out_tag, str(task), dest)


if __name__ == "__main__":
    main()
