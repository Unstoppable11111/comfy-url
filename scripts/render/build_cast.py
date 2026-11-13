#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用定妆照与场景参考图任务清单生成器（适用任意题材/朝代/画幅短剧）。

结合 character-refs 几何正面铁律与 Qwen-Image 2.1 高清写实摄影参数：
    python build_cast.py <project_dir> -o tasks/cast.json
    python build_cast.py <project_dir> -o tasks/cast.json --with-face --with-scenes
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prompt_utils import (  # noqa: E402
    infer_era_profile,
    make_seed,
    read_json_optional,
    resolve_canvas,
    sanitize_close_appearance,
)

FULL_SIZE = (832, 1216)   # 2:3 竖版：全身定妆母版
FACE_SIZE = (896, 1120)   # 4:5 竖版：胸部以上面部特写锚点

FULL_GEOM_TAIL = (
    "，全身正面定妆基准照（Full-body front-facing character reference portrait），"
    "头顶至双脚完整入画且上下留白，双肩、髋部、双脚严格正对镜头，"
    "鼻梁位于面部正中线，双耳对称可见，双臂自然下垂于身体两侧、手指舒展无道具，"
    "平视镜头直视前方；纯浅灰无缝影棚背景（solid neutral light grey studio backdrop），"
    "柔和均匀影棚漫射光，自然哑光健康肤质（matte healthy skin, non-greasy），"
    "高清写实摄影，画面中严禁出现文字、标尺、水印或分格拼图边框"
)

FACE_GEOM_TAIL = (
    "，面部与肩颈特写定妆照（Close-up head-and-shoulders front portrait, 85mm portrait lens），"
    "胸部以上紧凑构图，严格平视正面，鼻梁位于面部正中线，双耳对称可见，"
    "五官骨相、眼神、年龄特征、发型与领口配饰极度清晰；"
    "纯浅灰无缝影棚背景，柔和均匀影棚漫射光，真实皮肤纹理且清爽哑光不油腻（matte non-greasy skin），"
    "高清写实摄影，严禁出现任何文字、水印或分格边框"
)

BASE_CHAR_NEG = (
    "塑料磨皮感，满脸油光反光，斜身侧站，低头仰头，遮挡面部，"
    "手持道具，多手多脚，手指畸形，多格拼图，三视图分格，文字，水印，背景杂物"
)

BASE_SCENE_NEG = (
    "people, human, person, face, silhouette, crowd, hands, distorted perspective, "
    "text, watermark, split grid, collage"
)


def build_cast_tasks(proj_dir: Path, with_face=False, with_scenes=False, aspect=""):
    proj_name = proj_dir.name
    cast = json.loads((proj_dir / "characters" / "cast.json").read_text(encoding="utf-8"))
    art = read_json_optional(proj_dir / "art" / "art.json")
    outline = read_json_optional(proj_dir / "outline" / "outline.json")
    sb = read_json_optional(proj_dir / "storyboard" / "storyboard.json")

    era = infer_era_profile(art, outline)
    ratio = aspect or sb.get("aspectRatio") or "9:16"
    sc_w, sc_h, ratio_zh = resolve_canvas(ratio)
    shots = []

    for c in cast.get("characters", []):
        cid = c["id"]
        name = c.get("name", cid)
        persona = c.get("persona") or {}
        age = persona.get("ageRange", "")
        gender = persona.get("gender", "")
        look = persona.get("appearance", "").strip()
        img = c.get("image") or {}
        base_en = (img.get("prompt") or "").strip()
        base_zh = (img.get("promptLocal") or "").strip()
        neg = (img.get("negativePrompt") or "").strip()

        neg_parts = [BASE_CHAR_NEG, era.get("era_negative", ""), neg]
        full_neg = "，".join(x for x in neg_parts if x)

        # 1) Tier-1 全身正面定妆母版
        header = f"角色定妆照：{name}（{age}{gender}）" if (age or gender) else f"角色定妆照：{name}"
        parts = [header, base_zh, look, base_en]
        prompt = "。".join(p for p in parts if p) + FULL_GEOM_TAIL
        shots.append({
            "id": cid,
            "ep": 0,
            "kind": "cast_full",
            "prompt": prompt,
            "negative_prompt": full_neg,
            "w": FULL_SIZE[0],
            "h": FULL_SIZE[1],
            "seed": make_seed(proj_name, f"{cid}_full"),
        })

        # 2) Tier-2 面部特写定妆锚点（通用正则剔除全身/下装词汇）
        if with_face:
            face_en = sanitize_close_appearance(base_en)
            face_zh = sanitize_close_appearance(base_zh)
            face_look = sanitize_close_appearance(look)
            f_parts = [f"角色面部特写锚点：{name}（{age}{gender}）", face_zh, face_look, face_en]
            f_prompt = "。".join(p for p in f_parts if p) + FACE_GEOM_TAIL
            shots.append({
                "id": f"{cid}_face",
                "ep": 0,
                "kind": "cast_face",
                "prompt": f_prompt,
                "negative_prompt": full_neg,
                "w": FACE_SIZE[0],
                "h": FACE_SIZE[1],
                "seed": make_seed(proj_name, f"{cid}_face"),
            })

    # 3) 可选：场景纯空镜建筑锚点（自动跟随 art.json 朝代与 storyboard 画幅）
    if with_scenes and art:
        for sc in art.get("scenes", []):
            sid = sc["id"]
            sname = sc.get("name", sid)
            anchors = "，".join(f"{a['name']}（{a['desc']}）" for a in sc.get("anchors", []))
            light_p = ((sc.get("lighting") or [{}])[0]).get("prompt", "")
            img_p = (sc.get("image") or {}).get("prompt", "")
            img_neg = (sc.get("image") or {}).get("negativePrompt", "")
            s_prompt = (
                f"{era['scene_prefix']}：{sname}，空间包含：{anchors}。"
                f"{img_p} {light_p} "
                f"{ratio_zh}电影级建筑实景摄影，无人空镜，画面中绝对不出现任何人物、人脸、手部或人形剪影，单帧满画幅无边框无文字水印。"
            )
            shots.append({
                "id": f"scene_{sid}",
                "ep": 0,
                "kind": "scene_ref",
                "prompt": s_prompt,
                "negative_prompt": f"{BASE_SCENE_NEG}, {img_neg}".strip(", "),
                "w": sc_w,
                "h": sc_h,
                "seed": make_seed(proj_name, f"scene_{sid}"),
            })

    return shots


def main():
    ap = argparse.ArgumentParser(description="从任意项目目录生成通用定妆照与场景锚点任务清单")
    ap.add_argument("project", help="项目目录路径（含 characters/cast.json）")
    ap.add_argument("-o", "--out", required=True, help="输出 JSON 路径")
    ap.add_argument("--with-face", action="store_true", help="同时生成 _face 胸部以上特写锚点任务")
    ap.add_argument("--with-scenes", action="store_true", help="同时生成 scene_S0X 空镜参考图任务")
    ap.add_argument("--aspect", default="", help="覆盖场景锚点画幅（如 9:16 或 16:9），默认读取 storyboard.json")
    args = ap.parse_args()

    proj_dir = Path(args.project).resolve()
    shots = build_cast_tasks(
        proj_dir,
        with_face=args.with_face,
        with_scenes=args.with_scenes,
        aspect=args.aspect,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"project": proj_dir.name, "shots": shots}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print("定妆/锚点任务 %d 个 -> %s" % (len(shots), args.out))


if __name__ == "__main__":
    main()
