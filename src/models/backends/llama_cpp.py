"""llama.cpp backend stub for v4.0.

This backend is not yet implemented. Use openai_compatible backend with
llama.cpp's OpenAI-compatible server instead.
"""

from __future__ import annotations

from models.schema import ModelSpec


class LlamaCppBackend:
    """llama.cpp native backend (stub).

    v4.0 Status: Not implemented. Planned for future release.

    For llama.cpp models, use the openai_compatible backend with llama.cpp's
    built-in OpenAI-compatible HTTP server:

        # Start llama.cpp server
        llama-server -m model.gguf --port 8080

        # Configure in ModelSpec:
        backend = "openai_compatible"
        endpoint = "http://localhost:8080/v1"
        model_name = "local"
    """

    def __init__(self, spec: ModelSpec) -> None:
        """Initialize backend with model specification.

        Args:
            spec: Model configuration including model_path and other settings.
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
            "llama.cpp native backend is not implemented in v4.0. "
            "Use openai_compatible backend with llama.cpp's OpenAI-compatible server:\n"
            "  1. Start llama.cpp: llama-server -m model.gguf --port 8080\n"
            "  2. Configure ModelSpec:\n"
            "     backend = 'openai_compatible'\n"
            "     endpoint = 'http://localhost:8080/v1'\n"
            "     model_name = 'local'"
        )