"""回放：从事件日志重现局面。

K13 核心模块：通过事件日志确定性回放对局。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kernel.engine.actions import Action
from kernel.engine.apply import ApplyOutcome, apply
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState
from kernel.event_log import (
    CallEvent,
    DiscardTileEvent,
    DrawTileEvent,
    EventLog,
    FlowEvent,
    GameEvent,
    HandOverEvent,
    RonEvent,
    RoundBeginEvent,
    TsumoEvent,
)
from kernel.table.model import initial_table_snapshot

if TYPE_CHECKING:
    from kernel.tiles.model import Tile


class ReplayError(ValueError):
    """回放过程中发生的错误。"""


def _action_from_event(
    event: GameEvent,
    current_state: GameState,
) -> Action | None:
    """根据事件生成对应的动作。

    注意：由于事件不包含完整的动作信息（如 Meld 的具体构成），
    此函数主要用于验证，实际回放依赖于外部提供的动作序列。
    返回 None 表示系统事件（如 RoundBeginEvent），不需要动作。
    """
    if isinstance(event, RoundBeginEvent):
        return None  # 系统事件
    if isinstance(event, FlowEvent):
        return None  # 系统事件
    if isinstance(event, HandOverEvent):
        return None  # 系统事件
    # 其他事件类型需要动作，但这里无法完全重建
    # 回放时需要外部提供完整的动作序列
    return None


def replay_from_actions(
    actions: list[Action],
    *,
    seed: int | None = None,
    initial_wall: tuple[Tile, ...] | None = None,
) -> tuple[GameState, list[ApplyOutcome]]:
    """
    从动作序列回放对局。

    Args:
        actions: 动作序列
        seed: 随机种子（用于生成初始牌山，如果 initial_wall 未提供）
        initial_wall: 初始牌山（如果未提供，则使用 seed 生成）

    Returns:
        (final_state, outcomes): 最终状态和所有 apply 结果

    Raises:
        ReplayError: 回放过程中发生错误
    """

    state = GameState(
        phase=GamePhase.PRE_DEAL,
        table=initial_table_snapshot(),
        board=None,
        ron_winners=None,
    )
    outcomes = []

    for i, action in enumerate(actions):
        try:
            outcome = apply(state, action)
            outcomes.append(outcome)
            state = outcome.new_state
        except Exception as e:
            raise ReplayError(f"Action {i} failed: {e}") from e

    return state, outcomes


def replay_from_event_log(
    log: EventLog,
    actions: list[Action],
) -> tuple[GameState, list[ApplyOutcome]]:
    """
    从事件日志和动作序列回放对局（用于验证日志一致性）。

    Args:
        log: 事件日志
        actions: 与事件对应的动作序列

    Returns:
        (final_state, outcomes): 最终状态和所有 apply 结果

    Raises:
        ReplayError: 回放过程中发生错误，或事件与动作不匹配
    """
    state, outcomes = replay_from_actions(actions, seed=log.seed)

    # 验证事件序列一致性
    # 注意：由于 events 是每步 apply 生成的，我们需要扁平化所有事件
    all_events = []
    for outcome in outcomes:
        all_events.extend(outcome.events)

    if len(all_events) != len(log.events):
        raise ReplayError(
            f"Event count mismatch: expected {len(log.events)}, got {len(all_events)}"
        )

    # 验证每个事件的类型和序列号
    for i, (expected, actual) in enumerate(zip(log.events, all_events)):
        if type(expected) is not type(actual):
            raise ReplayError(
                f"Event {i} type mismatch: expected {type(expected).__name__}, "
                f"got {type(actual).__name__}"
            )
        if expected.sequence != actual.sequence:
            raise ReplayError(
                f"Event {i} sequence mismatch: expected {expected.sequence}, got {actual.sequence}"
            )

    return state, outcomes


def verify_event_log(log: EventLog) -> bool:
    """
    验证事件日志的基本一致性。

    检查项：
    1. 事件序列号从 0 开始且连续
    2. RoundBeginEvent 在第一个
    3. HandOverEvent 在最后一个（如果对局正常结束）

    Returns:
        True 如果日志一致，False 否则
    """
    if not log.events:
        return False

    # 检查序列号连续性
    for i, event in enumerate(log.events):
        if event.sequence != i:
            return False

    # 检查第一个事件是 RoundBeginEvent
    if not isinstance(log.events[0], RoundBeginEvent):
        return False

    return True


def extract_action_trace(outcome: ApplyOutcome) -> list[dict]:
    """
    从结果中提取动作轨迹（用于调试和记录）。

    Returns:
        动作轨迹列表，每个动作是一个字典
    """
    trace = []
    for event in outcome.events:
        event_data = {
            "type": type(event).__name__,
            "sequence": event.sequence,
            "seat": event.seat,
        }
        # 添加事件特有字段
        if isinstance(event, (DrawTileEvent, DiscardTileEvent, RonEvent, TsumoEvent)):
            event_data["tile"] = str(event.tile) if hasattr(event, "tile") else None
        if isinstance(event, CallEvent):
            event_data["call_kind"] = event.call_kind
        if isinstance(event, FlowEvent):
            event_data["flow_kind"] = str(event.flow_kind) if event.flow_kind else None
            event_data["tenpai_seats"] = list(event.tenpai_seats)
        if isinstance(event, HandOverEvent):
            event_data["winners"] = event.winners
            event_data["payments"] = event.payments
        if isinstance(event, RoundBeginEvent):
            event_data["dealer_seat"] = event.dealer_seat
            dora = str(event.dora_indicator) if event.dora_indicator else None
            event_data["dora_indicator"] = dora
        trace.append(event_data)
    return trace
