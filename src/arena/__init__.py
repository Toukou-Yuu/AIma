"""
Arena module: game engine, match runner, policy protocol.
"""

from arena.engine import GameEngine
from arena.result import EngineStepResult

__all__: list[str] = ["GameEngine", "EngineStepResult"]
