"""杠后岭上摸与杠宝指示牌翻开。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kernel.hand.multiset import add_tile
from kernel.play.model import TurnPhase
from kernel.wall.split import INDICATOR_COUNT, RINSHAN_COUNT

if TYPE_CHECKING:
    from kernel.deal.model import BoardState


def apply_after_kan_rinshan_draw(board: BoardState, seat: int) -> BoardState:
    """
    开杠并已更新手牌/副露之后：岭上摸一张、翻下一枚表指示牌，进入 ``MUST_DISCARD``（15 张须打）。

    岭上顺序：``dead_wall.rinshan[rinshan_draw_index]`` 从 0 递增（见 ``wall/README.md``）。
    """
    from kernel.deal.model import BoardState

    if board.turn_phase != TurnPhase.MUST_DISCARD:
        msg = "after_kan_rinshan expects MUST_DISCARD (post-meld totals)"
        raise ValueError(msg)
    if seat != board.current_seat:
        msg = "rinshan draw seat must equal current_seat"
        raise ValueError(msg)
    if board.rinshan_draw_index >= RINSHAN_COUNT:
        msg = "rinshan exhausted"
        raise ValueError(msg)
    if board.last_draw_was_rinshan:
        msg = "cannot chain rinshan draw without discarding"
        raise ValueError(msg)
    tile = board.dead_wall.rinshan[board.rinshan_draw_index]
    new_hands = list(board.hands)
    new_hands[seat] = add_tile(new_hands[seat], tile)
    new_rin_idx = board.rinshan_draw_index + 1
    k = len(board.revealed_indicators)
    if k >= INDICATOR_COUNT:
        msg = "no more dora indicators to reveal"
        raise ValueError(msg)
    next_indicator = board.dead_wall.indicators[k]
    new_revealed = board.revealed_indicators + (next_indicator,)
    return BoardState(
        hands=tuple(new_hands),
        live_wall=board.live_wall,
        live_draw_index=board.live_draw_index,
        dead_wall=board.dead_wall,
        revealed_indicators=new_revealed,
        current_seat=seat,
        turn_phase=TurnPhase.MUST_DISCARD,
        river=board.river,
        melds=board.melds,
        last_draw_tile=tile,
        last_draw_was_rinshan=True,
        rinshan_draw_index=new_rin_idx,
        call_state=None,
        riichi=board.riichi,
        ippatsu_eligible=board.ippatsu_eligible,
        double_riichi=board.double_riichi,
        all_discards_per_seat=board.all_discards_per_seat,
        called_discard_indices=board.called_discard_indices,
    )
