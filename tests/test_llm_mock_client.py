"""注入 Mock ``CompletionClient`` 的跑局路径。"""

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
from llm.runner import choose_legal_action
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


def test_choose_legal_action_uses_client_json() -> None:
    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=11))
    state = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    seat = pending_actor_seats(state)[0]
    acts = legal_actions(state, seat)
    assert acts
    w = dict(legal_action_to_wire(acts[0]))
    w["why"] = "测试：固定选首项合法动作"
    payload = json.dumps(w, ensure_ascii=False)
    la, why, history = choose_legal_action(state, seat, client=_ScriptedClient(payload), dry_run=False)
    assert la == acts[0]
    assert why == "测试：固定选首项合法动作"
    assert isinstance(history, list)
    # 历史应包含 user + assistant 两条消息
    assert len(history) == 2


def test_choose_fallback_when_json_invalid() -> None:
    g0 = initial_game_state()
    w = tuple(shuffle_deck(build_deck(), seed=12))
    state = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=w)).new_state
    seat = pending_actor_seats(state)[0]
    acts = legal_actions(state, seat)
    la, why, history = choose_legal_action(state, seat, client=_ScriptedClient("not json"), dry_run=False)
    assert la == acts[0]
    assert why is None
    # 即使解析失败也应记录历史
    assert isinstance(history, list)
