#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用短剧关键帧任务编译器（Qwen-Image 2.1 + shuohao-skills + character-refs 深度融合）。

适用任意题材（现代/古装/民国/仙侠/科幻）、任意画幅（9:16/16:9/3:4 等）与任意人物数量的短剧项目：

    python build_shots.py <project_dir> -o tasks/shots.json --ep 1 --ref
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prompt_utils import (  # noqa: E402
    clean_text,
    infer_era_profile,
    make_seed,
    read_json_optional,
    resolve_canvas,
    sanitize_close_appearance,
    strip_empty_room_clauses,
)

SHOT_SIZE_ZH = {
    "extreme-wide": "大远景",
    "wide": "全景",
    "medium": "中景",
    "close": "特写",
    "extreme-close": "大特写",
}

BASE_NEGATIVE = (
    "塑料磨皮感，满脸油光反光，改变参考图人物年龄，多手多脚，手指畸形，肢体残缺，"
    "画面出现汉字或英文乱码，字幕，水印，LOGO，多格漫画分镜边框，拼图"
)

TEXTUAL_PROP_HINTS = (
    "协议", "合同", "户口", "书", "信", "纸", "单页", "页", "契",
    "证", "卷", "奏折", "圣旨", "请柬", "帖子", "名片", "账本", "报告", "函", "状",
)


def load_context(project_dir: Path, override_size=""):
    art = json.loads((project_dir / "art" / "art.json").read_text(encoding="utf-8"))
    cast = json.loads((project_dir / "characters" / "cast.json").read_text(encoding="utf-8"))
    sb = json.loads((project_dir / "storyboard" / "storyboard.json").read_text(encoding="utf-8"))
    outline = read_json_optional(project_dir / "outline" / "outline.json")
    script = read_json_optional(project_dir / "script" / "script.json")
    staging = read_json_optional(project_dir / "staging" / "staging.json")

    w, h, ratio_zh = resolve_canvas(sb.get("aspectRatio", "9:16"), override_size=override_size)
    era = infer_era_profile(art, outline)

    art_scenes_by_id = {s["id"]: s for s in art.get("scenes", [])}
    art_scenes_by_idx = {i + 1: s for i, s in enumerate(art.get("scenes", []))}
    props = {x["id"]: x for x in art.get("props", [])}
    cast_chars = {c["id"]: c for c in cast.get("characters", [])}
    outline_chars = {c["id"]: c for c in outline.get("characters", [])}
    script_eps = {e["ep"]: e for e in script.get("episodes", [])}
    staging_map = {(s["ep"], s["scene"]): s for s in staging.get("scenes", [])}

    return {
        "proj_name": project_dir.name,
        "cast_lang": cast.get("lang", "zh"),
        "w": w,
        "h": h,
        "ratio_zh": ratio_zh,
        "era": era,
        "art": art,
        "art_scenes_by_id": art_scenes_by_id,
        "art_scenes_by_idx": art_scenes_by_idx,
        "props": props,
        "cast_chars": cast_chars,
        "outline_chars": outline_chars,
        "script_eps": script_eps,
        "staging_map": staging_map,
        "sb": sb,
        "portraits_dir": project_dir / "characters" / "portraits",
    }


def make_char_anchors(cid, cast_chars, outline_chars):
    """为任意角色动态生成「中全景全身锚点」与「特写去全身词锚点」。"""
    c = cast_chars.get(cid)
    oc = outline_chars.get(cid, {})
    if not c:
        name = oc.get("name", cid)
        role = clean_text(oc.get("role", ""))
        full_txt = f"{name}（{role}）" if role else name
        close_txt = sanitize_close_appearance(full_txt) or name
        return full_txt, close_txt

    name = c.get("name", cid)
    p = c.get("persona") or {}
    age = p.get("ageRange", "")
    gender = p.get("gender", "")
    identity = p.get("identity", "")
    app = clean_text(p.get("appearance", "")).rstrip("。")
    prefix = f"{name}（{age}{gender}" + (f"，{identity}" if identity else "")

    full_anchor = f"{prefix}，{app}）" if app else f"{prefix}）"
    close_app = sanitize_close_appearance(app)
    close_anchor = f"{prefix}，{close_app}）" if close_app else f"{prefix}）"
    return full_anchor, close_anchor


