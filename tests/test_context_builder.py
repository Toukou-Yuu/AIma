"""context/builders.py 覆盖测试：ContextBuilder / scope / token budget."""

from __future__ import annotations

from types import SimpleNamespace

from agents.pipeline import AgentPipeline
from context.builders import ContextBuilder
from context.compression import CompressionEngine
from context.event_projector import EventFilterConfig, EventProjector
from context.events import ContextEvent as V4ContextEvent
from context.schema import ContextSpec
from context.token_budget import TokenBudgetConfig, TokenBudgetManager
from llm.agent.context_store import ContextEvent

# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------


def _event(
    turn: int = 1,
    action_kind: str = "discard",
    action_text: str = "打1m",
    why: str | None = None,
    legal: int = 4,
    riichi_players: tuple[int, ...] = (),
    scores: tuple[int, ...] = (25000, 25000, 25000, 25000),
    **kw,
) -> ContextEvent:
    return ContextEvent(
        turn_index=turn,
        phase="in_round",
        action_kind=action_kind,
        action_text=action_text,
        why=why,
        legal_action_count=legal,
        riichi_players=riichi_players,
        scores=scores,
        **kw,
    )


def _events(n: int, **kw) -> list[ContextEvent]:
    return [_event(turn=i + 1, action_text=f"打{i + 1}m", **kw) for i in range(n)]


def _v4_event(hand: int, turn: int, text: str) -> V4ContextEvent:
    return V4ContextEvent(
        match_id="match_001",
        job_id="job_001",
        hand_index=hand,
        step_index=turn + 1,
        turn_index=turn,
        seat=0,
        event_type="DiscardTileEvent",
        text=text,
    )


# ===================================================================
# EventProjector: scope 过滤
# ===================================================================


def test_scope_stateless_returns_empty() -> None:
    """stateless scope 返回空列表。"""
    config = EventFilterConfig(scope="stateless")
    projector = EventProjector(config)
    evs = _events(5)
    result = projector.project(evs, current_hand_index=0, current_turn_index=3)
    assert result == []


def test_scope_per_turn_returns_current_turn() -> None:
    """per_turn scope 只返回当前 turn 的事件。"""
    config = EventFilterConfig(scope="per_turn")
    projector = EventProjector(config)
    evs = _events(10)
    result = projector.project(evs, current_hand_index=0, current_turn_index=5)
    assert len(result) == 1
    assert result[0].turn_index == 5


def test_scope_per_turn_is_limited_to_current_hand() -> None:
    """per_turn scope 不应混入其他手牌中相同 turn_index 的事件。"""
    config = EventFilterConfig(scope="per_turn")
    projector = EventProjector(config)
    evs = [
        _v4_event(hand=0, turn=0, text="old hand round begin"),
        _v4_event(hand=0, turn=1, text="old hand discard"),
        _v4_event(hand=1, turn=0, text="current hand round begin"),
    ]

    result = projector.project(evs, current_hand_index=1, current_turn_index=0)

    assert [ev.text for ev in result] == ["current hand round begin"]


def test_scope_per_hand_returns_all() -> None:
    """per_hand scope 返回所有事件（当前手牌）。"""
    config = EventFilterConfig(scope="per_hand")
    projector = EventProjector(config)
    evs = _events(5)
    result = projector.project(evs, current_hand_index=0, current_turn_index=3)
    assert len(result) == 5


def test_scope_per_match_returns_all() -> None:
    """per_match scope 返回所有事件。"""
    config = EventFilterConfig(scope="per_match")
    projector = EventProjector(config)
    evs = _events(5)
    result = projector.project(evs, current_hand_index=0, current_turn_index=3)
    assert len(result) == 5


def test_max_events_limit() -> None:
    """max_events 限制返回数量。"""
    config = EventFilterConfig(scope="per_match", max_events=3)
    projector = EventProjector(config)
    evs = _events(10)
    result = projector.project(evs, current_hand_index=0, current_turn_index=5)
    assert len(result) == 3
    # 保留最近的事件
    assert result[0].turn_index == 8


# ===================================================================
# CompressionEngine: 压缩策略
# ===================================================================


def test_compression_none() -> None:
    """compression='none' 渲染全部事件。"""
    engine = CompressionEngine(mode="none", budget=0)
    evs = _events(3)
    result = engine.compress(evs, detailed=True)
    assert result.rendered_event_count == 3
    assert "第1巡" in result.text
    assert "第3巡" in result.text
    assert result.compression_mode == "none"


