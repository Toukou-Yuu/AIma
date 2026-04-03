"""唯一 ``pass_call`` 时跳过 LLM 请求。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import ActionKind
from llm.runner import choose_legal_action


def test_singleton_pass_call_does_not_invoke_client() -> None:
    client = MagicMock()
    client.complete.side_effect = AssertionError("complete should not be called")
    lone = (LegalAction(kind=ActionKind.PASS_CALL, seat=2),)
    with patch("llm.runner.legal_actions", return_value=lone):
        la, why, history = choose_legal_action(
            MagicMock(),
            2,
            client=client,
            dry_run=False,
            session_audit=False,
        )
    assert why is None
    assert la.kind == ActionKind.PASS_CALL
    assert la.seat == 2
    assert history == []  # 未调用 API 时历史为空列表
    client.complete.assert_not_called()


def test_pass_and_ron_still_invokes_client() -> None:
    from kernel.tiles import Tile
    from kernel.tiles.model import Suit

    client = MagicMock(return_value='{"kind":"pass_call","seat":1}')
    t = Tile(Suit.HONOR, 1, False)
    acts = (
        LegalAction(kind=ActionKind.PASS_CALL, seat=1),
        LegalAction(kind=ActionKind.RON, seat=1, tile=t),
    )
    with (
        patch("llm.runner.legal_actions", return_value=acts),
        patch("llm.runner.observation", return_value=MagicMock()),
        patch("llm.runner.build_user_prompt", return_value="{}"),
    ):
        la, why, history = choose_legal_action(
            MagicMock(),
            1,
            client=client,
            dry_run=False,
            session_audit=False,
        )
    assert la == acts[0]
    assert isinstance(history, list)
    client.complete.assert_called_once()