def get_scene_context(ctx, ep_no, seg):
    sc_idx = seg.get("sceneIndex")
    script_ep = ctx["script_eps"].get(ep_no, {})
    sc_list = script_ep.get("scenes", [])
    script_sc = sc_list[sc_idx - 1] if sc_idx and 1 <= sc_idx <= len(sc_list) else {}
    scene_id = script_sc.get("sceneId")
    art_sc = (
        ctx["art_scenes_by_id"].get(scene_id)
        or ctx["art_scenes_by_idx"].get(sc_idx)
        or {}
    )
    staging_sc = ctx["staging_map"].get((ep_no, sc_idx), {})
    return script_sc, art_sc, staging_sc


def format_scene_anchors(art_sc):
    """优先使用 art.json 具象物理 anchors，避免抽象剧情摘要干扰生图模型。"""
    if not art_sc:
        return "实景拍摄场地"
    name = clean_text(art_sc.get("name", "")) or "主场景"
    anchors = art_sc.get("anchors") or []
    anchor_items = []
    for a in anchors[:3]:
        aname = clean_text(a.get("name", ""))
        adesc = clean_text(a.get("desc", ""))
        if aname:
            anchor_items.append(f"{aname}（{adesc}）" if adesc else aname)
    if anchor_items:
        return f"{name}，空间具象陈设包括：" + "；".join(anchor_items)
    return name


def format_lighting(script_sc, art_sc, has_chars=False):
    lit_zh = clean_text(script_sc.get("lighting", ""))
    lights = art_sc.get("lighting") or []
    matched_en = ""
    for item in lights:
        if item.get("state") == lit_zh and item.get("prompt"):
            matched_en = item["prompt"]
            break
    if not matched_en and lights:
        matched_en = lights[0].get("prompt", "")
    if matched_en and has_chars:
        matched_en = strip_empty_room_clauses(matched_en)
    if lit_zh and matched_en:
        return f"{lit_zh}（{matched_en.rstrip('.')}）"
    return lit_zh or matched_en or "自然写实影视光线"


def format_beats_detail(cut, script_sc):
    f, t = cut.get("beats") or (None, None)
    flow = script_sc.get("flow") or []
    if not (isinstance(f, int) and isinstance(t, int) and 1 <= f <= len(flow)):
        return ""
    bits = []
    for b in flow[f - 1 : min(t, len(flow))]:
        if isinstance(b.get("line"), str):
            deliv = clean_text(b.get("delivery", ""))
            if deliv:
                bits.append(deliv)
        else:
            act = clean_text(b.get("action", "")).rstrip("。")
            if act:
                bits.append(act)
    return "；".join(bits)


def format_staging_detail(char_ids, staging_sc, cast_chars, outline_chars):
    places = {p["id"]: p for p in (staging_sc.get("places") or []) if p.get("present", True)}
    hints = []
    for cid in char_ids:
        pl = places.get(cid)
        if not pl or not pl.get("item"):
            continue
        cname = (cast_chars.get(cid) or outline_chars.get(cid) or {}).get("name", cid)
        item = clean_text(pl["item"])
        posture = "坐于" if pl.get("posture") == "sit" else "立于"
        hints.append(f"{cname}{posture}{item}旁")
    return "，".join(hints)


