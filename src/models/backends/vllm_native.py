"""vLLM native backend stub for v4.0.

This backend is not yet implemented. Use openai_compatible backend with
vLLM's OpenAI-compatible endpoint instead.
"""

from __future__ import annotations

from models.schema import ModelSpec


class VllmNativeBackend:
    """vLLM native backend (stub).

    v4.0 Status: Not implemented. Planned for future release.

    For vLLM models, use the openai_compatible backend with vLLM's
    built-in OpenAI-compatible API server:

        # Start vLLM server
        vllm serve model_name --port 8000

        # Configure in ModelSpec:
        backend = "openai_compatible"
        endpoint = "http://localhost:8000/v1"
        model_name = "model_name"
    """

    def __init__(self, spec: ModelSpec) -> None:
        """Initialize backend with model specification.

        Args:
            spec: Model configuration including endpoint and other settings.
        """
        self.spec = spec

    def complete(
        self,
        messages: list,  # list[ChatMessage] - avoid circular import
        *,
        model: str | None = None,
    ) -> str:
        """Not implemented - raises NotImplementedError.

        Args:
            messages: Chat messages for completion.
            model: Optional model name override.

        Raises:
            NotImplementedError: Always - use openai_compatible backend instead.
        """
        raise NotImplementedError(
            "vLLM native backend is not implemented in v4.0. "
            "Use openai_compatible backend with vLLM's OpenAI-compatible server:\n"
            "  1. Start vLLM: vllm serve model_name --port 8000\n"
            "  2. Configure ModelSpec:\n"
            "     backend = 'openai_compatible'\n"
            "     endpoint = 'http://localhost:8000/v1'\n"
            "     model_name = 'model_name'"
        )