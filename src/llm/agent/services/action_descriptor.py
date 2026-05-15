"""Action descriptor functions.

Convert action objects to readable text descriptions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel.engine.actions import Action


def describe_action(action: "Action") -> str:
    """Convert action to readable text.

    Args:
        action: The action to describe.

    Returns:
        Human-readable description of the action.
    """
    from kernel.engine.actions import ActionKind

    kind = action.kind

    if kind == ActionKind.DISCARD:
        tile_code = action.tile.to_code() if action.tile else "?"
        riichi_str = "并立直" if action.declare_riichi else ""
        return f"打{tile_code}{riichi_str}"

    if kind == ActionKind.OPEN_MELD and action.meld:
        m = action.meld
        tiles = "/".join(t.to_code() for t in m.tiles) if m.tiles else "?"
        called = m.called_tile.to_code() if m.called_tile else "?"
        kind_map = {"chi": "吃", "pon": "碰", "daiminkan": "杠"}
        cn = kind_map.get(m.kind.value, m.kind.value)
        return f"{cn} {tiles} (叫{called})"

    if kind == ActionKind.ANKAN and action.meld:
        m = action.meld
        tiles = "/".join(t.to_code() for t in m.tiles) if m.tiles else "?"
        return f"暗杠 {tiles}"

    if kind == ActionKind.KAKAN and action.meld:
        m = action.meld
        tiles = "/".join(t.to_code() for t in m.tiles) if m.tiles else "?"
        called = m.called_tile.to_code() if m.called_tile else "?"
        return f"加杠 {tiles} (叫{called})"

    if kind == ActionKind.RON:
        return "荣和"

    if kind == ActionKind.TSUMO:
        return "自摸"

    if kind == ActionKind.PASS_CALL:
        return "跳过"

    if kind == ActionKind.DRAW:
        return "摸牌"

    return kind.value


def describe_action_summary(action: "Action") -> str | None:
    """Convert action to summary text, only returning key events.

    Key events include: win (ron/tsumo), riichi declaration, melds (chi/pon/kan).
    Normal actions (discard, draw, pass) return None.

    Args:
        action: The action to describe.

    Returns:
        Summary text for key events, or None for non-key events.
    """
    from kernel.engine.actions import ActionKind

    kind = action.kind

    # Key event 1: win
    if kind == ActionKind.RON:
        return "荣和"

    if kind == ActionKind.TSUMO:
        return "自摸"

    # Key event 2: riichi (detected via discard + declare_riichi)
    if kind == ActionKind.DISCARD and action.declare_riichi:
        tile_code = action.tile.to_code() if action.tile else "?"
        return f"打{tile_code}立直宣言"

    # Key event 3: melds (chi/pon/kan)
    if kind == ActionKind.OPEN_MELD and action.meld:
        m = action.meld
        tiles = "/".join(t.to_code() for t in m.tiles) if m.tiles else "?"
        kind_map = {"chi": "吃", "pon": "碰", "daiminkan": "杠"}
        cn = kind_map.get(m.kind.value, m.kind.value)
        return f"{cn}{tiles}"

    if kind == ActionKind.ANKAN and action.meld:
        m = action.meld
        tiles = "/".join(t.to_code() for t in m.tiles) if m.tiles else "?"
        return f"暗杠{tiles}"

    if kind == ActionKind.KAKAN and action.meld:
        m = action.meld
        tiles = "/".join(t.to_code() for t in m.tiles) if m.tiles else "?"
        return f"加杠{tiles}"

    # Non-key event: return None (not recorded)
    return None