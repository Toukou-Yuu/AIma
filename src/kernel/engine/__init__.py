"""对局状态机壳与 ``apply`` 入口；具体行牌见后续模块。"""

from kernel.engine.actions import Action, ActionKind
from kernel.engine.apply import ApplyOutcome, EngineError, IllegalActionError, apply
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState, initial_game_state

__all__ = [
    "Action",
    "ActionKind",
    "ApplyOutcome",
    "EngineError",
    "GamePhase",
    "GameState",
    "IllegalActionError",
    "apply",
    "initial_game_state",
]