def format_props_detail(prop_ids, props_map):
    if not prop_ids:
        return ""
    descs = []
    has_textual = False
    for pid in prop_ids:
        pr = props_map.get(pid)
        if not pr:
            continue
        pname = clean_text(pr.get("name", pid))
        if any(h in pname for h in TEXTUAL_PROP_HINTS):
            has_textual = True
        anchors = [clean_text(a.get("name", "")) for a in (pr.get("anchors") or [])[:2] if a.get("name")]
        if anchors:
            descs.append(f"{pname}（细节：{'、'.join(anchors)}）")
        else:
            descs.append(pname)
    if not descs:
        return ""
    note = "（文件或纸面道具仅作视觉质感示意，不生成具体可读文字）" if has_textual else ""
    return "关键道具：" + "、".join(descs) + note


def build_framing_header(cut):
    """Framing-First：根据景别在 Prompt 最首部强制写死机位与取景边界。"""
    size = cut.get("size") or "medium"
    size_zh = SHOT_SIZE_ZH.get(size, "中景")
    lens = clean_text(cut.get("lens", ""))
    cam_pos = clean_text(cut.get("cameraPosition", ""))
    comp = clean_text(cut.get("composition", ""))

    if size in ("close", "extreme-close"):
        framing_cmd = "胸部以上近距离肖像取景，人脸及神态占主画幅，严禁退回全身或半身远景"
        if not lens or "50mm" in lens or "35mm" in lens:
            lens = "85mm人像长焦，浅景深"
    elif size == "medium":
        framing_cmd = "腰部以上半身取景，清晰展现人物神态、上半身衣着与手部戏剧动作"
        lens = lens or "50mm标准定焦，自然景深"
    else:
        framing_cmd = "全身与环境纵深取景，完整交代人物全身姿态与空间位置关系"
        if not lens or "50mm" in lens:
            lens = "35mm广角定焦，深景深"

    tech = [x for x in (framing_cmd, lens, cam_pos, comp) if x]
    return f"【{size_zh}镜头，{'，'.join(tech)}】"


def resolve_refs(cut, ctx, use_ref=True):
    char_ids = list(cut.get("characters") or [])
    cast_chars = ctx["cast_chars"]
    portraits_dir = ctx["portraits_dir"]
    size = cut.get("size") or "medium"
    is_close = size in ("close", "extreme-close")

    ref_files = []
    ref_cids = []
    non_ref_cids = []

    for cid in char_ids:
        if cid in cast_chars and use_ref:
            face_file = portraits_dir / f"{cid}_face.png"
            if is_close and face_file.exists():
                ref_files.append(f"{cid}_face")
            else:
                ref_files.append(cid)
            ref_cids.append(cid)
        else:
            non_ref_cids.append(cid)

    return ref_files, ref_cids, non_ref_cids


def build_negative_prompt(cut, ctx, shot_type):
    parts = [BASE_NEGATIVE]
    era_neg = ctx["era"].get("era_negative", "")
    if era_neg:
        parts.append(era_neg)
    if shot_type in ("scene", "prop"):
        parts.append("人物，人脸，人体剪影")
    if shot_type == "character":
        for cid in cut.get("characters") or []:
            c = ctx["cast_chars"].get(cid)
            neg = clean_text(((c or {}).get("image") or {}).get("negativePrompt", ""))
            if neg:
                parts.append(neg)
    # 去重保序
    seen = set()
    uniq = []
    for chunk in parts:
        for item in re.split(r"[，,]", chunk):
            tok = item.strip()
            if tok and tok not in seen:
                seen.add(tok)
                uniq.append(tok)
    return "，".join(uniq)


