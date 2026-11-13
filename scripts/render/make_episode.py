#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用单集/整剧关键帧全自动生成流水线：建任务 → 同步参考图 → 推送执行 → 回传成图并生成预览拼图。

    python make_episode.py ../../projects/<project_dir> --ep 1 --tag <drama_tag>
    python make_episode.py ../../projects/<project_dir> --ep 0 --tag <drama_tag>   # 生成全集
    python make_episode.py ../../projects/<project_dir> --ep 3 --tag <drama_tag> --no-ref
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "remote"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from term import Term  # noqa: E402
import push as pushmod  # noqa: E402
from sjconfig import get as cfg_get  # noqa: E402

DEFAULT_BASE = os.environ.get("DRAMA_BASE") or cfg_get("DRAMA_BASE") or "http://xn-b.suanjiayun.com:61146"


def sh(cmd):
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(HERE))


def upload_portraits_http(casts_dir: Path, cast_tag: str, base: str):
    """通过 ComfyUI /upload/image 接口将本地定妆母版直接推送到远端 input/cast/<cast_tag>/。"""
    files = sorted(casts_dir.glob("*.png"))
    if not files:
        return 0
    ok = 0
    endpoint = base.rstrip("/") + "/upload/image"
    for fpath in files:
        boundary = "----AntigravityBoundary" + uuid.uuid4().hex
        raw = fpath.read_bytes()
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"subfolder\"\r\n\r\ncast/{cast_tag}\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"type\"\r\n\r\ninput\r\n".encode(),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n".encode(),
            (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"image\"; filename=\"{fpath.name}\"\r\n"
                f"Content-Type: image/png\r\n\r\n"
            ).encode()
            + raw
            + f"\r\n--{boundary}--\r\n".encode(),
        ]
        body = b"".join(parts)
        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read().decode())
        ok += 1
        print("  upload ref -> %s/%s" % (res.get("subfolder", ""), res.get("name", fpath.name)), flush=True)
    return ok


def pull(tag, ids_file, dest, base: str):
    shots = json.loads(Path(ids_file).read_text(encoding="utf-8"))["shots"]
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    ok = 0
    for s in shots:
        sid = s["id"]
        url = base.rstrip("/") + "/view?" + urllib.parse.urlencode(
            {"filename": sid + "_00001_.png", "subfolder": "drama/" + tag, "type": "output"})
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                (dest / (sid + ".png")).write_bytes(r.read())
            ok += 1
        except Exception as e:
            print("  FAIL", sid, e)
    print("下载 %d/%d 张 -> %s" % (ok, len(shots), dest))
    return ok


def save_contact_sheet(dest: Path, out_jpg: Path, ids_file: Path, cols=4, out_w=1200):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return
    shots = json.loads(ids_file.read_text(encoding="utf-8"))["shots"]
    items = [(s["id"], dest / (s["id"] + ".png")) for s in shots if (dest / (s["id"] + ".png")).exists()]
    if not items:
        return
    cell_w = out_w // cols
    sample = Image.open(items[0][1])
    cell_h = int(cell_w * sample.height / sample.width)
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (out_w, rows * (cell_h + 20)), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    for idx, (sid, p) in enumerate(items):
        im = Image.open(p).convert("RGB").resize((cell_w, cell_h))
        x = (idx % cols) * cell_w
        y = (idx // cols) * (cell_h + 20)
        sheet.paste(im, (x, y + 20))
        draw.text((x + 6, y + 4), sid, fill=(235, 235, 235))
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_jpg, "JPEG", quality=85)
    print("联系表预览图 -> %s" % out_jpg)


def main():
    ap = argparse.ArgumentParser(description="通用短剧关键帧单集/全集流水线")
    ap.add_argument("project", help="项目目录路径")
    ap.add_argument("--ep", type=int, default=1, help="集号（0 表示全部集）")
    ap.add_argument("--tag", required=True, help="服务器输出目录标签")
    ap.add_argument("--cast-tag", default="", help="服务器参考图目录标签（默认同 --tag）")
    ap.add_argument("--base", default=DEFAULT_BASE, help="ComfyUI 公网端口地址（用于自动传参考图与回传成图）")
    ap.add_argument("--no-ref", action="store_true", help="纯文生图")
    ap.add_argument("--steps", type=int, default=25)
    ap.add_argument("--cfg", type=float, default=1.0)
    ap.add_argument("--size", default="", help="覆盖画幅分辨率 WxH，默认读取 storyboard.aspectRatio")
    args = ap.parse_args()

    proj = Path(args.project).resolve()
    name = proj.name
    ref = not args.no_ref
    cast_tag = args.cast_tag or args.tag
    base = args.base.rstrip("/")
    ep_label = "ep%d" % args.ep if args.ep else "all"

    tasks_dir = HERE / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task = tasks_dir / ("shots_%s_%s%s.json" % (name, ep_label, "_ref" if ref else ""))
    dest = proj / "storyboard" / ("frames" if ref else "frames_textonly")

    # 1) 建任务（通用双 Skill 融合编译器）
    cmd = [sys.executable, str(HERE / "build_shots.py"), str(proj),
           "-o", str(task), "--ep", str(args.ep)]
    if ref:
        cmd.append("--ref")
    if args.size:
        cmd.extend(["--size", args.size])
    sh(cmd)

    # 2) 上传定妆参考图（HTTP 自动推送至 input/cast/<cast_tag>/）并启动远端生成
    if ref:
        casts = proj / "characters" / "portraits"
        if not casts.exists() or not any(casts.glob("*.png")):
            raise SystemExit("缺少定妆照：%s\n先跑 build_cast.py + 出图" % casts)
        try:
            upload_portraits_http(casts, cast_tag, base)
        except Exception as e:
            print("HTTP 上传定妆照跳过（将改用远端 setup_cast.py）：%s" % e)

    t = Term()
    try:
        if ref:
            pushmod.upload(t, str(HERE / "setup_cast.py"), "/root/setup_cast.py")
            t.cmd("python3 /root/setup_cast.py %s /ComfyUI/output/drama/cast_%s || true" % (cast_tag, cast_tag), wait=60)

        pushmod.upload(t, str(HERE / "run_shots.py"), "/root/run_shots.py")
        pushmod.upload(t, str(task), "/root/" + task.name)
        out_tag = ("ref_" if ref else "") + args.tag
        log = "/root/run_%s_%s.log" % (args.tag, ep_label)
        start = ("cd /root && COMFY=http://127.0.0.1:8080 nohup python3 run_shots.py %s "
                 "--tag %s --cast-tag %s --steps %d --cfg %s > %s 2>&1 & echo started"
                 % (task.name, out_tag, cast_tag, args.steps, args.cfg, log))
        print(t.cmd(start, wait=30))

        # 3) 轮询
        t0 = time.time()
        for _ in range(240):
            time.sleep(20)
            line = t.cmd("tail -1 %s" % log, wait=30).strip()
            if line:
                print("  [%4.1f 分] %s" % ((time.time() - t0) / 60, line), flush=True)
            if "DONE" in line or "No such file" in line:
                break
    finally:
        t.close()

    # 4) 下载并生成联系表预览图
    pull(out_tag, str(task), dest, base)
    preview_jpg = ROOT / "docs" / "previews" / ("sheet_%s_%s%s.jpg" % (args.tag, ep_label, "" if ref else "_textonly"))
    save_contact_sheet(dest, preview_jpg, task)


if __name__ == "__main__":
    main()
