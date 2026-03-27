"""校验模型选择与 ``legal_actions`` 一致。"""

from __future__ import annotations

from typing import Any

from kernel.api.legal_actions import LegalAction
from llm.wire import legal_action_to_wire


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
    """若 ``choice`` 与某一合法动作 wire 表示一致则返回该动作。"""
    norm = normalize_choice(choice)
    for la in legal:
        w = legal_action_to_wire(la)
        if w == norm:
            return la
    return None
