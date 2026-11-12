#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 cast.json 生成定妆照任务清单。

    python build_cast.py ../../projects/novel_01_qianlong -o cast_qianlong.json
"""
import argparse
import json
from pathlib import Path

SIZE = (832, 1216)  # 2:3 竖版，全身 + 脸部细节

TAIL = "，正面全身站姿，中性浅灰纯色背景，影棚柔光，服装与发型细节清晰，定妆照，高清写实"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    cast = json.loads((Path(args.project) / "characters" / "cast.json").read_text(encoding="utf-8"))
    shots = []
    for c in cast["characters"]:
        base = (c.get("image") or {}).get("prompt") or ""
        look = c.get("persona", {}).get("appearance", "")
        prompt = base.strip()
        if look:
            prompt += "。" + look
        prompt += TAIL
        shots.append({"id": c["id"], "ep": 0, "prompt": prompt, "w": SIZE[0], "h": SIZE[1]})

    Path(args.out).write_text(
        json.dumps({"project": Path(args.project).name, "shots": shots},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("定妆任务 %d 个 -> %s" % (len(shots), args.out))


if __name__ == "__main__":
    main()
