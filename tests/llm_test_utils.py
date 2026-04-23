"""LLM tests shared runtime configuration helpers."""

from __future__ import annotations

from pathlib import Path

from llm.agent import PlayerAgent
from llm.config import LLMRuntimeConfig, load_llm_runtime_config

_TEST_RUNTIME_PATH = Path("tests/fixtures/llm_runtime.yaml")


def load_test_runtime_config() -> LLMRuntimeConfig:
    """Load runtime config from file so tests do not embed hard-coded defaults."""
    return load_llm_runtime_config(config_path=_TEST_RUNTIME_PATH)


def build_test_agent(
    *,
    system_prompt: str | None = None,
    context_scope: str | None = None,
    prompt_mode: str | None = None,
) -> PlayerAgent:
    """Construct a PlayerAgent using test config-file runtime values."""
    runtime = load_test_runtime_config()
    effective_scope = runtime.context_scope if context_scope is None else context_scope
    effective_prompt_mode = runtime.prompt_format if prompt_mode is None else prompt_mode
    return PlayerAgent(
        history_budget=runtime.history_budget,
        system_prompt=system_prompt,
        prompt_mode=effective_prompt_mode,
        compression_level=runtime.compression_level,
        context_scope=effective_scope,
        context_budget_tokens=runtime.context_budget_tokens,
        reserved_output_tokens=runtime.reserved_output_tokens,
        safety_margin_tokens=runtime.safety_margin_tokens,
    )
