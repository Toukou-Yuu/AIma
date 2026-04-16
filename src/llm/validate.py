"""校验模型选择与 ``legal_actions`` 一致。"""

from __future__ import annotations

import re
from typing import Any

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import ActionKind
from llm.constants import CN_TO_TILE_MAP
from llm.wire import legal_action_to_wire


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
    - "大明杠..." -> daiminkan
    """
    action_str = action_str.strip()
    normalized = _normalize_action_text(action_str)

    # 1. 过
    if normalized in {"过", "跳过"}:
        for la in legal:
            if la.kind == ActionKind.PASS_CALL:
                return la
        return None

    # 2. 自摸
    if normalized == "自摸":
        for la in legal:
            if la.kind == ActionKind.TSUMO:
                return la
        return None

    # 3. 打牌（含立直）
    if normalized.startswith("打"):
        # 提取牌名
        match = re.match(r"打(.+?)(并立直)?$", normalized)
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
    if normalized.startswith("荣和"):
        tile_cn = normalized[2:].strip()
        tile_code = cn_to_tile_code(tile_cn) if tile_cn else None
        for la in legal:
            if la.kind == ActionKind.RON:
                win_tile = getattr(la, "win_tile", None) or la.tile
                if tile_code and win_tile:
                    if win_tile.to_code() == tile_code:
                        return la
                elif not tile_code:  # 没指定牌名，匹配任意荣和
                    return la
        return None

    # 5. 吃/碰/杠 - 与自然语言提示共用同一动作描述函数
    for la in legal:
        for alias in _natural_action_aliases(la):
            if normalized == alias:
                return la

    return None


def _normalize_action_text(text: str) -> str:
    """归一化模型输出动作文本，便于与提示词文案匹配。"""
    compact = re.sub(r"\s+", "", text.strip())
    compact = compact.replace("（", "(").replace("）", ")")
    compact = re.sub(r"(?<!大)明杠", "大明杠", compact)
    return compact


def _natural_action_aliases(action: LegalAction) -> set[str]:
    """为自然语言动作生成一组可接受别名。"""
    from llm.observation_format import action_to_natural_text

    base = action_to_natural_text(action, action.seat)
    aliases = {_normalize_action_text(base)}
    aliases.add(_normalize_action_text(base.replace("跳过", "过")))

    if action.meld is not None:
        meld = action.meld
        kind_alias_map = {
            "chi": "吃",
            "pon": "碰",
            "daiminkan": "大明杠",
            "ankan": "暗杠",
            "shankuminkan": "加杠",
        }
        kind_text = kind_alias_map.get(meld.kind.value, meld.kind.value)
        tile_text = "".join(_tile_to_cn_text(t) for t in meld.tiles)
        aliases.add(_normalize_action_text(f"{kind_text}{tile_text}"))
        aliases.add(_normalize_action_text(f"{kind_text}{' '.join(_tile_to_cn_text(t) for t in meld.tiles)}"))
        if meld.called_tile is not None:
            aliases.add(_normalize_action_text(f"{kind_text}{tile_text}(叫{_tile_to_cn_text(meld.called_tile)})"))

    return aliases


def _tile_to_cn_text(tile) -> str:
    """Tile -> 中文名。"""
    from llm.observation_format import tile_to_cn

    return tile_to_cn(tile)


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
