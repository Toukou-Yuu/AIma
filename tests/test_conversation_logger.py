"""Conversation logger diagnostics."""

from __future__ import annotations

from llm.agent.conversation_logger import ConversationLogger
from llm.protocol import ChatMessage


def test_conversation_logger_writes_parser_result(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    logger = ConversationLogger(player_id="player-a", conversation_id="conv-a", enabled=True)

    logger.log_turn(
        turn_number=1,
        seat=0,
        phase="in_round",
        messages=[ChatMessage(role="user", content="choose")],
        response="",
        parser_result={
            "status": "parse_failed",
            "error": "no JSON object",
            "fallback_action": {"kind": "draw", "seat": 0},
        },
    )
    logger.close()

    files = list(tmp_path.glob("configs/players/player-a/conversations/*-conv-a.md"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "**AIma Parser**" in text
    assert '"status": "parse_failed"' in text
    assert '"fallback_action"' in text
