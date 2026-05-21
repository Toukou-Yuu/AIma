"""流局处理逻辑：四家立直、荒牌、四杠、三家和了流局。"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from kernel.board import BoardState
from kernel.engine.events import EventBuilder
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState
from kernel.flow import FlowKind, FlowResult, check_flow_kind, settle_flow
from kernel.hand.melds import MeldKind
from kernel.table.model import TableSnapshot
from kernel.table.transitions import advance_round, final_settlement, should_match_end

if TYPE_CHECKING:
    from kernel.tiles.model import Tile


_KAN_KINDS = frozenset({MeldKind.ANKAN, MeldKind.DAIMINKAN, MeldKind.KAKAN})


def count_kans_per_seat(board: BoardState) -> tuple[int, int, int, int]:
    """统计每家的杠数（暗杠 + 大明杠 + 加杠）。"""
    return tuple(
        sum(1 for m in seat_melds if m.kind in _KAN_KINDS)
        for seat_melds in board.melds
    )


def detect_flow_after_riichi(
    board: BoardState,
    riichi_state: tuple[bool, bool, bool, bool],
) -> FlowResult | None:
    """
    检测四家立直流局。

    在立直宣言后检测。返回 FlowResult 或 None。
    """
    return check_flow_kind(board, riichi_state=riichi_state)


def detect_flow_after_kan(board: BoardState) -> FlowResult | None:
    """
    检测四杠流局。

    在开杠后检测。返回 FlowResult 或 None。
    """
    kan_counts = count_kans_per_seat(board)
    return check_flow_kind(board, kan_counts=kan_counts)


def detect_flow_exhausted(board: BoardState) -> FlowResult | None:
    """
    检测荒牌流局。

    在弃牌后检测。返回 FlowResult 或 None。
    """
    return check_flow_kind(board, riichi_state=tuple(board.riichi))


def detect_flow_four_winds(board: BoardState) -> FlowResult | None:
    """
    检测四风连打流局。

    条件：
    - 首巡（每家恰好 1 张舍牌）
    - 无副露（所有 melds 为空）
    - 前 4 张舍牌为相同风牌（东/南/西/北）

    在 NEED_DRAW 阶段摸牌前检测。返回 FlowResult 或 None。
    """
    # 检查首巡：每家恰好 1 张舍牌
    for seat_discards in board.all_discards_per_seat:
        if len(seat_discards) != 1:
            return None

    # 检查无副露
    for seat_melds in board.melds:
        if len(seat_melds) > 0:
            return None

    # 按座位顺序收集前 4 张舍牌
    first_4_river = [board.all_discards_per_seat[s][0] for s in range(4)]

    return check_flow_kind(board, first_4_river=first_4_river)


def apply_flow_transition(
    state: GameState,
    flow_result: FlowResult,
    event_builder: EventBuilder,
) -> tuple[GameState, GameEvent]:
    """
    应用流局转换：更新状态到 FLOWN，生成 FlowEvent。

    返回 (new_state, flow_event)。
    """
    new_table, tenpai_result = settle_flow(state.table, state.board)
    flow_event = event_builder.flow(
        flow_kind=flow_result.kind,
        tenpai_seats=tenpai_result.tenpai_seats if tenpai_result else frozenset(),
    )

    new_state = GameState(
        phase=GamePhase.FLOWN,
        table=new_table,
        board=state.board,
        flow_result=flow_result,
        tenpai_result=tenpai_result,
        ron_winners=None,
        event_sequence=event_builder._sequence,
    )
    return new_state, flow_event


def apply_three_ron_flow(
    board: "BoardState",
    table: "TableSnapshot",
    ron_claimants: frozenset[int],
    event_builder: EventBuilder,
) -> GameState:
    """
    应用三家和了流局。

    返回新的 FLOWN 状态。
    """
    from kernel.call import board_after_ron_winners  # 延迟导入避免循环
    from kernel.table.model import TableSnapshot

    settled = board_after_ron_winners(board)
    flow_result = FlowResult(
        kind=FlowKind.THREE_RON,
        ron_claimants=ron_claimants,
    )
    new_state = GameState(
        phase=GamePhase.FLOWN,
        table=table,
        board=settled,
        flow_result=flow_result,
        tenpai_result=None,
        ron_winners=None,
        event_sequence=event_builder._sequence,
    )
    return new_state


def advance_after_flow(
    table: TableSnapshot,
    tenpai_result,
    dealer_seat: int,
    wall: list["Tile"],
    event_builder: EventBuilder,
) -> tuple[GameState, tuple[GameEvent, ...]]:
    """
    流局后推进到下一局或终局。

    返回 (new_state, events)。
    """
    from kernel.deal import assert_wall_is_standard_deck, build_board_after_split
    from kernel.wall.split import split_wall as deal_split_wall

    # 先判断是否连庄（亲家听牌）
    continue_dealer = tenpai_result is not None and dealer_seat in tenpai_result.tenpai_seats

    if continue_dealer:
        # 连庄：不判断终局，直接推进
        new_table = advance_round(table, continue_dealer=True)
    elif should_match_end(table):
        # 亲流 + 终局条件满足：终局
        ranking, final_table = final_settlement(table)
        end_ev = event_builder.match_end(
            ranking=ranking,
            final_scores=final_table.scores,
        )
        return GameState(
            phase=GamePhase.MATCH_END,
            table=final_table,
            board=None,
            ron_winners=None,
            flow_result=None,
            tenpai_result=tenpai_result,
            event_sequence=event_builder._sequence,
        ), (end_ev,)
    else:
        # 亲流但未达终局条件：推进下一局
        new_table = advance_round(table, continue_dealer=False)

    # 重新开局配牌
    if wall is None:
        msg = "NEXT_ROUND requires wall"
        raise ValueError(msg)
    try:
        assert_wall_is_standard_deck(wall)
    except ValueError as e:
        raise ValueError(str(e)) from e
    try:
        split = deal_split_wall(wall)
        board = build_board_after_split(split, new_table.dealer_seat)
    except ValueError as e:
        raise ValueError(str(e)) from e

    # 生成新局的 RoundBeginEvent
    dora_ind = board.revealed_indicators[0] if board.revealed_indicators else None
    seeds = tuple(s * 13 for s in range(4))
    round_begin_event = event_builder.round_begin(
        dealer_seat=new_table.dealer_seat,
        dora_indicator=dora_ind,
        seeds=seeds,
    )

    return GameState(
        phase=GamePhase.IN_ROUND,
        table=new_table,
        board=board,
        ron_winners=None,
        flow_result=None,
        tenpai_result=None,
        event_sequence=event_builder._sequence,
    ), (round_begin_event,)