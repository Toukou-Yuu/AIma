"""ModelBackend 测试。

Backend types:
- dummy: 固定响应后端，用于简单测试
- mock: 可配置响应后端，用于测试
- openai_compatible: OpenAI 兼容 API 后端
- llama_cpp: 未实现，应抛出 ValueError
- vllm_native: 未实现，应抛出 ValueError
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from models.backend import ChatMessage
from models.registry import build_backend
from models.schema import ModelSpec


class TestDummyBackend:
    """DummyBackend 测试。"""

    def test_returns_fixed_response(self) -> None:
        """返回固定响应。"""
        spec = ModelSpec(backend="dummy", model_name="test-model")
        from models.backends.dummy import DummyBackend

        backend = DummyBackend(spec)
        messages = [ChatMessage(role="user", content="Hello")]

        result = backend.complete(messages)

        assert result == "dummy response"

    def test_returns_custom_response_from_extra(self) -> None:
        """从 extra 配置返回自定义响应。"""
        spec = ModelSpec(
            backend="dummy",
            model_name="test-model",
            extra={"response": "custom response"},
        )
        from models.backends.dummy import DummyBackend

        backend = DummyBackend(spec)
        messages = [ChatMessage(role="user", content="Hello")]

        result = backend.complete(messages)

        assert result == "custom response"

    def test_tracks_last_messages(self) -> None:
        """追踪最近一次调用的消息列表。"""
        spec = ModelSpec(backend="dummy", model_name="test-model")
        from models.backends.dummy import DummyBackend

        backend = DummyBackend(spec)

        assert backend.last_messages is None

        messages = [
            ChatMessage(role="system", content="You are helpful"),
            ChatMessage(role="user", content="Hello"),
        ]
        backend.complete(messages)

        assert backend.last_messages is not None
        assert len(backend.last_messages) == 2
        assert backend.last_messages[0].role == "system"
        assert backend.last_messages[1].role == "user"
        assert backend.last_messages[1].content == "Hello"

    def test_response_can_be_changed(self) -> None:
        """响应可以被动态修改。"""
        spec = ModelSpec(backend="dummy", model_name="test-model")
        from models.backends.dummy import DummyBackend

        backend = DummyBackend(spec)
        messages = [ChatMessage(role="user", content="Hello")]

        assert backend.complete(messages) == "dummy response"

        backend.response = "new response"
        assert backend.complete(messages) == "new response"

    def test_requires_dummy_backend_type(self) -> None:
        """必须使用 backend=dummy 配置。"""
        spec = ModelSpec(backend="mock", model_name="test-model")
        from models.backends.dummy import DummyBackend

        with pytest.raises(ValueError, match="DummyBackend requires backend=dummy"):
            DummyBackend(spec)


class TestMockBackend:
    """MockBackend 测试。"""

    def test_returns_default_response(self) -> None:
        """无匹配时返回默认响应（model_name）。"""
        spec = ModelSpec(backend="mock", model_name="test-model")
        from models.backends.mock import MockBackend

        backend = MockBackend(spec)
        messages = [ChatMessage(role="user", content="Hello")]

        result = backend.complete(messages)

        assert result == "test-model"

    def test_configurable_responses(self) -> None:
        """可配置响应映射。"""
        spec = ModelSpec(backend="mock", model_name="test-model")
        from models.backends.mock import MockBackend

        responses = {"What is your name?": "I am MockBot", "Hello": "Hi there!"}
        backend = MockBackend(spec, responses=responses)

        result1 = backend.complete([ChatMessage(role="user", content="Hello")])
        assert result1 == "Hi there!"

        result2 = backend.complete([ChatMessage(role="user", content="What is your name?")])
        assert result2 == "I am MockBot"

    def test_matches_response_by_last_user_message(self) -> None:
        """根据最后一条用户消息匹配响应。"""
        spec = ModelSpec(backend="mock", model_name="test-model")
        from models.backends.mock import MockBackend

        responses = {"question": "answer"}
        backend = MockBackend(spec, responses=responses)

        messages = [
            ChatMessage(role="system", content="Be helpful"),
            ChatMessage(role="user", content="ignored"),
            ChatMessage(role="assistant", content="previous response"),
            ChatMessage(role="user", content="question"),
        ]
        result = backend.complete(messages)

        assert result == "answer"

    def test_uses_first_user_message_from_end(self) -> None:
        """从后向前查找第一条用户消息。"""
        spec = ModelSpec(backend="mock", model_name="test-model")
        from models.backends.mock import MockBackend

        responses = {"first": "matched first", "second": "matched second"}
        backend = MockBackend(spec, responses=responses)

        # 最后一条用户消息是 "second"，应该匹配 "matched second"
        messages = [
            ChatMessage(role="user", content="first"),
            ChatMessage(role="assistant", content="response"),
            ChatMessage(role="user", content="second"),
        ]
        result = backend.complete(messages)

        assert result == "matched second"

    def test_falls_back_to_default_when_no_match(self) -> None:
        """无匹配时回退到默认响应。"""
        spec = ModelSpec(backend="mock", model_name="test-model")
        from models.backends.mock import MockBackend

        responses = {"other": "other response"}
        backend = MockBackend(spec, responses=responses)

        result = backend.complete([ChatMessage(role="user", content="Hello")])

        assert result == "test-model"

    def test_default_response_from_extra(self) -> None:
        """可从 extra 配置默认响应。"""
        spec = ModelSpec(
            backend="mock",
            model_name="test-model",
            extra={"default_response": "custom default"},
        )
        from models.backends.mock import MockBackend

        backend = MockBackend(spec)

        result = backend.complete([ChatMessage(role="user", content="unknown")])

        assert result == "custom default"

    def test_tracks_last_messages(self) -> None:
        """追踪最近一次调用的消息列表。"""
        spec = ModelSpec(backend="mock", model_name="test-model")
        from models.backends.mock import MockBackend

        backend = MockBackend(spec)

        assert backend.last_messages is None

        messages = [ChatMessage(role="user", content="Hello")]
        backend.complete(messages)

        assert backend.last_messages is not None
        assert len(backend.last_messages) == 1
        assert backend.last_messages[0].content == "Hello"

    def test_set_response(self) -> None:
        """可动态设置响应。"""
        spec = ModelSpec(backend="mock", model_name="test-model")
        from models.backends.mock import MockBackend

        backend = MockBackend(spec)
        backend.set_response("Hello", "Hi!")

        result = backend.complete([ChatMessage(role="user", content="Hello")])

        assert result == "Hi!"

    def test_set_default_response(self) -> None:
        """可动态设置默认响应。"""
        spec = ModelSpec(backend="mock", model_name="test-model")
        from models.backends.mock import MockBackend

        backend = MockBackend(spec)
        backend.set_default_response("new default")

        result = backend.complete([ChatMessage(role="user", content="unknown")])

        assert result == "new default"

    def test_requires_mock_backend_type(self) -> None:
        """必须使用 backend=mock 配置。"""
        spec = ModelSpec(backend="dummy", model_name="test-model")
        from models.backends.mock import MockBackend

        with pytest.raises(ValueError, match="MockBackend requires backend=mock"):
            MockBackend(spec)


class TestOpenAICompatibleBackendRequest:
    """OpenAICompatibleBackend 请求构建测试（不发起真实 HTTP 调用）。"""

    def test_request_construction_headers_and_body(self) -> None:
        """测试请求构建：headers 和 body。"""
        spec = ModelSpec(
            backend="openai_compatible",
            model_name="gpt-4",
            endpoint="https://api.example.com/v1",
            temperature=0.7,
            max_tokens=1024,
        )
        from models.backends.openai_compatible import OpenAICompatibleBackend

        backend = OpenAICompatibleBackend(spec)

        messages = [
            ChatMessage(role="system", content="You are helpful"),
            ChatMessage(role="user", content="Hello"),
        ]

        # Mock httpx.Client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hi there!"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("models.backends.openai_compatible.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = backend.complete(messages)

        # 验证返回值
        assert result == "Hi there!"

        # 验证请求参数
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://api.example.com/v1/chat/completions"

        # 验证 headers
        headers = call_args[1]["headers"]
        assert headers["Content-Type"] == "application/json"
        assert "Authorization" not in headers  # 无 api_key_env 配置

        # 验证 body
        body = call_args[1]["json"]
        assert body["model"] == "gpt-4"
        assert body["temperature"] == 0.7
        assert body["max_tokens"] == 1024
        assert body["messages"] == [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ]

    def test_request_with_api_key(self) -> None:
        """测试带 API key 的请求。"""
        spec = ModelSpec(
            backend="openai_compatible",
            model_name="gpt-4",
            endpoint="https://api.example.com/v1",
            api_key_env="OPENAI_API_KEY",
        )
        from models.backends.openai_compatible import OpenAICompatibleBackend

        backend = OpenAICompatibleBackend(spec)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            # 需要重新实例化以读取环境变量
            backend = OpenAICompatibleBackend(spec)

            with patch("models.backends.openai_compatible.httpx.Client") as mock_client_class:
                mock_client = MagicMock()
                mock_client.post.return_value = mock_response
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_client_class.return_value = mock_client

                backend.complete([ChatMessage(role="user", content="test")])

                headers = mock_client.post.call_args[1]["headers"]
                assert headers["Authorization"] == "Bearer sk-test-key"

    def test_request_with_top_p(self) -> None:
        """测试包含 top_p 参数的请求。"""
        spec = ModelSpec(
            backend="openai_compatible",
            model_name="gpt-4",
            endpoint="https://api.example.com/v1",
            top_p=0.9,
        )
        from models.backends.openai_compatible import OpenAICompatibleBackend

        backend = OpenAICompatibleBackend(spec)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("models.backends.openai_compatible.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            backend.complete([ChatMessage(role="user", content="test")])

            body = mock_client.post.call_args[1]["json"]
            assert body["top_p"] == 0.9

    def test_request_with_extra_params(self) -> None:
        """测试 extra 参数合并到请求体。"""
        spec = ModelSpec(
            backend="openai_compatible",
            model_name="gpt-4",
            endpoint="https://api.example.com/v1",
            extra={"custom_param": "custom_value", "timeout_sec": 30.0},
        )
        from models.backends.openai_compatible import OpenAICompatibleBackend

        backend = OpenAICompatibleBackend(spec)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("models.backends.openai_compatible.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            backend.complete([ChatMessage(role="user", content="test")])

            body = mock_client.post.call_args[1]["json"]
            assert body["custom_param"] == "custom_value"

    def test_request_with_custom_model(self) -> None:
        """测试调用时指定自定义模型。"""
        spec = ModelSpec(
            backend="openai_compatible",
            model_name="gpt-4",
            endpoint="https://api.example.com/v1",
        )
        from models.backends.openai_compatible import OpenAICompatibleBackend

        backend = OpenAICompatibleBackend(spec)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("models.backends.openai_compatible.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            backend.complete([ChatMessage(role="user", content="test")], model="gpt-4-turbo")

            body = mock_client.post.call_args[1]["json"]
            assert body["model"] == "gpt-4-turbo"

    def test_response_stripping(self) -> None:
        """测试响应内容去除首尾空白。"""
        spec = ModelSpec(
            backend="openai_compatible",
            model_name="gpt-4",
            endpoint="https://api.example.com/v1",
        )
        from models.backends.openai_compatible import OpenAICompatibleBackend

        backend = OpenAICompatibleBackend(spec)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "  response with spaces  "}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("models.backends.openai_compatible.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = backend.complete([ChatMessage(role="user", content="test")])

            assert result == "response with spaces"

    def test_raises_on_missing_endpoint(self) -> None:
        """缺少 endpoint 时抛出 ValueError。"""
        spec = ModelSpec(
            backend="openai_compatible",
            model_name="gpt-4",
            endpoint=None,
        )
        from models.backends.openai_compatible import OpenAICompatibleBackend

        with pytest.raises(ValueError, match="OpenAICompatibleBackend requires endpoint"):
            OpenAICompatibleBackend(spec)

    def test_raises_on_unexpected_response_shape(self) -> None:
        """响应格式异常时抛出 RuntimeError。"""
        spec = ModelSpec(
            backend="openai_compatible",
            model_name="gpt-4",
            endpoint="https://api.example.com/v1",
        )
        from models.backends.openai_compatible import OpenAICompatibleBackend

        backend = OpenAICompatibleBackend(spec)

        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "format"}
        mock_response.raise_for_status = MagicMock()

        with patch("models.backends.openai_compatible.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            with pytest.raises(RuntimeError, match="unexpected OpenAI response shape"):
                backend.complete([ChatMessage(role="user", content="test")])

    def test_requires_openai_compatible_backend_type(self) -> None:
        """必须使用 backend=openai_compatible 配置。"""
        spec = ModelSpec(backend="dummy", model_name="test-model")
        from models.backends.openai_compatible import OpenAICompatibleBackend

        with pytest.raises(
            ValueError, match="OpenAICompatibleBackend requires backend=openai_compatible"
        ):
            OpenAICompatibleBackend(spec)


class TestRegistry:
    """build_backend 注册表测试。"""

    def test_build_dummy_backend(self) -> None:
        """构建 DummyBackend。"""
        spec = ModelSpec(backend="dummy", model_name="test-model")
        from models.backends.dummy import DummyBackend

        backend = build_backend(spec)

        assert isinstance(backend, DummyBackend)
        assert backend.spec.model_name == "test-model"

    def test_build_mock_backend(self) -> None:
        """构建 MockBackend。"""
        spec = ModelSpec(
            backend="mock",
            model_name="test-model",
            extra={"responses": {"Hello": "Hi!"}},
        )
        from models.backends.mock import MockBackend

        backend = build_backend(spec)

        assert isinstance(backend, MockBackend)
        # 验证 responses 配置生效
        result = backend.complete([ChatMessage(role="user", content="Hello")])
        assert result == "Hi!"

    def test_build_openai_compatible_backend(self) -> None:
        """构建 OpenAICompatibleBackend。"""
        spec = ModelSpec(
            backend="openai_compatible",
            model_name="gpt-4",
            endpoint="https://api.example.com/v1",
        )
        from models.backends.openai_compatible import OpenAICompatibleBackend

        backend = build_backend(spec)

        assert isinstance(backend, OpenAICompatibleBackend)
        assert backend.spec.model_name == "gpt-4"

    def test_llama_cpp_raises_value_error(self) -> None:
        """llama_cpp 后端抛出 ValueError（未实现）。"""
        spec = ModelSpec(backend="llama_cpp", model_name="local")

        with pytest.raises(ValueError, match="llama.cpp native backend is not implemented"):
            build_backend(spec)

    def test_vllm_native_raises_value_error(self) -> None:
        """vllm_native 后端抛出 ValueError（未实现）。"""
        spec = ModelSpec(backend="vllm_native", model_name="local")

        with pytest.raises(ValueError, match="vLLM native backend is not implemented"):
            build_backend(spec)

    def test_replay_raises_value_error(self) -> None:
        """replay 后端抛出 ValueError（未实现）。"""
        spec = ModelSpec(backend="replay", model_name="local")

        with pytest.raises(ValueError, match="Backend type 'replay' is not implemented"):
            build_backend(spec)

    def test_unknown_type_validated_by_pydantic(self) -> None:
        """未知后端类型由 Pydantic 在 ModelSpec 构建时验证。

        由于 ModelSpec.backend 使用 Literal 类型，Pydantic 会在构造时拒绝未知类型，
        因此 build_backend 中的 "unknown type" 分支是 unreachable 的防御性代码。
        """
        import pydantic

        with pytest.raises(pydantic.ValidationError, match="Input should be"):
            ModelSpec(backend="unknown_type", model_name="test")  # type: ignore[arg-type]