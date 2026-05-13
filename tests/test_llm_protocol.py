"""llm.protocol 覆盖缺口测试。"""

from __future__ import annotations

from llm.protocol import build_client, build_seat_clients


def _cfg(provider="openai", api_key="test-key"):
    from llm.config import LLMClientConfig
    return LLMClientConfig(
        provider=provider, api_key=api_key, base_url="http://test",
        model="test-model", timeout_sec=30, max_context=4096, max_tokens=1024,
        system_prompt="test", prompt_format="natural", context_scope="per_hand",
        compression_level="none", history_budget=2000, context_compression_threshold=0.8,
    )


class TestBuildClient:
    """build_client 各 provider 分支。"""

    def test_openai_provider(self, monkeypatch) -> None:
        """provider='openai' 应构造 OpenAIChatClient。"""
        constructed = []

        class FakeOpenAI:
            def __init__(self, cfg):
                constructed.append(("openai", cfg))

        monkeypatch.setattr("llm.adapters.openai_chat.OpenAIChatClient", FakeOpenAI)
        client = build_client(_cfg("openai"))
        assert constructed[0][0] == "openai"

    def test_anthropic_provider(self, monkeypatch) -> None:
        """默认 provider 应构造 AnthropicMessagesClient。"""
        constructed = []

        class FakeAnthropic:
            def __init__(self, cfg):
                constructed.append(("anthropic", cfg))

        monkeypatch.setattr("llm.adapters.anthropic_messages.AnthropicMessagesClient", FakeAnthropic)
        client = build_client(_cfg("anthropic"))
        assert constructed[0][0] == "anthropic"


class TestBuildSeatClients:
    """build_seat_clients 错误守卫。"""

    def test_missing_api_key_raises(self) -> None:
        try:
            build_seat_clients({0: _cfg(api_key="")})
            raise AssertionError("expected ValueError for missing API key")
        except ValueError:
            pass
