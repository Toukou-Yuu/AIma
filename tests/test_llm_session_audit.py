"""``--log-session`` 对应的 runner 侧 logging。"""

from __future__ import annotations

import logging

import pytest

from llm.runner import run_llm_match


@pytest.fixture
def caplog_for_runner(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level(logging.INFO, logger="llm.runner")
    return caplog


def test_session_audit_logs_apply_lines(caplog_for_runner: pytest.LogCaptureFixture) -> None:
    run_llm_match(seed=2, max_steps=8, dry_run=True, session_audit=True)
    texts = [r.message for r in caplog_for_runner.records]
    assert any("begin_round" in t for t in texts)
    assert any("apply step=" in t for t in texts)
