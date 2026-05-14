"""对局状态机壳与 ``apply`` 入口；具体行牌见后续模块。"""

from kernel.engine.actions import Action, ActionKind
from kernel.engine.apply import ApplyOutcome, EngineError, IllegalActionError, apply
from kernel.engine.events import EventBuilder
from kernel.engine.flow import (
    advance_after_flow,
    apply_flow_transition,
    apply_three_ron_flow,
    count_kans_per_seat,
    detect_flow_after_kan,
    detect_flow_after_riichi,
    detect_flow_exhausted,
)
from kernel.engine.phase import GamePhase
from kernel.engine.settlement import settle_ron, settle_tsumo
from kernel.engine.state import GameState, initial_game_state

__all__ = [
    "Action",
    "ActionKind",
    "ApplyOutcome",
    "EngineError",
    "EventBuilder",
    "GamePhase",
    "GameState",
    "IllegalActionError",
    "apply",
    "initial_game_state",
    # 新增导出
    "advance_after_flow",
    "apply_flow_transition",
    "apply_three_ron_flow",
    "count_kans_per_seat",
    "detect_flow_after_kan",
    "detect_flow_after_riichi",
    "detect_flow_exhausted",
    "settle_ron",
    "settle_tsumo",
]
