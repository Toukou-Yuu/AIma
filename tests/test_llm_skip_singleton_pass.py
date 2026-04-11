"""唯一 pass_call 或 draw 时跳过 LLM 请求。"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import ActionKind
from llm.agent import PlayerAgent
from llm.agent.context import EpisodeContext


def test_singleton_pass_call_does_not_invoke_client() -> None:
    """测试唯一合法动作是 PASS_CALL 时跳过 LLM 请求。"""
    client = MagicMock()
    client.complete.side_effect = AssertionError("complete should not be called")

    agent = PlayerAgent(system_prompt="你是麻将牌手")
    episode_ctx = EpisodeContext(2)

    lone = (LegalAction(kind=ActionKind.PASS_CALL, seat=2),)

    # 由于 kernel.api/__init__.py 导入了 legal_actions，
    # kernel.api.legal_actions 被覆盖为函数，无法用标准 patch
    # 需要直接从 sys.modules 获取真正的模块
    real_module = sys.modules["kernel.api.legal_actions"]
    with patch.object(real_module, "legal_actions", return_value=lone):
        decision = agent.decide(
            MagicMock(),
            2,
            episode_ctx=episode_ctx,
            client=client,
            dry_run=False,
        )

    assert decision.why is None
    assert decision.action.kind == ActionKind.PASS_CALL
    assert decision.action.seat == 2
    assert decision.history == []  # 未调用 API 时历史为空列表
    client.complete.assert_not_called()


def test_singleton_draw_does_not_invoke_client() -> None:
    """测试唯一合法动作是 DRAW 时跳过 LLM 请求。"""
    client = MagicMock()
    client.complete.side_effect = AssertionError("complete should not be called")

    agent = PlayerAgent(system_prompt="你是麻将牌手")
    episode_ctx = EpisodeContext(0)

    lone = (LegalAction(kind=ActionKind.DRAW, seat=0),)

    real_module = sys.modules["kernel.api.legal_actions"]
    with patch.object(real_module, "legal_actions", return_value=lone):
        decision = agent.decide(
            MagicMock(),
            0,
            episode_ctx=episode_ctx,
            client=client,
            dry_run=False,
        )

    assert decision.why is None
    assert decision.action.kind == ActionKind.DRAW
    client.complete.assert_not_called()


def test_pass_and_ron_still_invokes_client() -> None:
    """测试有多个合法动作时仍会调用 LLM。"""
    from kernel.tiles import Tile
    from kernel.tiles.model import Suit

    t = Tile(Suit.HONOR, 1, False)
    acts = (
        LegalAction(kind=ActionKind.PASS_CALL, seat=1),
        LegalAction(kind=ActionKind.RON, seat=1, tile=t),
    )

    # 返回 JSON 让 Agent 选择 PASS_CALL
    client = MagicMock(return_value='{"kind":"pass_call","seat":1}')

    agent = PlayerAgent(system_prompt="你是麻将牌手")
    episode_ctx = EpisodeContext(1)

    # 创建一个可以被 JSON 序列化的 observation mock
    mock_obs = MagicMock()
    mock_obs.hand = None  # 使 build_compressed_observation 不出错

    real_la_module = sys.modules["kernel.api.legal_actions"]
    real_obs_module = sys.modules["kernel.api.observation"]

    # 需要也 mock build_compressed_observation
    with (
        patch.object(real_la_module, "legal_actions", return_value=acts),
        patch.object(real_obs_module, "observation", return_value=mock_obs),
        patch("llm.observation_format.build_compressed_observation", return_value={"hand": "mock"}),
    ):
        decision = agent.decide(
            MagicMock(),
            1,
            episode_ctx=episode_ctx,
            client=client,
            dry_run=False,
        )

    assert decision.action == acts[0]
    assert isinstance(decision.history, list)
    client.complete.assert_called_once()