def build_shot_prompt(cut, ctx, ep_no, seg, use_ref=True):
    script_sc, art_sc, staging_sc = get_scene_context(ctx, ep_no, seg)
    scene_id = script_sc.get("sceneId") or art_sc.get("id", "")
    char_ids = list(cut.get("characters") or [])
    prop_ids = list(cut.get("props") or [])
    size = cut.get("size") or "medium"
    is_close = size in ("close", "extreme-close")
    era = ctx["era"]
    ratio_zh = ctx["ratio_zh"]

    framing_header = build_framing_header(cut)
    scene_anchor_str = format_scene_anchors(art_sc)
    lighting_str = format_lighting(script_sc, art_sc, has_chars=bool(char_ids))
    frame_text = clean_text(cut.get("frame", ""))
    if is_close and char_ids:
        frame_text = sanitize_close_appearance(frame_text)

    beat_detail = format_beats_detail(cut, script_sc)
    staging_detail = format_staging_detail(char_ids, staging_sc, ctx["cast_chars"], ctx["outline_chars"])
    prop_detail = format_props_detail(prop_ids, ctx["props"])

    focus = clean_text(cut.get("focus", ""))
    eyeline = clean_text(cut.get("eyeline", ""))

    # 分类 A：纯场景空镜（无角色、无道具）
    if not char_ids and not prop_ids:
        shot_type = "scene"
        prompt = (
            f"{framing_header}"
            f"{era['scene_prefix']}：{scene_anchor_str}。"
            f"画面内容：{frame_text}。"
            f"光线氛围：{lighting_str}。"
            f"无人空镜，画面中绝对不出现任何人物、人脸、手部或人形剪影，"
            f"{era['style_tail']}，真实35mm胶片光学景深，{ratio_zh}单帧满画幅无边框无文字水印。"
        )
        return shot_type, [], scene_id, prompt

    # 分类 B：纯道具特写镜（无角色、有道具）
    if not char_ids and prop_ids:
        shot_type = "prop"
        prompt = (
            f"{framing_header}"
            f"纯道具微距质感镜头，置于{art_sc.get('name', '主场景桌面')}：{prop_detail}。"
            f"画面细节：{frame_text}。"
            f"光线氛围：{lighting_str}。"
            f"纯道具镜头，画面中绝不出现任何完整人物面孔或人体，纸面不出现可读大字，"
            f"{era['style_tail']}，高清写实微距摄影，{ratio_zh}单帧满画幅无边框无文字水印。"
        )
        return shot_type, [], scene_id, prompt

    # 分类 C：人物关键帧（单人/多人/含配角，通用扩展到任意角色数 N）
    shot_type = "character"
    ref_files, ref_cids, non_ref_cids = resolve_refs(cut, ctx, use_ref=use_ref)

    edit_clauses = []
    if use_ref and ref_cids:
        if len(ref_cids) == 1:
            cid = ref_cids[0]
            full_a, close_a = make_char_anchors(cid, ctx["cast_chars"], ctx["outline_chars"])
            if is_close:
                edit_clauses.append(
                    f"严格保持参考图1中人物{close_a}的面部五官骨相、年龄特征、发型与领口衣着细节完全不变"
                    "（严禁退回全身构图，严禁改变人物年龄与面部特征），"
                    f"将人物置于{scene_anchor_str}中"
                )
            else:
                edit_clauses.append(
                    f"严格保持参考图1中人物{full_a}的面部五官、年龄特征、发型、体型和服装完全不变，"
                    f"将人物置于{scene_anchor_str}中"
                )
        else:
            bindings = []
            for idx, cid in enumerate(ref_cids, 1):
                full_a, close_a = make_char_anchors(cid, ctx["cast_chars"], ctx["outline_chars"])
                anchor = close_a if is_close else full_a
                bindings.append(f"参考图{idx}对应{anchor}")
            edit_clauses.append(
                f"多人同框场景：{'；'.join(bindings)}；"
                "严格保持每位角色各自的面部五官、年龄特征、发型与专属服装独立不变，"
                "严禁角色间串脸、混淆年龄服装或变成双胞胎，"
                f"将人物置于{scene_anchor_str}中"
            )
    else:
        descs = []
        for cid in char_ids:
            full_a, close_a = make_char_anchors(cid, ctx["cast_chars"], ctx["outline_chars"])
            descs.append(close_a if is_close else full_a)
        edit_clauses.append(f"场景为{scene_anchor_str}，人物包括：{'；'.join(descs)}")

    if use_ref and ref_cids and non_ref_cids:
        extra = [make_char_anchors(cid, ctx["cast_chars"], ctx["outline_chars"])[0] for cid in non_ref_cids]
        edit_clauses.append("同场配角为" + "、".join(extra))

    action_parts = [frame_text]
    if beat_detail and beat_detail not in frame_text:
        if is_close:
            beat_detail = sanitize_close_appearance(beat_detail)
        if beat_detail:
            action_parts.append(f"戏剧动作与神态：{beat_detail}")
    if staging_detail and staging_detail not in frame_text and not is_close:
        action_parts.append(f"空间站位：{staging_detail}")
    if prop_detail:
        action_parts.append(prop_detail)

    tech_tail_bits = [lighting_str]
    if focus:
        tech_tail_bits.append(f"焦点：{focus}")
    if eyeline:
        tech_tail_bits.append(f"视线：{eyeline}")

    quality_tail = (
        f"{era['style_tail']}，自然哑光健康肤质（matte skin, non-greasy, clear complexion），"
        f"真实35mm胶片光学景深，{ratio_zh}单帧满画幅画面，严禁出现任何文字、字幕、水印或分格边框"
    )

    parts = [framing_header] + edit_clauses + action_parts + ["，".join(tech_tail_bits), quality_tail]
    prompt = "。".join(p.strip("。 ") for p in parts if p and p.strip("。 ")) + "。"
    return shot_type, ref_files, scene_id, prompt


