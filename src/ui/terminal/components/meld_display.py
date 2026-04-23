"""副露显示组件。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kernel.hand.melds import MeldKind
from ui.terminal.components.tiles import tiles_to_display

if TYPE_CHECKING:
    from ui.terminal.components.name_resolver import NameResolver

_MELD_KIND_NAMES = {
    "chi": "吃",
    "pon": "碰",
    "daiminkan": "大明杠",
    "ankan": "暗杠",
    "shankuminkan": "加杠",
}


class MeldDisplay:
    """统一格式化终端 UI 中的副露信息。"""

    def __init__(self, name_resolver: "NameResolver") -> None:
        self._name_resolver = name_resolver

    def format_melds(
        self,
        melds: list | tuple,
        owner_seat: int,
        *,
        include_source: bool,
    ) -> str:
        """格式化副露列表。"""
        if not melds:
            return "无"
        return " ".join(
            self.format_meld(meld, owner_seat, include_source=include_source)
            for meld in melds
        )

    def format_meld(
        self,
        meld: Any,
        owner_seat: int,
        *,
        include_source: bool,
    ) -> str:
        """格式化单组副露。"""
        kind_value = getattr(meld.kind, "value", str(meld.kind))
        kind_name = _MELD_KIND_NAMES.get(kind_value, kind_value)
        tiles_text = tiles_to_display(meld.tiles)

        if meld.kind in (MeldKind.ANKAN, MeldKind.SHANKUMINKAN):
            return f"{kind_name}[{tiles_text}]"

        source = ""
        if include_source:
            source_seat = self._discarder_seat_for_meld(owner_seat, meld)
            if source_seat is not None:
                source = self._name_resolver.get_name_or_seat(source_seat)
        return f"{kind_name}{source}[{tiles_text}]"

    def _discarder_seat_for_meld(self, owner_seat: int, meld: Any) -> int | None:
        """将相对鸣牌来源还原为绝对座位。"""
        if meld.from_seat is None:
            return None
        return (owner_seat + meld.from_seat) % 4
