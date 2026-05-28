"""Models module: ModelBackend protocol and implementations."""

from models.registry import build_backend
from models.schema import ModelSpec

__all__ = ["ModelSpec", "build_backend"]
