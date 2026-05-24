"""
Arena module: game engine, match runner, policy protocol.
"""

from arena.engine import GameEngine
from arena.result import EngineStepResult
from arena.errors import IllegalPolicyDecisionError
from arena.match_result import MatchResult
from arena.match_runner import MatchRunner
from arena.policy import DecisionContext, PolicyDecision, Policy
from arena.sinks import EventSink, NullSink, InMemorySink

__all__: list[str] = [
    "GameEngine",
    "EngineStepResult",
    "IllegalPolicyDecisionError",
    "MatchResult",
    "MatchRunner",
    "DecisionContext",
    "PolicyDecision",
    "Policy",
    "EventSink",
    "NullSink",
    "InMemorySink",
]
