"""注入 Mock CompletionClient 的 Agent 决策路径。"""

from __future__ import annotations

import json

from kernel import (
    Action,
    ActionKind,
    apply,
    build_deck,
    initial_game_state,
    legal_actions,
    shuffle_deck,
)
from llm.agent import PlayerAgent, Decision
from llm.agent.context import EpisodeContext
from llm.turns import pending_actor_seats
from llm.wire import legal_action_to_wire
from tests.llm_test_utils import build_test_agent


class _ScriptedClient:
    """始终返回预先序列化的合法动作 JSON。"""

    def __init__(self, payload: str) -> None:
        self._payload = payload

    def complete(
        self,
        messages: list[object],
        *,
        model: str | None = None,
    ) -> str:
        return self._payload


def test_agent_decide_uses_client_json() -> None:
    """测试 Agent.decide 正确解析 LLM 返回的 JSON。"""
    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=11))
    state = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    seat = pending_actor_seats(state)[0]
    acts = legal_actions(state, seat)
    assert acts

    # 构造返回的 JSON payload
    wire = dict(legal_action_to_wire(acts[0]))
    wire["why"] = "测试：固定选首项合法动作"
    payload = json.dumps(wire, ensure_ascii=False)

    agent = build_test_agent(system_prompt="你是麻将牌手")
    episode_ctx = EpisodeContext(seat)
    decision = agent.decide(
        state,
        seat,
        episode_ctx=episode_ctx,
        client=_ScriptedClient(payload),
        dry_run=False,
    )

    assert decision.action == acts[0]
    assert decision.why == "测试：固定选首项合法动作"
    assert isinstance(decision.history, list)
    # 历史应包含 1 个 Decision（本次决策）
    assert len(decision.history) == 1
    assert decision.history[0].action == acts[0]


def test_agent_decide_fallback_when_json_invalid() -> None:
    """测试 LLM 返回无效 JSON 时的 fallback 行为。"""
    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=12))
    state = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    seat = pending_actor_seats(state)[0]
    acts = legal_actions(state, seat)

    agent = build_test_agent(system_prompt="你是麻将牌手")
    episode_ctx = EpisodeContext(seat)
    decision = agent.decide(
        state,
        seat,
        episode_ctx=episode_ctx,
        client=_ScriptedClient("not json"),
        dry_run=False,
    )

    assert decision.action == acts[0]
    assert decision.why is None
    # 即使解析失败也应记录历史
    assert isinstance(decision.history, list)


def test_agent_decide_dry_run() -> None:
    """测试 dry_run 模式跳过 LLM 调用。"""
    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=13))
    state = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    seat = pending_actor_seats(state)[0]
    acts = legal_actions(state, seat)

    agent = build_test_agent()
    episode_ctx = EpisodeContext(seat)
    decision = agent.decide(
        state,
        seat,
        episode_ctx=episode_ctx,
        client=None,
        dry_run=True,
    )

    assert decision.action == acts[0]
    assert decision.why is None
    assert decision.history == []
