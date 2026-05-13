"""llm.adapters 覆盖缺口测试。

覆盖 AnthropicMessagesClient 与 OpenAIChatClient 的构造验证、请求构建与响应解析。
使用 monkeypatch 模拟 httpx.Client。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from llm.config import LLMClientConfig
from llm.protocol import ChatMessage


def _make_cfg(provider: str = "anthropic") -> LLMClientConfig:
    return LLMClientConfig(
        provider=provider,
        base_url="https://api.example.com",
        api_key="test-key",
        model="test-model",
        timeout_sec=30.0,
        max_context=8000,
        max_tokens=1000,
        system_prompt="test system prompt",
        prompt_format="natural",
        context_scope="per_hand",
        compression_level="snip",
        history_budget=5,
        context_compression_threshold=0.8,
    )


# --- AnthropicMessagesClient ---

class TestAnthropicMessagesClient:
    def test_wrong_provider_raises(self) -> None:
        from llm.adapters.anthropic_messages import AnthropicMessagesClient
        cfg = _make_cfg(provider="openai")
        with pytest.raises(ValueError, match="anthropic"):
            AnthropicMessagesClient(cfg)

    def test_constructor_sets_url(self) -> None:
        from llm.adapters.anthropic_messages import AnthropicMessagesClient
        cfg = _make_cfg("anthropic")
        client = AnthropicMessagesClient(cfg)
        assert client._url == "https://api.example.com/v1/messages"

    def test_complete_basic(self, monkeypatch) -> None:
        from llm.adapters.anthropic_messages import AnthropicMessagesClient
        cfg = _make_cfg("anthropic")
        client = AnthropicMessagesClient(cfg)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "hello"}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("httpx.Client", lambda **kwargs: mock_client)

        messages = [ChatMessage(role="user", content="test")]
        result = client.complete(messages)
        assert result == "hello"

    def test_complete_with_system_message(self, monkeypatch) -> None:
        from llm.adapters.anthropic_messages import AnthropicMessagesClient
        cfg = _make_cfg("anthropic")
        client = AnthropicMessagesClient(cfg)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "response"}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("httpx.Client", lambda **kwargs: mock_client)

        messages = [
            ChatMessage(role="system", content="sys"),
            ChatMessage(role="user", content="hello"),
            ChatMessage(role="assistant", content="hi"),
        ]
        result = client.complete(messages)
        assert result == "response"
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "system" in payload

    def test_complete_multiple_text_blocks(self, monkeypatch) -> None:
        from llm.adapters.anthropic_messages import AnthropicMessagesClient
        cfg = _make_cfg("anthropic")
        client = AnthropicMessagesClient(cfg)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [
                {"type": "text", "text": "hello "},
                {"type": "text", "text": "world"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("httpx.Client", lambda **kwargs: mock_client)

        messages = [ChatMessage(role="user", content="test")]
        result = client.complete(messages)
        assert result == "hello world"

    def test_complete_bad_response_raises(self, monkeypatch) -> None:
        from llm.adapters.anthropic_messages import AnthropicMessagesClient
        cfg = _make_cfg("anthropic")
        client = AnthropicMessagesClient(cfg)

        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "shape"}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("httpx.Client", lambda **kwargs: mock_client)

        messages = [ChatMessage(role="user", content="test")]
        with pytest.raises(RuntimeError, match="unexpected"):
            client.complete(messages)

    def test_complete_with_model_override(self, monkeypatch) -> None:
        from llm.adapters.anthropic_messages import AnthropicMessagesClient
        cfg = _make_cfg("anthropic")
        client = AnthropicMessagesClient(cfg)

        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"type": "text", "text": "ok"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("httpx.Client", lambda **kwargs: mock_client)

        messages = [ChatMessage(role="user", content="test")]
        client.complete(messages, model="custom-model")
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["model"] == "custom-model"


# --- OpenAIChatClient ---

class TestOpenAIChatClient:
    def test_wrong_provider_raises(self) -> None:
        from llm.adapters.openai_chat import OpenAIChatClient
        cfg = _make_cfg(provider="anthropic")
        with pytest.raises(ValueError, match="openai"):
            OpenAIChatClient(cfg)

    def test_constructor_sets_url(self) -> None:
        from llm.adapters.openai_chat import OpenAIChatClient
        cfg = _make_cfg("openai")
        client = OpenAIChatClient(cfg)
        assert client._url == "https://api.example.com/chat/completions"

    def test_complete_basic(self, monkeypatch) -> None:
        from llm.adapters.openai_chat import OpenAIChatClient
        cfg = _make_cfg("openai")
        client = OpenAIChatClient(cfg)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "hello"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("httpx.Client", lambda **kwargs: mock_client)

        messages = [ChatMessage(role="user", content="test")]
        result = client.complete(messages)
        assert result == "hello"

    def test_complete_empty_content(self, monkeypatch) -> None:
        from llm.adapters.openai_chat import OpenAIChatClient
        cfg = _make_cfg("openai")
        client = OpenAIChatClient(cfg)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": None}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("httpx.Client", lambda **kwargs: mock_client)

        messages = [ChatMessage(role="user", content="test")]
        result = client.complete(messages)
        assert result == ""

    def test_complete_bad_response_raises(self, monkeypatch) -> None:
        from llm.adapters.openai_chat import OpenAIChatClient
        cfg = _make_cfg("openai")
        client = OpenAIChatClient(cfg)

        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "shape"}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("httpx.Client", lambda **kwargs: mock_client)

        messages = [ChatMessage(role="user", content="test")]
        with pytest.raises(RuntimeError, match="unexpected"):
            client.complete(messages)

    def test_complete_with_model_override(self, monkeypatch) -> None:
        from llm.adapters.openai_chat import OpenAIChatClient
        cfg = _make_cfg("openai")
        client = OpenAIChatClient(cfg)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        monkeypatch.setattr("httpx.Client", lambda **kwargs: mock_client)

        messages = [ChatMessage(role="user", content="test")]
        client.complete(messages, model="gpt-4")
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["model"] == "gpt-4"
