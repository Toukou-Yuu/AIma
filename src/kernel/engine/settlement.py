"""和了结算逻辑：荣和与自摸结算。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kernel.call import board_after_ron_winners
from kernel.event_log import GameEvent, WinSettlementLine
from kernel.flow.settle import update_honba
from kernel.scoring.dora import ura_indicators_for_settlement
from kernel.scoring.settle import settle_ron_table, settle_tsumo_table
from kernel.table.model import TableSnapshot

if TYPE_CHECKING:
    from kernel.board import BoardState
    from kernel.engine.events import EventBuilder


def settle_ron(
    table: TableSnapshot,
    board: BoardState,
    ron_winners: frozenset[int],
    discard_seat: int,
    win_tile: "Tile",
    is_chankan: bool,
    dealer_seat: int,
    event_builder: "EventBuilder",
) -> tuple[TableSnapshot, BoardState, tuple[GameEvent, ...]]:
    """
    结算荣和。

    返回 (new_table, settled_board, events)。
    events 包含 RonEvent 列表和 HandOverEvent。
    """
    settled = board_after_ron_winners(board)
    ura = ura_indicators_for_settlement(
        board.dead_wall,
        len(board.revealed_indicators),
    )

    # 连庄判定：亲家和了则连庄（一炮多响时任一亲家和了即连庄）
    continue_dealer = any(w == dealer_seat for w in ron_winners)
    new_table, win_lines, payments = settle_ron_table(
        table,
        board,
        ron_winners=ron_winners,
        discard_seat=discard_seat,
        win_tile=win_tile,
        ura_indicators=ura,
        is_chankan=is_chankan,
    )
    new_table = update_honba(new_table, continue_dealer=continue_dealer)

    # 生成 RonEvent 和 HandOverEvent
    events: list[GameEvent] = []
    for winner in ron_winners:
        ron_event = event_builder.ron(
            seat=winner,
            win_tile=win_tile,
            discard_seat=discard_seat,
        )
        events.append(ron_event)
    hand_over_event = event_builder.hand_over(
        winners=tuple(ron_winners),
        payments=payments,
        win_lines=win_lines,
    )
    events.append(hand_over_event)

    return new_table, settled, tuple(events)


def settle_tsumo(
    table: TableSnapshot,
    board: BoardState,
    winner: int,
    win_tile: "Tile",
    is_rinshan: bool,
    dealer_seat: int,
    event_builder: "EventBuilder",
) -> tuple[TableSnapshot, BoardState, tuple[GameEvent, ...]]:
    """
    结算自摸。

    返回 (new_table, settled_board, events)。
    events 包含 TsumoEvent 和 HandOverEvent。
    """
    from kernel.play import board_after_tsumo_win  # 延迟导入避免循环

    settled = board_after_tsumo_win(board, winner=winner, win_tile=win_tile)
    ura = ura_indicators_for_settlement(
        board.dead_wall,
        len(board.revealed_indicators),
    )

    # 连庄判定：亲家自摸则连庄
    continue_dealer = winner == dealer_seat
    new_table, win_lines, payments = settle_tsumo_table(
        table,
        board,
        winner=winner,
        win_tile=win_tile,
        ura_indicators=ura,
    )
    new_table = update_honba(new_table, continue_dealer=continue_dealer)

    # 生成 TsumoEvent 和 HandOverEvent
    tsumo_event = event_builder.tsumo(
        seat=winner,
        win_tile=win_tile,
        is_rinshan=is_rinshan,
    )
    hand_over_event = event_builder.hand_over(
        winners=(winner,),
        payments=payments,
        win_lines=win_lines,
    )

    return new_table, settled, (tsumo_event, hand_over_event)