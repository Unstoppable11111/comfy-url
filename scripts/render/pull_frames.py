#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把服务器上某个目录的成图下载到本地。

    python pull_frames.py --base http://xn-b.suanjiayun.com:61146 \
        --tag ref_qianlong --ids shots_qianlong_ref_ep1.json \
        --dest ../../projects/novel_01_qianlong/storyboard/frames
"""
import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="如 http://xn-b.suanjiayun.com:61146")
    ap.add_argument("--tag", required=True, help="服务器 output/drama 下的目录名")
    ap.add_argument("--ids", required=True, help="任务 json，取里面的 shot id")
    ap.add_argument("--dest", required=True)
    ap.add_argument("--suffix", default="_00001_")
    args = ap.parse_args()

    shots = json.loads(Path(args.ids).read_text(encoding="utf-8"))["shots"]
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    sub = "drama/%s" % args.tag
    ok = fail = 0
    t0 = time.time()
    for s in shots:
        sid = s["id"]
        fname = sid + args.suffix + ".png"
        url = "%s/view?%s" % (args.base.rstrip("/"), urllib.parse.urlencode(
            {"filename": fname, "subfolder": sub, "type": "output"}))
        out = dest / (sid + ".png")
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                out.write_bytes(r.read())
            ok += 1
        except Exception as e:
            fail += 1
            print("FAIL", sid, e)
    print("下载 %d 张，失败 %d，用时 %.1fs -> %s" % (ok, fail, time.time() - t0, dest))


if __name__ == "__main__":
    main()
