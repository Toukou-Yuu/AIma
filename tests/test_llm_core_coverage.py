"""llm.agent.core 覆盖缺口测试。"""

from __future__ import annotations

from kernel.engine.actions import ActionKind
from kernel.api.legal_actions import LegalAction
from kernel.tiles.model import Suit, Tile
from llm.agent.core import _parser_log_payload, _debug_save_last_prompt
from llm.agent.decision_parser import DecisionParseResult
from llm.protocol import ChatMessage

MAN1 = Tile(Suit.MAN, 1)


# --- _parser_log_payload ---

class TestParserLogPayload:
    def test_basic_status(self) -> None:
        """基本 status 字段（L228-230）。"""
        result = DecisionParseResult(
            action=None, why=None, choice=None, status="ok",
        )
        payload = _parser_log_payload(result, fallback_action=None)
        assert payload["status"] == "ok"

    def test_all_fields(self) -> None:
        """所有可选字段（L231-242）。"""
        la = LegalAction(kind=ActionKind.DISCARD, tile=MAN1, seat=0)
        result = DecisionParseResult(
            action=la, why="reason", choice={"action": "discard"},
            status="matched", note="note", error="err",
        )
        fallback = LegalAction(kind=ActionKind.PASS_CALL, seat=0)
        payload = _parser_log_payload(result, fallback_action=fallback)
        assert payload["note"] == "note"
        assert payload["error"] == "err"
        assert payload["why"] == "reason"
        assert payload["choice"] == {"action": "discard"}
        assert "matched_action" in payload
        assert "fallback_action" in payload

    def test_none_fields_omitted(self) -> None:
        """None 字段不包含在 payload 中。"""
        result = DecisionParseResult(
            action=None, why=None, choice=None, status="fallback",
        )
        payload = _parser_log_payload(result, fallback_action=None)
        assert "note" not in payload
        assert "error" not in payload
        assert "why" not in payload
        assert "choice" not in payload
        assert "matched_action" not in payload
        assert "fallback_action" not in payload


# --- _debug_save_last_prompt ---

class TestDebugSaveLastPrompt:
    def test_exception_handled(self) -> None:
        """写入失败时静默捕获（L263-265）。"""
        # 传入空消息列表，函数内部会尝试写入 logs/ 目录
        # 如果 logs/ 不存在或无权限，应该静默处理
        _debug_save_last_prompt([])

    def test_normal_messages(self) -> None:
        """正常消息列表不报错。"""
        messages = [
            ChatMessage(role="system", content="test"),
            ChatMessage(role="user", content="hello"),
        ]
        _debug_save_last_prompt(messages)
