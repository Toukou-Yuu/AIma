"""Action 序列化：供 artifact 写入使用。"""

from __future__ import annotations

from typing import Any

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import Action
from kernel.event_log import GameEvent
from kernel.hand.melds import Meld
from kernel.replay_json import action_to_wire, game_event_to_wire, meld_to_wire


def action_to_record(action: Action) -> dict[str, Any]:
    """Action → 可读 JSON dict（复用 kernel.replay_json.action_to_wire）。

    Args:
        action: kernel Action 对象

    Returns:
        可 JSON 序列化的 dict
    """
    return action_to_wire(action)


def legal_action_to_record(legal_action: LegalAction) -> dict[str, Any]:
    """LegalAction → 可读 JSON dict。

    Args:
        legal_action: kernel LegalAction 对象

    Returns:
        可 JSON 序列化的 dict
    """
    d: dict[str, Any] = {
        "kind": legal_action.kind.value,
        "seat": legal_action.seat,
    }
    if legal_action.tile is not None:
        d["tile"] = legal_action.tile.to_code()
    if legal_action.meld is not None:
        d["meld"] = meld_to_wire(legal_action.meld)
    if legal_action.declare_riichi:
        d["declare_riichi"] = True
    return d


def meld_to_record(meld: Meld) -> dict[str, Any]:
    """Meld → 可读 JSON dict（复用 kernel.replay_json.meld_to_wire）。

    Args:
        meld: kernel Meld 对象

    Returns:
        可 JSON 序列化的 dict
    """
    return meld_to_wire(meld)


def event_to_record(event: GameEvent) -> dict[str, Any]:
    """GameEvent → 可读 JSON dict（复用 kernel.replay_json.game_event_to_wire）。

    Args:
        event: kernel GameEvent 对象

    Returns:
        可 JSON 序列化的 dict
    """
    return game_event_to_wire(event)