#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把分镜表翻译成「带角色参考图」的出图任务清单。

    python build_shots.py ../../projects/novel_01_qianlong -o s.json --ep 1 --ref
"""
import argparse
import json
import re
from pathlib import Path

SIZE_9_16 = (768, 1344)


def clip(text, n=70):
    text = re.sub(r"\s+", "", str(text or ""))
    return text[:n]


def load(project):
    p = Path(project)
    art = json.loads((p / "art" / "art.json").read_text(encoding="utf-8"))
    cast = json.loads((p / "characters" / "cast.json").read_text(encoding="utf-8"))
    sb = json.loads((p / "storyboard" / "storyboard.json").read_text(encoding="utf-8"))
    scenes = {i + 1: s for i, s in enumerate(art.get("scenes", []))}
    props = {x["id"]: x for x in art.get("props", [])}
    chars = {c["id"]: c for c in cast.get("characters", [])}
    return scenes, props, chars, sb


def scene_text(scene):
    if not scene:
        return ""
    desc = clip(scene.get("summary", ""), 80)
    return "%s（%s）" % (scene.get("name", ""), desc) if desc else scene.get("name", "")


def build_edit_prompt(cut, scene, chars, props):
    """写成「编辑指令」，模型才会真的用参考图。"""
    ids = [c for c in (cut.get("characters") or []) if c in chars]
    names = "、".join(chars[c]["name"] for c in ids)

    if len(ids) == 1:
        head = "保持参考图中人物（%s）的长相、发型、体型和服装完全不变，" % names
    elif len(ids) > 1:
        head = "保持参考图中%d个人物（%s）各自的长相、发型、体型和服装完全不变，" % (len(ids), names)
    else:
        head = ""

    parts = [head + "把人物置于" + scene_text(scene) + "中"]

    frame = clip(cut.get("frame", ""), 80)
    if frame:
        parts.append(frame)

    tech = []
    if cut.get("lens"):
        tech.append(str(cut["lens"]))
    if cut.get("composition"):
        tech.append("%s构图" % cut["composition"])
    if tech:
        parts.append("，".join(tech))

    pnames = [props[p]["name"] for p in (cut.get("props") or []) if p in props]
    if pnames:
        parts.append("画面中可见道具：" + "、".join(pnames))

    parts.append("竖屏9:16，电影感，写实摄影，自然光，高细节")
    return "。".join(x for x in parts if x)


def build_text_prompt(cut, scene, chars, props):
    parts = []
    st = scene_text(scene)
    if st:
        parts.append(st)
    names = []
    for cid in cut.get("characters", []) or []:
        c = chars.get(cid)
        if not c:
            continue
        look = clip(c.get("persona", {}).get("appearance", ""), 45)
        names.append("%s（%s）" % (c.get("name", cid), look) if look else c.get("name", cid))
    if names:
        parts.append("画面人物：" + "；".join(names))
    pnames = [props[p]["name"] for p in (cut.get("props") or []) if p in props]
    if pnames:
        parts.append("道具：" + "、".join(pnames))
    frame = clip(cut.get("frame", ""), 80)
    if frame:
        parts.append(frame)
    tech = []
    if cut.get("lens"):
        tech.append(str(cut["lens"]))
    if cut.get("composition"):
        tech.append("%s构图" % cut["composition"])
    if tech:
        parts.append("，".join(tech))
    parts.append("竖屏9:16，电影感，写实摄影，自然光，高细节")
    return "。".join(x for x in parts if x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--ep", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ref", action="store_true", help="带角色参考图（图生图）")
    args = ap.parse_args()

    scenes, props, chars, sb = load(args.project)
    w, h = SIZE_9_16
    shots = []

    for ep in sb["episodes"]:
        if args.ep and ep["ep"] != args.ep:
            continue
        for seg in ep["segments"]:
            scene = scenes.get(seg.get("sceneIndex"))
            for i, cut in enumerate(seg.get("cuts", []), 1):
                sid = "%s-%02d" % (seg["id"], i)
                if args.ref:
                    prompt = build_edit_prompt(cut, scene, chars, props)
                    refs = [c for c in (cut.get("characters") or []) if c in chars]
                else:
                    prompt = build_text_prompt(cut, scene, chars, props)
                    refs = []
                shots.append({"id": sid, "ep": ep["ep"], "prompt": prompt,
                              "w": w, "h": h, "refs": refs})
                if args.limit and len(shots) >= args.limit:
                    break
            if args.limit and len(shots) >= args.limit:
                break
        if args.limit and len(shots) >= args.limit:
            break

    Path(args.out).write_text(
        json.dumps({"project": Path(args.project).name, "shots": shots},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("生成 %d 个镜头（%s）-> %s" % (len(shots), "带参考图" if args.ref else "纯文生图", args.out))


if __name__ == "__main__":
    main()
