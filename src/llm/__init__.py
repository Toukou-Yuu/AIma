"""
大模型侧：HTTP 适配、提示拼装、解析校验与跑局编排。

牌桌规则仅存在于 ``kernel``；本包通过 ``legal_actions`` / ``observation`` / ``apply`` 接入。
"""

from llm.agent import PlayerAgent
from llm.config import (
    LLMClientConfig,
    LLMProfileConfig,
    MatchConfig,
    SeatLLMBinding,
    load_llm_config,
    load_llm_profiles,
    load_match_config,
    load_seat_llm_bindings,
    load_seat_llm_configs,
)
from llm.protocol import ChatMessage, CompletionClient, build_client, build_seat_clients
from llm.runner import RunResult, run_llm_match

__all__ = [
    "LLMClientConfig",
    "LLMProfileConfig",
    "MatchConfig",
    "SeatLLMBinding",
    "ChatMessage",
    "CompletionClient",
    "PlayerAgent",
    "RunResult",
    "build_client",
    "build_seat_clients",
    "load_llm_config",
    "load_llm_profiles",
    "load_match_config",
    "load_seat_llm_bindings",
    "load_seat_llm_configs",
    "run_llm_match",
]
