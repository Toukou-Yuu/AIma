"""校验模型选择与 ``legal_actions`` 一致。"""

from __future__ import annotations

import re
from typing import Any

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import ActionKind
from kernel.tiles.model import Tile
from llm.wire import legal_action_to_wire

# 中文牌面反向映射
CN_TO_TILE_MAP = {
    "一万": "1m", "二万": "2m", "三万": "3m", "四万": "4m", "五万": "5m",
    "六万": "6m", "七万": "7m", "八万": "8m", "九万": "9m",
    "一筒": "1p", "二筒": "2p", "三筒": "3p", "四筒": "4p", "五筒": "5p",
    "六筒": "6p", "七筒": "7p", "八筒": "8p", "九筒": "9p",
    "一索": "1s", "二索": "2s", "三索": "3s", "四索": "4s", "五索": "5s",
    "六索": "6s", "七索": "7s", "八索": "8s", "九索": "9s",
    "东": "1z", "南": "2z", "西": "3z", "北": "4z",
    "白": "5z", "发": "6z", "中": "7z",
    # 赤宝牌
    "五万赤": "5mr", "五筒赤": "5pr", "五索赤": "5sr",
    "五万(赤)": "5mr", "五筒(赤)": "5pr", "五索(赤)": "5sr",
}


def cn_to_tile_code(cn: str) -> str | None:
    """将中文牌名转换为编码."""
    # 处理赤宝牌的括号
    cn_clean = cn.replace("(赤)", "赤")
    return CN_TO_TILE_MAP.get(cn_clean)


def parse_cn_action(action_str: str, legal: tuple[LegalAction, ...]) -> LegalAction | None:
    """解析中文动作描述并匹配合法动作.

    支持格式：
    - "打三万" -> discard
    - "打三万并立直" -> discard + riichi
    - "过" -> pass_call
    - "荣和三万" -> ron
    - "自摸" -> tsumo
    - "吃..." -> open_meld
    - "碰..." -> pon
    - "明杠..." -> daiminkan
    """
    action_str = action_str.strip()

    # 1. 过
    if action_str == "过" or action_str == "跳过":
        for la in legal:
            if la.kind == ActionKind.PASS_CALL:
                return la
        return None

    # 2. 自摸
    if action_str == "自摸":
        for la in legal:
            if la.kind == ActionKind.TSUMO:
                return la
        return None

    # 3. 打牌（含立直）
    if action_str.startswith("打"):
        # 提取牌名
        match = re.match(r"打(.+?)(并立直)?$", action_str)
        if match:
            tile_cn = match.group(1)
            declare_riichi = match.group(2) is not None
            tile_code = cn_to_tile_code(tile_cn)
            if tile_code:
                for la in legal:
                    if la.kind == ActionKind.DISCARD:
                        la_code = la.tile.to_code() if la.tile else None
                        riichi_match = (la.declare_riichi == declare_riichi)
                        if la_code == tile_code and riichi_match:
                            return la
        return None

    # 4. 荣和
    if action_str.startswith("荣和"):
        tile_cn = action_str[2:].strip()
        tile_code = cn_to_tile_code(tile_cn) if tile_cn else None
        for la in legal:
            if la.kind == ActionKind.RON:
                if tile_code and la.win_tile:
                    if la.win_tile.to_code() == tile_code:
                        return la
                elif not tile_code:  # 没指定牌名，匹配任意荣和
                    return la
        return None

    # 5. 吃/碰/杠 - 复杂情况，暂时不解析，回退到旧格式
    if any(k in action_str for k in ["吃", "碰", "杠"]):
        return None

    return None


def explain_text_from_choice(d: dict[str, Any]) -> str | None:
    """模型 JSON 中的 ``why`` 字段，供可读日志；非法或空则 ``None``。"""
    w = d.get("why")
    if w is None:
        return None
    if isinstance(w, str):
        s = w.strip()
        return s if s else None
    s = str(w).strip()
    return s if s else None


def normalize_choice(d: dict[str, Any]) -> dict[str, Any]:
    """与 ``legal_action_to_wire`` 省略规则对齐；去掉模型附加的 ``why`` 等不参与匹配的字段。"""
    out = {k: v for k, v in d.items() if k != "why"}
    if out.get("kind") == "discard" and out.get("declare_riichi") is False:
        out.pop("declare_riichi", None)
    return out


def find_matching_legal_action(
    legal: tuple[LegalAction, ...],
    choice: dict[str, Any],
) -> LegalAction | None:
    """若 ``choice`` 与某一合法动作 wire 表示一致则返回该动作.

    支持两种格式：
    1. 旧格式: {"kind": "discard", "seat": 0, "tile": "3m", "why": "..."}
    2. 新格式: {"action": "打三万", "why": "..."}
    """
    # 尝试新格式（action 字段）
    action_str = choice.get("action")
    if action_str and isinstance(action_str, str):
        la = parse_cn_action(action_str, legal)
        if la:
            return la

    # 尝试旧格式（kind 字段）
    norm = normalize_choice(choice)
    for la in legal:
        w = legal_action_to_wire(la)
        if w == norm:
            return la
    return None
