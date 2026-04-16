"""LLM 上下文投影与会话边界测试。"""

from __future__ import annotations

import json

from kernel import Action, ActionKind, apply, build_deck, initial_game_state, legal_actions, shuffle_deck
from llm.agent import PlayerAgent
from llm.agent.context import EpisodeContext
from llm.agent.context_store import CompressionLevel, ContextEvent, ContextStore, PersistentState, TurnContext
from llm.agent.memory import PlayerMemory
from llm.agent.profile import PlayerProfile
from llm.agent.prompt import PromptProjector
from llm.agent.stats import PlayerStats
from llm.turns import pending_actor_seats
from llm.wire import legal_action_to_wire


class _TrackingClient:
    def __init__(self, payload: str) -> None:
        self._payload = payload
        self.session_ids: list[str | None] = []
        self.messages: list[list[object]] = []

    def complete(
        self,
        messages: list[object],
        *,
        model: str | None = None,
        session_id: str | None = None,
    ) -> str:
        self.session_ids.append(session_id)
        self.messages.append(messages)
        return self._payload


def _sample_state(seed: int = 21) -> tuple[object, int, tuple[object, ...]]:
    g0 = initial_game_state()
    wall = tuple(shuffle_deck(build_deck(), seed=seed))
    state = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall)).new_state
    seat = pending_actor_seats(state)[0]
    acts = legal_actions(state, seat)
    return state, seat, acts


def test_default_session_scope_is_per_hand() -> None:
    state, seat, acts = _sample_state()
    payload = json.dumps(dict(legal_action_to_wire(acts[0])), ensure_ascii=False)
    client = _TrackingClient(payload)
    agent = PlayerAgent(system_prompt="你是麻将牌手")

    ctx1 = EpisodeContext(seat, match_id="matchA", hand_number=1)
    agent.decide(state, seat, episode_ctx=ctx1, client=client, dry_run=False)

    ctx2 = EpisodeContext(seat, match_id="matchA", hand_number=2)
    agent.decide(state, seat, episode_ctx=ctx2, client=client, dry_run=False)

    assert client.session_ids[0] != client.session_ids[1]
    assert client.session_ids[0] is not None
    assert client.session_ids[0].endswith("_h1")
    assert client.session_ids[1].endswith("_h2")


def test_per_match_session_scope_reuses_session_id() -> None:
    state, seat, acts = _sample_state(seed=22)
    payload = json.dumps(dict(legal_action_to_wire(acts[0])), ensure_ascii=False)
    client = _TrackingClient(payload)
    agent = PlayerAgent(system_prompt="你是麻将牌手", session_scope="per_match")

    ctx1 = EpisodeContext(seat, match_id="matchB", hand_number=1)
    agent.decide(state, seat, episode_ctx=ctx1, client=client, dry_run=False)

    ctx2 = EpisodeContext(seat, match_id="matchB", hand_number=2)
    agent.decide(state, seat, episode_ctx=ctx2, client=client, dry_run=False)

    assert client.session_ids[0] == client.session_ids[1]
    assert client.session_ids[0] is not None
    assert client.session_ids[0].endswith("_mmatchB")


def test_stateless_session_scope_omits_session_id() -> None:
    state, seat, acts = _sample_state(seed=23)
    payload = json.dumps(dict(legal_action_to_wire(acts[0])), ensure_ascii=False)
    client = _TrackingClient(payload)
    agent = PlayerAgent(system_prompt="你是麻将牌手", session_scope="stateless")

    ctx = EpisodeContext(seat, match_id="matchC", hand_number=1)
    agent.decide(state, seat, episode_ctx=ctx, client=client, dry_run=False)

    assert client.session_ids == [None]


def test_prompt_projector_reads_latest_memory_snapshot() -> None:
    state, seat, acts = _sample_state(seed=24)
    payload = json.dumps(dict(legal_action_to_wire(acts[0])), ensure_ascii=False)
    client = _TrackingClient(payload)
    agent = PlayerAgent(system_prompt="你是麻将牌手")

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
    profile = PlayerProfile(id="default", name="Default", model="gpt-4o-mini")
    projector = PromptProjector(
        profile,
        system_prompt_base="你是麻将牌手",
        prompt_mode="natural",
        use_delta=True,
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
