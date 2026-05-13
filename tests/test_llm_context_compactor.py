"""context_compactor.py 覆盖测试：ContextCompactor.compact 异常处理与空摘要。"""

from __future__ import annotations

from llm.agent.context_compactor import ContextCompactor
from llm.agent.message_ledger import LedgerMessage
from llm.protocol import ChatMessage


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _ledger_message(
    turn: int = 1,
    role: str = "user",
    content: str = "test content",
) -> LedgerMessage:
    return LedgerMessage(
        message_id=f"turn_{turn}_{role}",
        role=role,  # type: ignore[arg-type]
        content=content,
        turn_index=turn,
        hand_number=1,
        kind="turn_state",
    )


class _StubClient:
    """可配置返回值或异常的 stub client。"""

    def __init__(self, result: str | None = None, exc: Exception | None = None):
        self._result = result
        self._exc = exc
        self.calls: list[list[ChatMessage]] = []

    def complete(self, messages, *, model=None):
        self.calls.append(messages)
        if self._exc is not None:
            raise self._exc
        return self._result or ""


# ===================================================================
# compact: 空消息列表
# ===================================================================


def test_compact_empty_messages() -> None:
    """空消息列表返回 None。"""
    compactor = ContextCompactor()
    client = _StubClient(result="摘要")
    result = compactor.compact(
        client=client, messages=[], hand_number=1, target_tokens=100,
    )
    assert result is None
    assert len(client.calls) == 0  # 不应调用 LLM


# ===================================================================
# compact: 正常摘要
# ===================================================================


def test_compact_returns_summary_message() -> None:
    """正常摘要返回 LedgerMessage。"""
    compactor = ContextCompactor()
    client = _StubClient(result="这是摘要内容")
    messages = [_ledger_message(1, "user", "决策1"), _ledger_message(1, "assistant", "回复1")]
    result = compactor.compact(
        client=client, messages=messages, hand_number=2, target_tokens=200,
    )
    assert result is not None
    assert result.role == "user"
    assert "语义压缩摘要" in result.content
    assert "这是摘要内容" in result.content
    assert result.hand_number == 2
    assert result.kind == "summary"
    assert result.compression_state == "autocompact"
    assert result.turn_index == messages[-1].turn_index


def test_compact_calls_client_with_correct_prompt() -> None:
    """调用 client 时发送正确的压缩提示。"""
    compactor = ContextCompactor()
    client = _StubClient(result="摘要")
    messages = [_ledger_message(1, "user", "你好"), _ledger_message(1, "assistant", "好的")]
    compactor.compact(
        client=client, messages=messages, hand_number=1, target_tokens=128,
    )
    assert len(client.calls) == 1
    call_messages = client.calls[0]
    assert len(call_messages) == 2
    assert call_messages[0].role == "system"
    assert "上下文压缩器" in call_messages[0].content
    assert call_messages[1].role == "user"
    assert "128 token" in call_messages[1].content


# ===================================================================
# compact: 异常处理
# ===================================================================


def test_compact_exception_returns_none() -> None:
    """client.complete 抛异常时返回 None，不传播。"""
    compactor = ContextCompactor()
    client = _StubClient(exc=RuntimeError("LLM 调用失败"))
    messages = [_ledger_message(1, "user", "内容")]
    result = compactor.compact(
        client=client, messages=messages, hand_number=1, target_tokens=100,
    )
    assert result is None


def test_compact_connection_error_returns_none() -> None:
    """网络错误也安全返回 None。"""
    compactor = ContextCompactor()
    client = _StubClient(exc=ConnectionError("timeout"))
    messages = [_ledger_message()]
    result = compactor.compact(
        client=client, messages=messages, hand_number=1, target_tokens=100,
    )
    assert result is None


# ===================================================================
# compact: 空摘要返回
# ===================================================================


def test_compact_empty_summary_returns_none() -> None:
    """client 返回空字符串时返回 None。"""
    compactor = ContextCompactor()
    client = _StubClient(result="")
    messages = [_ledger_message()]
    result = compactor.compact(
        client=client, messages=messages, hand_number=1, target_tokens=100,
    )
    assert result is None


def test_compact_whitespace_only_summary_returns_none() -> None:
    """client 返回纯空白时 .strip() 后为空，返回 None。"""
    compactor = ContextCompactor()
    client = _StubClient(result="   \n  ")
    messages = [_ledger_message()]
    result = compactor.compact(
        client=client, messages=messages, hand_number=1, target_tokens=100,
    )
    assert result is None


# ===================================================================
# _build_compaction_prompt
# ===================================================================


def test_build_compaction_prompt_includes_messages() -> None:
    """生成的压缩提示包含历史消息。"""
    compactor = ContextCompactor()
    messages = [
        _ledger_message(1, "user", "用户消息"),
        _ledger_message(1, "assistant", "助手回复"),
    ]
    prompt = compactor._build_compaction_prompt(messages, target_tokens=200)
    assert "[user turn=1]" in prompt
    assert "用户消息" in prompt
    assert "[assistant turn=1]" in prompt
    assert "助手回复" in prompt
    assert "200 token" in prompt


def test_build_compaction_prompt_target_minimum() -> None:
    """target_tokens 被截断到最少 64。"""
    compactor = ContextCompactor()
    prompt = compactor._build_compaction_prompt([_ledger_message()], target_tokens=10)
    assert "64 token" in prompt
