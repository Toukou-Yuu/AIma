"""``--log-session`` 对应的 runner 侧 logging。"""

from __future__ import annotations

import logging

import pytest

from llm.config import MatchEndCondition
from llm.runner import run_llm_match
from tests.llm_test_utils import load_test_runtime_config


@pytest.fixture
def caplog_for_runner(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level(logging.INFO, logger="llm.runner")
    return caplog


def test_session_audit_logs_apply_lines(caplog_for_runner: pytest.LogCaptureFixture) -> None:
    # 使用 match_end 来限制对局步数（单局即可测试）
    match_end = MatchEndCondition(type="hands", value=1, allow_negative=False)  # 只打1局
    runtime = load_test_runtime_config()
    run_llm_match(
        seed=2,
        match_end=match_end,
        dry_run=True,
        session_audit=True,
        request_delay_seconds=0.0,
        history_budget=runtime.history_budget,
        context_scope=runtime.context_scope,
        compression_level=runtime.compression_level,
        context_budget_tokens=runtime.context_budget_tokens,
        reserved_output_tokens=runtime.reserved_output_tokens,
        safety_margin_tokens=runtime.safety_margin_tokens,
        prompt_format=runtime.prompt_format,
        enable_conversation_logging=runtime.conversation_logging_enabled,
    )
    texts = [r.message for r in caplog_for_runner.records]
    assert any("begin_round" in t for t in texts)
    assert any("apply step=" in t for t in texts)
