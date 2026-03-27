"""
大模型侧：HTTP 适配、提示拼装、解析校验与跑局编排。

牌桌规则仅存在于 ``kernel``；本包通过 ``legal_actions`` / ``observation`` / ``apply`` 接入。
"""

from llm.config import LLMClientConfig, load_llm_config
from llm.protocol import ChatMessage, CompletionClient, build_client
from llm.runner import RunResult, run_llm_match

__all__ = [
    "LLMClientConfig",
    "ChatMessage",
    "CompletionClient",
    "RunResult",
    "build_client",
    "load_llm_config",
    "run_llm_match",
]
