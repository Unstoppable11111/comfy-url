#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用短剧出图提示词辅助工具（与具体剧目、朝代、画幅解耦）。"""
import hashlib
import json
import re
from pathlib import Path

ASPECT_BUCKETS = {
    "9:16": (768, 1344, "竖屏9:16"),
    "16:9": (1344, 768, "横屏16:9"),
    "3:4": (896, 1152, "竖屏3:4"),
    "4:3": (1152, 896, "横屏4:3"),
    "2:3": (832, 1216, "竖屏2:3"),
    "3:2": (1216, 832, "横屏3:2"),
    "1:1": (1024, 1024, "方形1:1"),
}

_ANCIENT_HINTS = (
    "古", "唐", "宋", "元", "明", "清", "汉", "秦", "魏", "晋", "隋", "朝",
    "宫廷", "宫斗", "宅斗", "仙侠", "武侠", "玄幻", "修真", "江湖", "架空古代",
)
_PERIOD_HINTS = ("民国", "年代", "七零", "八零", "九零", "旧上海", "抗战")
_SCIFI_HINTS = ("科幻", "末世", "赛博", "星际", "废土", "未来")
_MODERN_HINTS = ("现代", "都市", "当代", "职场", "豪门", "校园", "商战", "悬疑")


def clean_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def read_json_optional(path: Path, default=None):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {} if default is None else default


def make_seed(namespace, *parts):
    key = ":".join([str(namespace), *(str(x) for x in parts)])
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return 100000 + (int(digest[:8], 16) % 8000000)


def resolve_canvas(aspect_ratio="9:16", override_size=""):
    """根据 storyboard.aspectRatio 或手工 WxH 解析通用画布分辨率与画幅描述。"""
    if override_size:
        m = re.match(r"^\s*(\d+)\s*[xX×,]\s*(\d+)\s*$", str(override_size))
        if not m:
            raise ValueError(f"无效分辨率格式 {override_size!r}，应为 WxH 如 768x1344")
        w, h = int(m.group(1)), int(m.group(2))
        ratio_tag = f"竖屏{aspect_ratio}" if h > w else (f"横屏{aspect_ratio}" if w > h else "方形1:1")
        return w, h, ratio_tag
    key = str(aspect_ratio or "9:16").strip()
    return ASPECT_BUCKETS.get(key, (768, 1344, f"竖屏{key}" if key else "竖屏9:16"))


def infer_era_profile(art=None, outline=None):
    """从 art.json(dynasty) 与 outline.json(params.genre) 动态推断时代与风格，不写死现代剧。"""
    art = art or {}
    outline = outline or {}
    dynasty = clean_text(art.get("dynasty", ""))
    genre = clean_text((outline.get("params") or {}).get("genre", ""))
    combined = f"{dynasty} {genre}".strip()

    if any(k in combined for k in _SCIFI_HINTS):
        label = genre or dynasty or "科幻"
        return {
            "era": "scifi",
            "style_tail": f"{label}实景影视写实电影感",
            "scene_prefix": f"{label}纯建筑环境空镜",
            "era_negative": "古装长袍，简陋道具，低分辨率，塑料模型感",
        }
    if any(k in combined for k in _ANCIENT_HINTS):
        label = f"{dynasty}{genre}" if (dynasty and genre and dynasty not in genre) else (dynasty or genre or "古装")
        return {
            "era": "ancient",
            "style_tail": f"{label}东方古装实景影视美学",
            "scene_prefix": f"{label}纯建筑场景空镜",
            "era_negative": "现代西装，现代T恤牛仔裤，运动鞋，手表，手机，现代化玻璃高楼，霓虹灯",
        }
    if any(k in combined for k in _PERIOD_HINTS):
        label = dynasty or genre or "民国年代"
        return {
            "era": "period",
            "style_tail": f"{label}年代写实电影感",
            "scene_prefix": f"{label}纯建筑场景空镜",
            "era_negative": "现代电子屏幕，科幻元素，当代快时尚服饰，仙侠古装长袍",
        }
    if any(k in combined for k in _MODERN_HINTS):
        label = genre if (genre and ("现代" in genre or "都市" in genre)) else f"{dynasty or '现代'}{genre or '都市短剧'}"
        return {
            "era": "modern",
            "style_tail": f"{label}写实电影感",
            "scene_prefix": f"{label}纯建筑空镜",
            "era_negative": "古装长袍，古代发髻，欧洲中世纪宫廷长裙",
        }
    label = genre or dynasty or "精品短剧"
    return {
        "era": "neutral",
        "style_tail": f"{label}实景影视电影感",
        "scene_prefix": f"{label}纯建筑环境空镜",
        "era_negative": "",
    }


def sanitize_close_appearance(text):
    """通用特写外貌清洗：按词法/正则剔除全身、体型及下装描述，适用任意剧目。"""
    s = str(text or "")
    # 1. 英文全身构图描述
    s = re.sub(
        r"\b[Ff]ull[- ]?body(?:\s+(?:character\s+concept\s+of|concept|portrait|shot|view))?\b",
        "",
        s,
    )
    # 2. 中文全身、身高、体型、广角焦距词汇
    s = re.sub(
        r"(?:全身站姿|全身|身高[约\d一二三四五六七八九十米厘米cm]*|体型|身材[匀称修长纤细丰满]*|"
        r"身姿[修长笔挺曼妙窈窕]*|身形[高挑修长瘦削魁梧]*|长腿|修长双腿|50mm\s*标准[^，。；]*|35mm\s*广角[^，。；]*)",
        "",
        s,
    )
    # 3. 剥离配饰中的鞋履与下装裤装短语，避免模型被迫拍到腿脚而拉远
    s = re.sub(
        r"(?:(?:配以|搭配|配|及|与|和|脚踩|脚蹬)\s*)?[^，。；、（）()与和及]*?(?:阔腿裤|西裤|长裤|短裤|牛仔裤|工装裤|休闲裤|高跟鞋|皮鞋|运动鞋|战靴|长靴|短靴|凉鞋|布鞋|绣花鞋|靴子)",
        "",
        s,
    )
    # 4. 将连衣裙/套裙/襦裙/长袍等全身服装词转为肩领上装细节（通用支持现代与古装）
    s = re.sub(
        r"(?:拖尾长裙|连衣裙|百褶裙|半身裙|蓬蓬裙|鱼尾裙|礼服裙|马面裙|套裙|长裙|短裙|襦裙|裙装)",
        "服饰肩领细节",
        s,
    )
    s = re.sub(r"(?:长袍|长衫|旧袍)", "上装衣襟", s)
    s = re.sub(r"[，,]{2,}", "，", s)
    s = re.sub(r"[；;]{2,}", "；", s)
    return s.strip(" ，。；,.")


def strip_empty_room_clauses(text):
    """从 art.json 的空镜光照英文提示词中移除无人约束，避免与人物关键帧冲突。"""
    s = str(text or "")
    s = re.sub(r",?\s*(?:absolutely\s+)?(?:no|without)\s+(?:people|humans?|person|crowd)\b[^.]*\.?", "", s, flags=re.I)
    s = re.sub(r",?\s*empty\s+(?:room|interior|hall|street|office|venue|courtyard|hallway|space)\b[^.]*\.?", "", s, flags=re.I)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" ,.")