def test_compression_snip() -> None:
    """compression='snip' 省略超出预算的事件。"""
    engine = CompressionEngine(mode="snip", budget=2)
    evs = _events(5)
    result = engine.compress(evs, detailed=False)
    assert result.snipped_event_count == 3
    assert result.rendered_event_count == 2
    assert "已省略" in result.text


def test_compression_collapse() -> None:
    """compression='collapse' 折叠较早记录。"""
    engine = CompressionEngine(mode="collapse", budget=4)
    evs = _events(10)
    result = engine.compress(evs, detailed=False)
    assert result.collapsed_event_count > 0
    assert "已折叠" in result.text


def test_compression_autocompact_stub() -> None:
    """compression='autocompact' stub 实现（等同 collapse）。"""
    engine = CompressionEngine(mode="autocompact", budget=4)
    evs = _events(10)
    result = engine.compress(evs, detailed=False)
    assert result.compression_mode == "autocompact"
    # stub 状态下行为与 collapse 类似
    assert result.collapsed_event_count > 0


# ===================================================================
# TokenBudgetManager: token 截断
# ===================================================================


def test_token_budget_no_truncation_needed() -> None:
    """文本未超预算时不截断。"""
    config = TokenBudgetConfig(max_tokens=1000)
    manager = TokenBudgetManager(config)
    text = "短文本"
    result = manager.truncate(text)
    assert result.prompt_truncated is False
    assert result.text == text


def test_token_budget_truncation_needed() -> None:
    """文本超预算时截断。"""
    config = TokenBudgetConfig(max_tokens=50)
    manager = TokenBudgetManager(config)
    # 创建长文本
    lines = [f"第{i}巡: 打{i}m 理由很长很长很长" for i in range(20)]
    text = "\n".join(lines)
    result = manager.truncate(text)
    assert result.prompt_truncated is True
    assert len(result.text) < len(text)


def test_token_budget_preserves_recent() -> None:
    """截断时保留最近内容。"""
    config = TokenBudgetConfig(max_tokens=30)  # 减小预算以触发截断
    manager = TokenBudgetManager(config)
    # 创建足够长的文本以超过预算
    lines = [f"第{i}巡: 打{i}m 理由说明详细" for i in range(20)]
    text = "\n".join(lines)
    result = manager.truncate(text)
    # 截断时应该保留最近的行
    assert result.prompt_truncated is True
    # 最近的高编号巡应该在结果中（第18巡或第19巡或第20巡）
    assert any(f"第{i}巡" in result.text for i in range(15, 21)) or "截断" in result.text


def test_token_budget_empty_text() -> None:
    """空文本不截断。"""
    config = TokenBudgetConfig(max_tokens=100)
    manager = TokenBudgetManager(config)
    result = manager.truncate("")
    assert result.prompt_truncated is False
    assert result.text == ""


# ===================================================================
# ContextBuilder: 集成测试
# ===================================================================


def test_builder_stateless_scope() -> None:
    """stateless scope 返回空历史。"""
    spec = ContextSpec(scope="stateless")
    builder = ContextBuilder(spec)
    evs = _events(10)
    result = builder.build(evs, current_hand_index=0, current_turn_index=5)
    assert result.text == ""
    assert result.raw_event_count == 0


def test_builder_per_turn_scope() -> None:
    """per_turn scope 只包含当前 turn。"""
    spec = ContextSpec(scope="per_turn")
    builder = ContextBuilder(spec)
    evs = _events(10)
    result = builder.build(evs, current_hand_index=0, current_turn_index=5)
    assert result.raw_event_count == 1
    assert "第5巡" in result.text


def test_agent_pipeline_build_context_uses_latest_turn_in_current_hand() -> None:
    """AgentPipeline 调 ContextBuilder 时应传入当前手牌内最新 turn_index。"""
    spec = ContextSpec(scope="per_turn")
    builder = ContextBuilder(spec)
    pipeline = AgentPipeline(SimpleNamespace(context=builder))
    ctx = SimpleNamespace(
        hand_index=1,
        seat=0,
        event_history=(
            _v4_event(hand=0, turn=3, text="previous hand latest"),
            _v4_event(hand=1, turn=0, text="current hand round begin"),
        ),
    )

    result = pipeline._build_context(ctx)

    assert result.raw_event_count == 1
    assert "current hand round begin" in result.text
    assert "previous hand latest" not in result.text


