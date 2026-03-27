"""校验模型选择与 ``legal_actions`` 一致。"""

from __future__ import annotations

from typing import Any

from kernel.api.legal_actions import LegalAction
from llm.wire import legal_action_to_wire


def normalize_choice(d: dict[str, Any]) -> dict[str, Any]:
    """与 ``legal_action_to_wire`` 省略规则对齐。"""
    out = dict(d)
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