def build_tasks(project_dir: Path, ep=0, limit=0, ref=True, override_size=""):
    ctx = load_context(project_dir, override_size=override_size)
    shots = []

    for episode in ctx["sb"].get("episodes", []):
        if ep and episode.get("ep") != ep:
            continue
        for seg in episode.get("segments", []):
            for i, cut in enumerate(seg.get("cuts", []), 1):
                sid = "%s-%02d" % (seg["id"], i)
                shot_type, refs, scene_id, prompt = build_shot_prompt(
                    cut, ctx, episode.get("ep"), seg, use_ref=ref
                )
                neg_prompt = build_negative_prompt(cut, ctx, shot_type)
                shots.append({
                    "id": sid,
                    "ep": episode.get("ep"),
                    "shot_type": shot_type,
                    "size": cut.get("size", "medium"),
                    "characters": list(cut.get("characters") or []),
                    "props": list(cut.get("props") or []),
                    "scene_id": scene_id,
                    "refs": refs,
                    "prompt": prompt,
                    "negative_prompt": neg_prompt,
                    "w": ctx["w"],
                    "h": ctx["h"],
                    "seed": make_seed(ctx["proj_name"], episode.get("ep"), sid, len(shots) + 1),
                })
                if limit and len(shots) >= limit:
                    break
            if limit and len(shots) >= limit:
                break
        if limit and len(shots) >= limit:
            break

    return ctx["proj_name"], shots


def main():
    ap = argparse.ArgumentParser(description="通用短剧关键帧任务编译器")
    ap.add_argument("project", help="项目目录路径（含 art/characters/storyboard）")
    ap.add_argument("-o", "--out", required=True, help="输出任务 JSON 路径")
    ap.add_argument("--ep", type=int, default=0, help="指定集号，0 表示全部集")
    ap.add_argument("--limit", type=int, default=0, help="最多导出镜头数（调试抽样用）")
    ap.add_argument("--ref", action="store_true", help="带角色参考图（图生图）")
    ap.add_argument("--size", default="", help="手工覆盖分辨率 WxH（如 1344x768），默认按 storyboard.aspectRatio 推导")
    args = ap.parse_args()

    proj_dir = Path(args.project).resolve()
    proj_name, shots = build_tasks(
        proj_dir, ep=args.ep, limit=args.limit, ref=args.ref, override_size=args.size
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"project": proj_name, "shots": shots}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print("生成 %d 个镜头（%s）-> %s" % (len(shots), "带参考图(通用双Skill融合)" if args.ref else "纯文生图(通用双Skill融合)", args.out))


if __name__ == "__main__":
    main()
