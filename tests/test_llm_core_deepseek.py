"""llm.agent.core decide() 覆盖测试。"""

from __future__ import annotations

from kernel import ActionKind, initial_game_state, apply, build_deck, shuffle_deck, legal_actions
from kernel.engine.actions import Action
from llm.agent.core import AgentCore
from llm.agent.context import EpisodeContext
from llm.agent.context_store import PersistentState
from llm.agent.memory import PlayerMemory
from llm.agent.profile import PlayerProfile
from llm.agent.prompt import PromptProjector
from llm.agent.stats import PlayerStats
from llm.config import LLMClientConfig
from llm.protocol import build_client


def _deepseek_client():
    cfg = LLMClientConfig(
        provider="openai",
        api_key="sk-467c7001b0024712b3c004b1c956e7dd",
        base_url="https://api.deepseek.com/",
        model="deepseek-v4-flash",
        timeout_sec=30,
        max_context=4096,
        max_tokens=256,
        system_prompt="你是一个日麻 AI。",
        prompt_format="natural",
        context_scope="per_hand",
        compression_level="none",
        history_budget=2000,
        context_compression_threshold=0.8,
    )
    return build_client(cfg)


def _profile():
    return PlayerProfile(
        id="test", name="Test", model="deepseek-v4-flash",
        provider="openai", temperature=0.7, max_tokens=256, timeout_sec=30,
        persona_prompt="你是一个日麻 AI。", strategy_prompt="",
    )


def _make_prompt_projector():
    return PromptProjector(
        profile=_profile(),
        prompt_mode="natural",
        context_scope="per_hand",
        history_budget=2000,
        compression_level="none",
        max_context_tokens=4096,
        max_output_tokens=256,
        context_compression_threshold=0.8,
        system_prompt_base="你是一个日麻 AI。请返回你要执行的动作。",
    )


def _game_state_with_legal_actions():
    """构造一个有合法动作的 GameState。"""
    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=42))
    g1 = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    seat = g1.board.current_seat
    acts = legal_actions(g1, seat)
    if not acts:
        g1 = apply(g1, Action(ActionKind.DRAW)).new_state
        seat = g1.board.current_seat
        acts = legal_actions(g1, seat)
    return g1, seat, acts


def _persistent_state():
    return PersistentState(memory=PlayerMemory(), stats=PlayerStats())


def test_decide_with_session_audit_and_delay() -> None:
    """session_audit=True + request_delay > 0 覆盖 core.py L139/L144-146/L196-198。"""
    client = _deepseek_client()
    projector = _make_prompt_projector()
    core = AgentCore(profile=_profile(), prompt_mode="natural")
    ctx = EpisodeContext(seat=0)

    state, seat, acts = _game_state_with_legal_actions()

    decision = core.decide(
        state=state,
        seat=seat,
        episode_ctx=ctx,
        prompt_projector=projector,
        persistent_state=_persistent_state(),
        client=client,
        session_audit=True,
        request_delay_seconds=0.1,
    )
    assert decision.action is not None


def test_decide_with_conversation_logger() -> None:
    """conversation_logger 非 None 覆盖 core.py L163-171。"""
    from llm.agent.conversation_logger import ConversationLogger

    client = _deepseek_client()
    projector = _make_prompt_projector()
    core = AgentCore(profile=_profile(), prompt_mode="natural")
    ctx = EpisodeContext(seat=0)

    state, seat, acts = _game_state_with_legal_actions()

    logger = ConversationLogger(
        player_id="test",
        conversation_id="test_conv",
        enabled=True,
    )
    try:
        decision = core.decide(
            state=state,
            seat=seat,
            episode_ctx=ctx,
            prompt_projector=projector,
            persistent_state=_persistent_state(),
            client=client,
            conversation_logger=logger,
            session_audit=False,
            request_delay_seconds=0.0,
        )
        assert decision.action is not None
    finally:
        logger.close()
