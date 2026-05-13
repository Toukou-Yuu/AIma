"""session.py LocalContextPolicy.build_window 覆盖。"""

from __future__ import annotations

from llm.agent.session import ConversationIdNamer, LocalContextPolicy


def test_stateless_scope() -> None:
    """stateless 所有层均为 False。"""
    policy = LocalContextPolicy(scope="stateless")
    w = policy.build_window()
    assert w.include_match_archive is False
    assert w.include_public_history is False
    assert w.include_self_history is False


def test_per_hand_scope() -> None:
    policy = LocalContextPolicy(scope="per_hand")
    w = policy.build_window()
    assert w.include_match_archive is False
    assert w.include_public_history is True
    assert w.include_self_history is True


def test_per_match_scope() -> None:
    policy = LocalContextPolicy(scope="per_match")
    w = policy.build_window()
    assert w.include_match_archive is True
    assert w.include_public_history is True
    assert w.include_self_history is True


def test_conversation_id_namer_default() -> None:
    namer = ConversationIdNamer()
    cid = namer.build_conversation_id(2, 3)
    assert "seat_2" in cid
    assert "h3" in cid
    assert "majiang_player_" in cid


def test_conversation_id_namer_with_player_id() -> None:
    namer = ConversationIdNamer(player_id="hikari")
    cid = namer.build_conversation_id(0, 1)
    assert "hikari" in cid
    assert "h1" in cid


def test_conversation_id_stable_per_instance() -> None:
    namer = ConversationIdNamer()
    a = namer.build_conversation_id(0)
    b = namer.build_conversation_id(0)
    assert a == b
