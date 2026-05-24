"""Context module: context builders, compression, token budget."""

from context.builders import BuiltContext, ContextBuilder
from context.compression import CompressionEngine, CompressionMode, CompressionResult
from context.event_projector import EventFilterConfig, EventProjector, EventScope
from context.schema import ContextSpec
from context.token_budget import TokenBudgetConfig, TokenBudgetManager, TruncationResult

__all__ = [
    # Builder
    "ContextBuilder",
    "BuiltContext",
    # Schema
    "ContextSpec",
    # Event projection
    "EventProjector",
    "EventFilterConfig",
    "EventScope",
    # Compression
    "CompressionEngine",
    "CompressionMode",
    "CompressionResult",
    # Token budget
    "TokenBudgetManager",
    "TokenBudgetConfig",
    "TruncationResult",
]
