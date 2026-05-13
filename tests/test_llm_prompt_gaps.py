"""llm.agent.prompt 覆盖缺口测试。"""

from __future__ import annotations

from llm.agent.prompt import PromptProjector


def _make_projector(**attrs):
    """绕过构造函数创建 PromptProjector 实例。"""
    from llm.agent.session import LocalContextPolicy
    p = object.__new__(PromptProjector)
    # 设置默认属性
    defaults = {
        "compression_level": "none",
        "prompt_mode": "natural",
        "history_budget": 2000,
        "archive_budget": 0,
        "context_policy": LocalContextPolicy(scope="per_hand"),
    }
    defaults.update(attrs)
    for k, v in defaults.items():
        object.__setattr__(p, k, v)
    return p


# --- _wrap_block ---

class TestWrapBlock:
    def test_empty_body_returns_empty(self) -> None:
        """空 body → 空字符串（L285）。"""
        p = _make_projector()
        assert p._wrap_block("header", "") == ""

    def test_falsy_body_returns_empty(self) -> None:
        p = _make_projector()
        assert p._wrap_block("header", None) == ""

    def test_normal_body(self) -> None:
        p = _make_projector()
        result = p._wrap_block("标题", "内容")
        assert "标题" in result
        assert "内容" in result


# --- _build_archive_variants ---

class TestBuildArchiveVariants:
    def test_empty_content_returns_empty_tuple(self) -> None:
        """空 archive_content → ()（L280）。"""
        p = _make_projector()
        result = p._build_archive_variants("")
        assert result == ()

    def test_nonempty_content(self) -> None:
        p = _make_projector()
        result = p._build_archive_variants("一些摘要内容")
        assert len(result) == 1


# --- _should_semantic_compact ---

class TestShouldSemanticCompact:
    def test_not_autocompact_returns_false(self) -> None:
        """compression_level != autocompact → False（L157-158）。"""
        p = _make_projector(compression_level="none")

        class FakePlan:
            diagnostics = None

        assert p._should_semantic_compact(FakePlan(), None) is False

    def test_client_none_returns_false(self) -> None:
        """compaction_client=None → False（L159-160）。"""
        p = _make_projector(compression_level="autocompact")

        class FakePlan:
            class FakeDiag:
                over_budget = False
                trimmed_blocks = []
            diagnostics = FakeDiag()

        assert p._should_semantic_compact(FakePlan(), None) is False


# --- _build_semantic_compacted_history ---

class TestBuildSemanticCompactedHistory:
    def test_client_none_returns_empty(self) -> None:
        """compaction_client=None → []（L172）。"""
        from llm.agent.context import EpisodeContext
        p = _make_projector(compression_level="autocompact")
        ctx = EpisodeContext(seat=0)
        result = p._build_semantic_compacted_history(ctx, compaction_client=None)
        assert result == []

    def test_short_history_returns_empty(self) -> None:
        """turn_indexes <= 2 → []（L175）。"""
        from llm.agent.context import EpisodeContext
        p = _make_projector(compression_level="autocompact")
        ctx = EpisodeContext(seat=0)
        result = p._build_semantic_compacted_history(ctx, compaction_client=None)
        assert result == []


# --- _build_user_prompt json mode ---

class TestBuildUserPromptJsonMode:
    def test_json_mode(self) -> None:
        """prompt_mode='json' 走 build_compressed_decision_prompt 分支（L203）。"""
        from kernel.api.observation import Observation, RiverEntry
        from kernel.engine.phase import GamePhase
        from kernel.tiles.model import Suit, Tile
        from collections import Counter
        from llm.agent.context import EpisodeContext
        from llm.agent.context_store import TurnContext
        from kernel.api.legal_actions import LegalAction
        from kernel.engine.actions import ActionKind

        p = _make_projector(prompt_mode="json", context_scope="stateless")
        obs = Observation(
            seat=0, dealer_seat=0, phase=GamePhase.IN_ROUND,
            hand=Counter({Tile(Suit.MAN, 1): 2}),
            melds=(), all_melds=((), (), (), ()),
            river=(), dora_indicators=(), ura_indicators=None,
            riichi_state=(False, False, False, False),
            scores=(25000, 25000, 25000, 25000), honba=0, kyoutaku=0,
            turn_seat=0, last_discard=None, last_discard_seat=None,
            wall_remaining=70, dead_wall=None, hands_by_seat=None,
        )
        la = LegalAction(kind=ActionKind.DISCARD, tile=Tile(Suit.MAN, 1), seat=0)
        tc = TurnContext(observation=obs, legal_actions=(la,), turn_index=1)
        ctx = EpisodeContext(seat=0)
        result = p._build_user_prompt(tc, episode_ctx=ctx)
        assert isinstance(result, str)
        assert len(result) > 0
