"""
Arena module: game engine, match runner, policy protocol.
"""

from arena.engine import GameEngine
from arena.result import EngineStepResult
from arena.errors import IllegalPolicyDecisionError
from arena.hand_result import HandResult
from arena.match_result import MatchResult
from arena.match_runner import MatchRunner
from arena.memory_sink import MemorySink
from arena.policy import DecisionContext, PolicyDecision, Policy
from arena.sinks import EventSink, NullSink, InMemorySink

__all__: list[str] = [
    "GameEngine",
    "EngineStepResult",
    "IllegalPolicyDecisionError",
    "HandResult",
    "MatchResult",
    "MatchRunner",
    "MemorySink",
    "DecisionContext",
    "PolicyDecision",
    "Policy",
    "EventSink",
    "NullSink",
    "InMemorySink",
]
