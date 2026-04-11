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


class _ScriptedClient:
    """始终返回预先序列化的合法动作 JSON。"""

    def __init__(self, payload: str) -> None:
        self._payload = payload

    def complete(
        self,
        messages: list[object],
        *,
        model: str | None = None,
        session_id: str | None = None,
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

    agent = PlayerAgent(system_prompt="你是麻将牌手")
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

    agent = PlayerAgent(system_prompt="你是麻将牌手")
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

    agent = PlayerAgent()
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


def test_agent_session_id_unique() -> None:
    """测试不同 Agent 实例有不同的 session_id（会话隔离）。"""
    import time

    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=14))
    state = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    seat = pending_actor_seats(state)[0]
    acts = legal_actions(state, seat)

    wire = dict(legal_action_to_wire(acts[0]))
    payload = json.dumps(wire, ensure_ascii=False)

    # 使用 MockClient 记录 session_id
    class _SessionTrackingClient:
        def __init__(self, payload: str) -> None:
            self._payload = payload
            self.session_ids: list[str] = []

        def complete(
            self,
            messages: list[object],
            *,
            model: str | None = None,
            session_id: str | None = None,
        ) -> str:
            if session_id:
                self.session_ids.append(session_id)
            return self._payload

    client = _SessionTrackingClient(payload)

    # 创建两个不同的 Agent 实例（会话隔离）
    agent1 = PlayerAgent(system_prompt="你是麻将牌手")
    agent2 = PlayerAgent(system_prompt="你是麻将牌手")

    # 两个不同实例应该有不同的 session_id
    episode_ctx1 = EpisodeContext(seat)
    agent1.decide(state, seat, episode_ctx=episode_ctx1, client=client, dry_run=False)

    episode_ctx2 = EpisodeContext(seat)
    agent2.decide(state, seat, episode_ctx=episode_ctx2, client=client, dry_run=False)

    # 两个 session_id 应不同（不同实例）
    assert len(client.session_ids) == 2
    assert client.session_ids[0] != client.session_ids[1]
    # 验证 session_id 格式
    assert client.session_ids[0].startswith("majiang_player_")
    assert client.session_ids[1].startswith("majiang_player_")


def test_agent_same_instance_same_session_id() -> None:
    """测试同一 Agent 实例多次调用使用相同的 session_id（对话历史连续）。"""
    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=15))
    state = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    seat = pending_actor_seats(state)[0]
    acts = legal_actions(state, seat)

    wire = dict(legal_action_to_wire(acts[0]))
    payload = json.dumps(wire, ensure_ascii=False)

    # 使用 MockClient 记录 session_id
    class _SessionTrackingClient:
        def __init__(self, payload: str) -> None:
            self._payload = payload
            self.session_ids: list[str] = []

        def complete(
            self,
            messages: list[object],
            *,
            model: str | None = None,
            session_id: str | None = None,
        ) -> str:
            if session_id:
                self.session_ids.append(session_id)
            return self._payload

    client = _SessionTrackingClient(payload)
    agent = PlayerAgent(system_prompt="你是麻将牌手")

    # 同一实例多次调用应该使用相同的 session_id
    episode_ctx1 = EpisodeContext(seat)
    agent.decide(state, seat, episode_ctx=episode_ctx1, client=client, dry_run=False)

    episode_ctx2 = EpisodeContext(seat)
    agent.decide(state, seat, episode_ctx=episode_ctx2, client=client, dry_run=False)

    # 两个 session_id 应相同（同一实例保持对话历史）
    assert len(client.session_ids) == 2
    assert client.session_ids[0] == client.session_ids[1]
    assert client.session_ids[0].startswith("majiang_player_")