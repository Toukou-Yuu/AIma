"""Backend factory registry.

Maps backend type strings to backend classes.
"""

from __future__ import annotations

# Backend type: "openai_compatible" | "llama_cpp" | "vllm_native" | "mock" | "dummy"

from models.backend import CompletionClient
from models.schema import ModelSpec


def build_backend(spec: ModelSpec) -> CompletionClient:
    """Build a backend instance from ModelSpec.

    Args:
        spec: Model specification containing backend type and config

    Returns:
        CompletionClient instance for the specified backend

    Raises:
        ValueError: If backend type is not supported
    """
    backend_type = spec.backend

    if backend_type == "dummy":
        from models.backends.dummy import DummyBackend

        return DummyBackend(spec)

    if backend_type == "mock":
        from models.backends.mock import MockBackend

        responses = spec.extra.get("responses", {})
        return MockBackend(spec, responses=responses)

    if backend_type == "openai_compatible":
        from models.backends.openai_compatible import OpenAICompatibleBackend

        return OpenAICompatibleBackend(spec)

    if backend_type == "llama_cpp":
        msg = (
            "llama.cpp native backend is not implemented in v4.0. "
            "Use openai_compatible backend with llama.cpp's OpenAI-compatible server:\n"
            "  1. Start llama.cpp: llama-server -m model.gguf --port 8080\n"
            "  2. Configure ModelSpec:\n"
            "     backend = 'openai_compatible'\n"
            "     endpoint = 'http://localhost:8080/v1'\n"
            "     model_name = 'local'"
        )
        raise ValueError(msg)

    if backend_type == "vllm_native":
        msg = (
            "vLLM native backend is not implemented in v4.0. "
            "Use openai_compatible backend with vLLM's OpenAI-compatible server:\n"
            "  1. Start vLLM: vllm serve model_name --port 8000\n"
            "  2. Configure ModelSpec:\n"
            "     backend = 'openai_compatible'\n"
            "     endpoint = 'http://localhost:8000/v1'\n"
            "     model_name = 'model_name'"
        )
        raise ValueError(msg)

    if backend_type == "replay":
        if spec.extra.get("replay_path"):
            from models.backends.replay import ReplayBackend

            return ReplayBackend(spec)
        msg = (
            f"Backend type 'replay' is not implemented in v4.0. "
            f"Use 'mock' backend with configured responses instead."
        )
        raise ValueError(msg)

    msg = (
        f"Unknown backend type: {backend_type!r}. "
        f"Supported types: dummy, mock, openai_compatible, llama_cpp, vllm_native"
    )
    raise ValueError(msg)
