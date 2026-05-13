"""context_store.py 覆盖测试：ContextEvent / BudgetManager / CompressionPipeline。"""

from __future__ import annotations

from llm.agent.context_store import (
    BudgetManager,
    CompressionPipeline,
    ContextEvent,
    ContextStore,
    HistoryProjection,
)


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


# ===================================================================
# ContextEvent.is_key_event
# ===================================================================


def test_is_key_event_ron() -> None:
    """ron 属于关键事件。"""
    assert _event(action_kind="ron", action_text="荣和").is_key_event


def test_is_key_event_tsumo() -> None:
    """tsumo 属于关键事件。"""
    assert _event(action_kind="tsumo", action_text="自摸").is_key_event


def test_is_key_event_open_meld() -> None:
    """open_meld 属于关键事件。"""
    assert _event(action_kind="open_meld", action_text="吃三筒").is_key_event


def test_is_key_event_ankan() -> None:
    """ankan 属于关键事件。"""
    assert _event(action_kind="ankan", action_text="暗杠1m").is_key_event


def test_is_key_event_shankuminkan() -> None:
    """shankuminkan 属于关键事件。"""
    assert _event(action_kind="shankuminkan", action_text="加杠5m").is_key_event


def test_is_key_event_riichi_in_text() -> None:
    """action_text 含"立直"即为关键事件。"""
    assert _event(action_kind="discard", action_text="打3m立直宣言").is_key_event


def test_is_key_event_normal_discard() -> None:
    """普通丢牌不是关键事件。"""
    ev = _event(action_kind="discard", action_text="打1m")
    assert not ev.is_key_event


# ===================================================================
# BudgetManager.recent_tail_budget
# ===================================================================


def test_recent_tail_budget_zero() -> None:
    """budget=0 时尾部为 0。"""
    bm = BudgetManager(0)
    assert bm.recent_tail_budget() == 0


def test_recent_tail_budget_one() -> None:
    """budget=1 时尾部为 1。"""
    bm = BudgetManager(1)
    assert bm.recent_tail_budget() == 1


def test_recent_tail_budget_even() -> None:
    """budget=6 时尾部为 3。"""
    bm = BudgetManager(6)
    assert bm.recent_tail_budget() == 3


def test_recent_tail_budget_odd() -> None:
    """budget=5 时尾部为 max(1, 5//2)=2。"""
    bm = BudgetManager(5)
    assert bm.recent_tail_budget() == 2


def test_recent_tail_budget_two() -> None:
    """budget=2 时尾部为 max(1, 1)=1。"""
    bm = BudgetManager(2)
    assert bm.recent_tail_budget() == 1


def test_budget_manager_char_budget() -> None:
    """history_budget>0 时 char_budget=max(240, budget*120)。"""
    bm = BudgetManager(1)
    assert bm.char_budget == 240  # max(240, 120)
    bm2 = BudgetManager(5)
    assert bm2.char_budget == 600  # max(240, 600)


def test_budget_manager_char_budget_zero() -> None:
    """history_budget=0 时 char_budget=0。"""
    bm = BudgetManager(0)
    assert bm.char_budget == 0


# ===================================================================
# CompressionPipeline: project 入口分支
# ===================================================================


def test_project_empty_events() -> None:
    """空事件列表返回空投影。"""
    pipe = CompressionPipeline(history_budget=4, compression_level="none")
    proj = pipe.project([], detailed=True)
    assert proj.text == ""
    assert proj.raw_event_count == 0
    assert proj.rendered_event_count == 0


def test_project_zero_budget() -> None:
    """budget=0 返回空投影。"""
    pipe = CompressionPipeline(history_budget=0, compression_level="none")
    proj = pipe.project(_events(3), detailed=True)
    assert proj.text == ""
    assert proj.rendered_event_count == 0


def test_project_none_level() -> None:
    """compression_level='none' 渲染全部事件。"""
    pipe = CompressionPipeline(history_budget=10, compression_level="none")
    evs = _events(3)
    proj = pipe.project(evs, detailed=True)
    assert proj.rendered_event_count == 3
    assert "第1巡" in proj.text
    assert "第3巡" in proj.text


# ===================================================================
# _snip
# ===================================================================


def test_snip_within_budget() -> None:
    """事件数未超预算，不省略。"""
    pipe = CompressionPipeline(history_budget=5, compression_level="snip")
    proj = pipe.project(_events(3), detailed=False)
    assert proj.snipped_event_count == 0
    assert proj.rendered_event_count == 3
    assert "已省略" not in proj.text


