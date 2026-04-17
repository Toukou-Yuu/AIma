"""LLM 上下文投影与会话边界测试。"""

from __future__ import annotations

import json
from pathlib import Path

from kernel import Action, ActionKind, apply, build_deck, initial_game_state, legal_actions, shuffle_deck
from llm.agent.context import EpisodeContext
from llm.agent.context_store import CompressionLevel, ContextEvent, ContextStore, PersistentState, TurnContext
from llm.agent.event_journal import MatchJournal
from llm.agent.match_context import MatchContext
from llm.agent.memory import PlayerMemory
from llm.agent.profile import PlayerProfile
from llm.agent.prompt import PromptProjector
from llm.agent.stats import PlayerStats
from llm.config import load_llm_runtime_config
from llm.turns import pending_actor_seats
from llm.wire import legal_action_to_wire
from tests.llm_test_utils import build_test_agent


_RUNTIME = load_llm_runtime_config(config_path=Path("tests/fixtures/llm_runtime.yaml"))


class _TrackingClient:
    def __init__(self, payload: str) -> None:
        self._payload = payload
        self.messages: list[list[object]] = []

    def complete(
        self,
        messages: list[object],
        *,
        model: str | None = None,
    ) -> str:
        self.messages.append(messages)
        return self._payload


def _sample_state(seed: int = 21) -> tuple[object, int, tuple[object, ...]]:
    g0 = initial_game_state()
    wall = tuple(shuffle_deck(build_deck(), seed=seed))
    state = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall)).new_state
    seat = pending_actor_seats(state)[0]
    acts = legal_actions(state, seat)
    return state, seat, acts


def test_default_context_scope_is_per_hand() -> None:
    state, seat, acts = _sample_state()
    payload = json.dumps(dict(legal_action_to_wire(acts[0])), ensure_ascii=False)
    client = _TrackingClient(payload)
    agent = build_test_agent(system_prompt="你是麻将牌手")

    ctx = EpisodeContext(seat, match_id="matchA", hand_number=1)
    agent.decide(state, seat, episode_ctx=ctx, client=client, dry_run=False)
    agent.decide(state, seat, episode_ctx=ctx, client=client, dry_run=False)

    second_messages = [msg.content for msg in client.messages[1]]
    assert any("本局我的决策历史" in content for content in second_messages)
    assert not any("本场前情摘要" in content for content in second_messages)


def test_per_match_context_scope_reuses_local_match_archive() -> None:
    state, seat, acts = _sample_state(seed=22)
    payload = json.dumps(dict(legal_action_to_wire(acts[0])), ensure_ascii=False)
    client = _TrackingClient(payload)
    agent = build_test_agent(system_prompt="你是麻将牌手", context_scope="per_match")
    match_ctx = MatchContext(seat)

    ctx1 = match_ctx.create_episode()
    agent.decide(state, seat, episode_ctx=ctx1, client=client, dry_run=False)
    ctx1.end_episode(1200)
    match_ctx.close_episode(ctx1)

    ctx2 = match_ctx.create_episode()
    agent.decide(state, seat, episode_ctx=ctx2, client=client, dry_run=False)

    second_messages = [msg.content for msg in client.messages[1]]
    assert any("本场前情摘要" in content for content in second_messages)
    assert any("第1局" in content for content in second_messages)


def test_stateless_context_scope_omits_local_history() -> None:
    state, seat, acts = _sample_state(seed=23)
    payload = json.dumps(dict(legal_action_to_wire(acts[0])), ensure_ascii=False)
    client = _TrackingClient(payload)
    agent = build_test_agent(system_prompt="你是麻将牌手", context_scope="stateless")

    ctx = EpisodeContext(seat, match_id="matchC", hand_number=1)
    agent.decide(state, seat, episode_ctx=ctx, client=client, dry_run=False)
    agent.decide(state, seat, episode_ctx=ctx, client=client, dry_run=False)

    second_messages = [msg.content for msg in client.messages[1]]
    assert not any("本局我的决策历史" in content for content in second_messages)
    assert not any("本局公共事件" in content for content in second_messages)
    assert not any("本场前情摘要" in content for content in second_messages)