def test_builder_per_hand_scope() -> None:
    """per_hand scope 包含当前手牌所有事件。"""
    spec = ContextSpec(scope="per_hand")
    builder = ContextBuilder(spec)
    evs = _events(5)
    result = builder.build(evs, current_hand_index=0, current_turn_index=3)
    assert result.raw_event_count == 5


def test_builder_per_match_scope() -> None:
    """per_match scope 包含全部事件。"""
    spec = ContextSpec(scope="per_match")
    builder = ContextBuilder(spec)
    evs = _events(5)
    result = builder.build(evs, current_hand_index=0, current_turn_index=3)
    assert result.raw_event_count == 5


def test_builder_with_compression() -> None:
    """compression='snip' 时 max_events 同时控制过滤和 compression budget。

    当 max_events=N 时：
    - EventProjector 过滤到 N 个事件
    - CompressionEngine budget=N，对这 N 个事件做 compression

    所以 snipped_event_count 记录的是 compression 阶段的省略，不是 EventProjector 的过滤。
    """
    # 测试 compression 的 snip 功能：使用较大 max_events 让更多事件传入 compression
    # compression budget = max_events = 10，事件数 = 15
    spec = ContextSpec(scope="per_match", compression="snip", max_events=10)
    builder = ContextBuilder(spec)
    evs = _events(15)  # 15 个原始事件
    result = builder.build(evs, current_hand_index=0, current_turn_index=5)
    # EventProjector 过滤 15 -> 10
    # CompressionEngine snip budget=10，events=10，snipped=0（无额外省略）
    assert result.raw_event_count == 10  # 被 EventProjector 过滤后的数量
    assert result.snipped_event_count == 0  # compression budget 与 filtered 数量相同


def test_builder_with_token_budget() -> None:
    """token budget 截断时 prompt_truncated=True。"""
    spec = ContextSpec(scope="per_match")
    builder = ContextBuilder(spec, token_budget=50)
    evs = _events(20)
    result = builder.build(evs, current_hand_index=0, current_turn_index=10)
    assert result.prompt_truncated is True


def test_builder_no_truncation_without_budget() -> None:
    """无 token budget 时不截断。"""
    spec = ContextSpec(scope="per_match")
    builder = ContextBuilder(spec, token_budget=0)
    evs = _events(5)
    result = builder.build(evs, current_hand_index=0, current_turn_index=3)
    assert result.prompt_truncated is False


def test_builder_build_empty() -> None:
    """build_empty 返回空上下文。"""
    spec = ContextSpec(scope="stateless")
    builder = ContextBuilder(spec)
    result = builder.build_empty()
    assert result.text == ""
    assert result.raw_event_count == 0
    assert result.prompt_truncated is False


def test_builder_different_scopes_different_history() -> None:
    """不同 scope 产生不同 history。"""
    evs = _events(10)

    # stateless: 无历史
    spec_stateless = ContextSpec(scope="stateless")
    builder_stateless = ContextBuilder(spec_stateless)
    result_stateless = builder_stateless.build(evs, current_hand_index=0, current_turn_index=5)
    assert result_stateless.raw_event_count == 0

    # per_turn: 只有当前 turn
    spec_per_turn = ContextSpec(scope="per_turn")
    builder_per_turn = ContextBuilder(spec_per_turn)
    result_per_turn = builder_per_turn.build(evs, current_hand_index=0, current_turn_index=5)
    assert result_per_turn.raw_event_count == 1

    # per_hand: 当前手牌全部
    spec_per_hand = ContextSpec(scope="per_hand")
    builder_per_hand = ContextBuilder(spec_per_hand)
    result_per_hand = builder_per_hand.build(evs, current_hand_index=0, current_turn_index=5)
    assert result_per_hand.raw_event_count == 10

    # per_match: 全部
    spec_per_match = ContextSpec(scope="per_match")
    builder_per_match = ContextBuilder(spec_per_match)
    result_per_match = builder_per_match.build(evs, current_hand_index=0, current_turn_index=5)
    assert result_per_match.raw_event_count == 10


# ===================================================================
# 导入别名测试
# ===================================================================


def test_import_from_builder_alias() -> None:
    """from context.builder import ContextBuilder 可用。"""
    from context.builder import BuiltContext, ContextBuilder

    assert ContextBuilder is not None
    assert BuiltContext is not None