def test_snip_exceeds_budget() -> None:
    """事件数超出预算，省略较早记录。"""
    pipe = CompressionPipeline(history_budget=2, compression_level="snip")
    proj = pipe.project(_events(5), detailed=False)
    assert proj.snipped_event_count == 3
    assert proj.rendered_event_count == 2
    assert "已省略 3 条较早记录" in proj.text
    assert "第5巡" in proj.text


def test_snip_detailed_mode() -> None:
    """detailed=True 渲染详细信息。"""
    pipe = CompressionPipeline(history_budget=2, compression_level="snip")
    ev = _event(turn=1, why="安全牌", legal=5, riichi_players=(1,))
    proj = pipe.project([ev], detailed=True)
    assert "理由" in proj.text
    assert "候选5项" in proj.text
    assert "立直家=家1" in proj.text


# ===================================================================
# _microcompact
# ===================================================================


def test_microcompact_truncates_and_clips() -> None:
    """micro 模式截断并裁剪每行。"""
    pipe = CompressionPipeline(history_budget=2, compression_level="micro")
    evs = _events(4)
    proj = pipe.project(evs, detailed=True)
    assert proj.snipped_event_count == 2
    assert "已截断" in proj.text


def test_microcompact_within_budget() -> None:
    """micro 模式下事件未超预算不截断。"""
    pipe = CompressionPipeline(history_budget=5, compression_level="micro")
    evs = _events(3)
    proj = pipe.project(evs, detailed=True)
    assert proj.snipped_event_count == 0


# ===================================================================
# _collapse
# ===================================================================


def test_collapse_within_budget() -> None:
    """事件数不超过 budget 时不折叠。"""
    pipe = CompressionPipeline(history_budget=5, compression_level="collapse")
    evs = _events(4)
    proj = pipe.project(evs, detailed=False)
    assert proj.collapsed_event_count == 0
    assert proj.rendered_event_count == 4


def test_collapse_exceeds_budget() -> None:
    """事件数超出 budget 时折叠较早记录。"""
    pipe = CompressionPipeline(history_budget=4, compression_level="collapse")
    evs = _events(8)
    proj = pipe.project(evs, detailed=False)
    assert proj.collapsed_event_count > 0
    assert "已折叠" in proj.text


def test_collapse_with_key_events_and_riichi() -> None:
    """折叠时展示关键事件和立直威胁家。"""
    older = [
        _event(turn=1, action_kind="discard", action_text="打1m"),
        _event(turn=2, action_kind="open_meld", action_text="吃三筒"),
        _event(turn=3, action_kind="discard", action_text="打3m立直宣言", riichi_players=(0,)),
    ]
    recent = [_event(turn=4, action_kind="discard", action_text="打4m")]
    pipe = CompressionPipeline(history_budget=2, compression_level="collapse")
    proj = pipe.project(older + recent, detailed=False)
    assert proj.collapsed_event_count == 3
    assert "关键事件" in proj.text
    assert "威胁家" in proj.text


# ===================================================================
# _autocompact
# ===================================================================


def test_autocompact_basic() -> None:
    """autocompact 生成高密度折叠摘要。"""
    evs = _events(6, why="理由")
    pipe = CompressionPipeline(history_budget=4, compression_level="autocompact")
    proj = pipe.project(evs, detailed=False)
    assert "本局已记录 6 次自家决策" in proj.text
    assert proj.collapsed_event_count > 0


def test_autocompact_with_key_events() -> None:
    """autocompact 中包含关键事件摘要。"""
    evs = [
        _event(turn=1, action_kind="ron", action_text="荣和", why="和了"),
        _event(turn=2, action_kind="discard", action_text="打1m"),
        _event(turn=3, action_kind="discard", action_text="打2m"),
        _event(turn=4, action_kind="discard", action_text="打3m"),
    ]
    pipe = CompressionPipeline(history_budget=2, compression_level="autocompact")
    proj = pipe.project(evs, detailed=False)
    assert "高密度摘要" in proj.text


def test_autocompact_no_key_events() -> None:
    """无关键事件时不高亮摘要。"""
    evs = _events(6)  # 全是普通 discard
    pipe = CompressionPipeline(history_budget=2, compression_level="autocompact")
    proj = pipe.project(evs, detailed=False)
    assert "高密度摘要" not in proj.text


