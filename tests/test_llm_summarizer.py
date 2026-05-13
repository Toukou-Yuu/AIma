"""llm.agent.llm_summarizer 覆盖缺口测试（0% → 100%）。"""

from __future__ import annotations

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


# --- 真实 DeepSeek API 调用 ---

class TestPolishWithDeepSeek:
    def test_polish_returns_memory(self) -> None:
        """真实 DeepSeek 调用 polish() 应返回 PlayerMemory。"""
        from llm.config import LLMClientConfig
        from llm.protocol import build_client

        cfg = LLMClientConfig(
            provider="openai",
            api_key="sk-467c7001b0024712b3c004b1c956e7dd",
            base_url="https://api.deepseek.com/",
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
