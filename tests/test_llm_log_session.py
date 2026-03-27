"""CLI 会话日志 stem 解析。"""

from __future__ import annotations

import pytest

from llm.cli import _resolve_log_stem


def test_log_stem_disabled() -> None:
    assert _resolve_log_stem(None) is None


def test_log_stem_auto_nonempty() -> None:
    s = _resolve_log_stem("")
    assert s
    assert len(s) >= 14


def test_log_stem_custom_ok() -> None:
    assert _resolve_log_stem("run_01") == "run_01"
    assert _resolve_log_stem("a-b.c_2") == "a-b.c_2"


@pytest.mark.parametrize(
    "bad",
    [" ../x", "a/b", "..", "-bad", "x" * 300],
)
def test_log_stem_rejects_unsafe(bad: str) -> None:
    with pytest.raises(ValueError):
        _resolve_log_stem(bad)