def test_autocompact_with_reasons() -> None:
    """有 why 字段时展示长期倾向。"""
    evs = [_event(turn=i + 1, why=f"理由{i}") for i in range(6)]
    pipe = CompressionPipeline(history_budget=2, compression_level="autocompact")
    proj = pipe.project(evs, detailed=False)
    assert "长期倾向" in proj.text


def test_autocompact_no_reasons() -> None:
    """无 why 字段时不展示长期倾向。"""
    evs = _events(6)  # why=None
    pipe = CompressionPipeline(history_budget=2, compression_level="autocompact")
    proj = pipe.project(evs, detailed=False)
    assert "长期倾向" not in proj.text


def test_autocompact_small_budget_uses_one_tail() -> None:
    """budget<=2 时 autocompact 只保留最后 1 条。"""
    evs = _events(4)
    pipe = CompressionPipeline(history_budget=2, compression_level="autocompact")
    proj = pipe.project(evs, detailed=False)
    assert proj.rendered_event_count == 1


# ===================================================================
# _collapse_events
# ===================================================================


def test_collapse_events_with_key_and_threat() -> None:
    """_collapse_events 同时含关键事件与威胁家。"""
    pipe = CompressionPipeline(history_budget=1, compression_level="collapse")
    evs = [
        _event(turn=1, action_kind="ron", action_text="荣和"),
        _event(turn=2, action_kind="discard", action_text="打2m", riichi_players=(1, 3)),
    ]
    lines = pipe._collapse_events(evs)
    text = "\n".join(lines)
    assert "较早 2 条记录已折叠" in text
    assert "关键事件" in text
    assert "威胁家" in text
    assert "家1" in text and "家3" in text


def test_collapse_events_no_key_no_threat() -> None:
    """无关键事件和威胁家时只显示折叠标题。"""
    pipe = CompressionPipeline(history_budget=1, compression_level="collapse")
    evs = [_event(turn=1, action_kind="discard", action_text="打1m")]
    lines = pipe._collapse_events(evs)
    assert len(lines) == 1
    assert "较早 1 条记录已折叠" in lines[0]


# ===================================================================
# _render_event
# ===================================================================


def test_render_event_compact_with_reason() -> None:
    """compact 模式含 why 时带裁剪理由。"""
    pipe = CompressionPipeline(history_budget=10, compression_level="none")
    ev = _event(turn=3, why="安全牌理由")
    text = pipe._render_event(ev, detailed=False, compact=True)
    assert "第3巡" in text
    assert "安全牌理由" in text


def test_render_event_compact_no_reason() -> None:
    """compact 模式无 why 时不带额外信息。"""
    pipe = CompressionPipeline(history_budget=10, compression_level="none")
    ev = _event(turn=3)
    text = pipe._render_event(ev, detailed=False, compact=True)
    assert text == "第3巡: 打1m"


def test_render_event_detailed_full() -> None:
    """detailed=True 展示全部信息。"""
    pipe = CompressionPipeline(history_budget=10, compression_level="none")
    ev = _event(
        turn=5,
        why="理由",
        legal=6,
        riichi_players=(2,),
        last_discard="3m",
        last_discard_seat=1,
    )
    text = pipe._render_event(ev, detailed=True, compact=False)
    assert "理由" in text
    assert "候选6项" in text
    assert "立直家=家2" in text
    assert "末打=家1:3m" in text


def test_render_event_non_detailed_non_compact() -> None:
    """非详细非紧凑模式：含理由（裁剪短）和候选数。"""
    pipe = CompressionPipeline(history_budget=10, compression_level="none")
    ev = _event(why="理由", legal=3)
    text = pipe._render_event(ev, detailed=False, compact=False)
    assert "理由" in text
    assert "候选3项" in text
    # 非详细模式不含立直家信息
    assert "立直家" not in text


def test_render_event_no_extras() -> None:
    """无额外信息时只返回 base 文本。"""
    pipe = CompressionPipeline(history_budget=10, compression_level="none")
    ev = _event(why=None, legal=0)
    text = pipe._render_event(ev, detailed=False, compact=False)
    assert text == "第1巡: 打1m"


# ===================================================================
# ContextStore 集成
# ===================================================================


def test_context_store_append_and_project() -> None:
    """ContextStore 追加事件后可投影。"""
    store = ContextStore()
    store.append_event(_event(turn=1))
    store.append_event(_event(turn=2))
    proj = store.project_history(detailed=False, history_budget=4, compression_level="none")
    assert proj.raw_event_count == 2
    assert "第1巡" in proj.text
