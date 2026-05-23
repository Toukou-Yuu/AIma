"""llm.agent.llm_summarizer 覆盖缺口测试（0% → 100%）。

H-26: 移除硬编码 API Key，使用环境变量。
"""

from __future__ import annotations

import os

import pytest

from llm.agent.llm_summarizer import LLMSummarizer, create_summarizer
from llm.agent.memory import EpisodeStats, PlayerMemory


def _memory() -> PlayerMemory:
    return PlayerMemory(
        play_bias="neutral",
        recent_patterns=["旧建议1"],
        total_games=5,
        last_updated="2026-01-01",
    )


def _stats() -> EpisodeStats:
    return EpisodeStats(
        player_id="test", seat=0,
        wins=3, deal_ins=1, riichi_count=2, riichi_win=1, riichi_deal_in=0,
    )


# --- client=None 路径 ---

class TestPolishClientNone:
    def test_returns_unchanged(self) -> None:
        """client=None 时直接返回原 memory（L21-22）。"""
        s = LLMSummarizer(client=None)
        mem = _memory()
        result = s.polish(mem, _stats())
        assert result is mem


# --- _build_polish_prompt ---

class TestBuildPolishPrompt:
    def test_contains_stats(self) -> None:
        s = LLMSummarizer()
        prompt = s._build_polish_prompt(_memory(), _stats())
        assert "和了" in prompt
        assert "放铳" in prompt
        assert "立直" in prompt
        assert "neutral" in prompt


# --- _parse_response ---

class TestParseResponse:
    def test_normal(self) -> None:
        s = LLMSummarizer()
        result = s._parse_response("建议1\n建议2\n建议3")
        assert len(result) == 3
        assert result[0] == "建议1"

    def test_empty(self) -> None:
        s = LLMSummarizer()
        result = s._parse_response("")
        assert result == []

    def test_max_5(self) -> None:
        s = LLMSummarizer()
        result = s._parse_response("a\nb\nc\nd\ne\nf\ng")
        assert len(result) == 5

    def test_strips_whitespace(self) -> None:
        s = LLMSummarizer()
        result = s._parse_response("  建议1  \n\n  建议2  \n")
        assert result == ["建议1", "建议2"]


# --- create_summarizer ---

class TestCreateSummarizer:
    def test_without_llm(self) -> None:
        result = create_summarizer(use_llm=False)
        assert not isinstance(result, LLMSummarizer)

    def test_with_llm_and_client(self) -> None:
        class FakeClient:
            def complete(self, messages, *, model=None):
                return "ok"

        result = create_summarizer(use_llm=True, client=FakeClient())
        assert isinstance(result, LLMSummarizer)

    def test_with_llm_no_client(self) -> None:
        """use_llm=True 但 client=None → 回退到 EpisodeSummarizer。"""
        result = create_summarizer(use_llm=True, client=None)
        assert not isinstance(result, LLMSummarizer)


# --- exception 回退路径 ---

class TestPolishExceptionFallback:
    def test_client_raises_returns_original(self) -> None:
        """client 抛异常时回退到原 memory（L46-48）。"""
        class BadClient:
            def complete(self, messages, *, model=None):
                raise RuntimeError("API error")

        s = LLMSummarizer(client=BadClient())
        mem = _memory()
        result = s.polish(mem, _stats())
        assert result is mem


# --- 真实 DeepSeek API 调用 ---

class TestPolishWithDeepSeek:
    pytestmark = pytest.mark.skipif(
        os.environ.get("RUN_LIVE_LLM_TESTS") != "1",
        reason="H-26: 需真实 API 调用，设置 RUN_LIVE_LLM_TESTS=1 运行",
    )

    def test_polish_returns_memory(self) -> None:
        """真实 DeepSeek 调用 polish() 应返回 PlayerMemory。

        H-26: API Key 从环境变量获取，不再硬编码。
        """
        from llm.config import LLMClientConfig
        from llm.protocol import build_client

        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            pytest.skip("H-26: 需设置 DEEPSEEK_API_KEY 环境变量")

        cfg = LLMClientConfig(
            provider="openai",
            api_key=api_key,  # H-26: 使用环境变量
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/"),
            model="deepseek-v4-flash",
            timeout_sec=30,
            max_context=4096,
            max_tokens=256,
            system_prompt="test",
            prompt_format="natural",
            context_scope="per_hand",
            compression_level="none",
            history_budget=2000,
            context_compression_threshold=0.8,
        )
        client = build_client(cfg)
        s = LLMSummarizer(client=client)
        mem = _memory()
        result = s.polish(mem, _stats())
        assert isinstance(result, PlayerMemory)
        assert result.play_bias == mem.play_bias
        assert result.total_games == mem.total_games