def test_per_hand_scope_can_include_public_event_history() -> None:
    g0 = initial_game_state()
    wall = tuple(shuffle_deck(build_deck(), seed=26))
    begin_out = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall))
    state = begin_out.new_state
    seat = pending_actor_seats(state)[0]
    acts = legal_actions(state, seat)
    payload = json.dumps(dict(legal_action_to_wire(acts[0])), ensure_ascii=False)
    client = _TrackingClient(payload)
    journal = MatchJournal()
    journal.start_hand(1, begin_out.events)
    agent = build_test_agent(system_prompt="你是麻将牌手")

    ctx = EpisodeContext(seat, match_id="match-public", hand_number=1, match_journal=journal)
    agent.decide(state, seat, episode_ctx=ctx, client=client, dry_run=False)

    messages = [msg.content for msg in client.messages[0]]
    assert any("本局公共事件" in content for content in messages)
    assert any("第1局开始" in content for content in messages)


def test_prompt_projector_reads_latest_memory_snapshot() -> None:
    state, seat, acts = _sample_state(seed=24)
    payload = json.dumps(dict(legal_action_to_wire(acts[0])), ensure_ascii=False)
    client = _TrackingClient(payload)
    agent = build_test_agent(system_prompt="你是麻将牌手")

    ctx1 = EpisodeContext(seat, match_id="matchD", hand_number=1)
    agent.decide(state, seat, episode_ctx=ctx1, client=client, dry_run=False)
    first_system = client.messages[0][0].content
    assert "整体风格" not in first_system

    agent.memory = PlayerMemory(play_bias="defensive")

    ctx2 = EpisodeContext(seat, match_id="matchD", hand_number=2)
    agent.decide(state, seat, episode_ctx=ctx2, client=client, dry_run=False)
    second_system = client.messages[1][0].content
    assert "整体风格: 偏向防守" in second_system


def test_natural_mode_never_switches_to_delta_frame() -> None:
    profile = PlayerProfile(
        id="default",
        name="Default",
        model="gpt-4o-mini",
        provider="openai",
        temperature=0.7,
        max_tokens=1024,
        timeout_sec=120.0,
        persona_prompt="",
        strategy_prompt="",
    )
    projector = PromptProjector(
        profile,
        system_prompt_base="你是麻将牌手",
        prompt_mode="natural",
        context_scope=_RUNTIME.context_scope,
        use_delta=True,
        history_budget=_RUNTIME.history_budget,
        compression_level=_RUNTIME.compression_level,
        context_budget_tokens=_RUNTIME.context_budget_tokens,
        reserved_output_tokens=_RUNTIME.reserved_output_tokens,
        safety_margin_tokens=_RUNTIME.safety_margin_tokens,
    )
    state, seat, acts = _sample_state(seed=25)
    obs = __import__("kernel").observation(state, seat, mode="human")
    ctx = EpisodeContext(seat, match_id="matchE", hand_number=1)
    ctx.last_observation = obs
    ctx.last_hand = obs.hand.copy() if obs.hand else None
    ctx.frame_count = 1

    assert projector.get_frame_type(ctx, should_send_keyframe=False) == "keyframe"


def test_context_store_collapse_keeps_recent_events() -> None:
    store = ContextStore()
    for idx in range(1, 7):
        store.append_event(
            ContextEvent(
                turn_index=idx,
                phase="in_round",
                action_kind="discard",
                action_text=f"打{idx}m",
                why=f"理由{idx}",
                legal_action_count=4,
                riichi_players=(),
                scores=(25000, 25000, 25000, 25000),
            )
        )

    projection = store.project_history(
        detailed=True,
        history_budget=4,
        compression_level="collapse",
    )

    assert "已折叠" in projection.text
    assert "第6巡" in projection.text
    assert projection.collapsed_event_count == 4
