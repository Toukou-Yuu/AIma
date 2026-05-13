"""match_context.py 覆盖测试：MatchContext.reset / get_stats / close_episode。"""

from __future__ import annotations

from llm.agent.context import EpisodeContext
from llm.agent.match_context import MatchContext
from llm.agent.stats import MatchStats


# ===================================================================
# MatchContext.reset
# ===================================================================


def test_reset_clears_state() -> None:
    """reset 后统计归零、局数归零。"""
    mc = MatchContext(seat=0)
    ep = mc.create_episode()
    ep.match_stats.wins = 5
    ep.match_stats.hands = 10
    ep.end_episode(3000)
    mc.close_episode(ep)

    mc.reset()
    stats = mc.get_stats()
    assert stats.wins == 0
    assert stats.hands == 0

    # reset 后可以正常创建新局
    ep2 = mc.create_episode()
    assert ep2.hand_number == 1


def test_reset_changes_match_id() -> None:
    """reset 后 match_id 变更。"""
    mc = MatchContext(seat=0)
    ep1 = mc.create_episode()
    old_id = ep1.match_id
    mc.close_episode(ep1)
    mc.reset()
    ep2 = mc.create_episode()
    # 新 match_id 应不同于旧的（概率极高）
    assert ep2.match_id != old_id


# ===================================================================
# MatchContext.get_stats
# ===================================================================


def test_get_stats_returns_copy() -> None:
    """get_stats 返回独立副本，修改不影响内部状态。"""
    mc = MatchContext(seat=0)
    ep = mc.create_episode()
    ep.match_stats.wins = 3
    mc.close_episode(ep)

    stats = mc.get_stats()
    stats.wins = 999
    assert mc.get_stats().wins == 3


def test_get_stats_initial_is_zero() -> None:
    """初始状态统计全零。"""
    mc = MatchContext(seat=0)
    stats = mc.get_stats()
    assert stats.wins == 0
    assert stats.deal_ins == 0
    assert stats.hands == 0


# ===================================================================
# MatchContext.close_episode
# ===================================================================


def test_close_episode_updates_match_stats() -> None:
    """close_episode 将局统计合并到本场统计。"""
    mc = MatchContext(seat=0)
    ep = mc.create_episode()
    ep.match_stats.wins = 1
    ep.match_stats.hands = 8
    ep.end_episode(5000)
    mc.close_episode(ep)

    stats = mc.get_stats()
    assert stats.wins == 1
    assert stats.points == 5000
    assert stats.hands == 9  # 8 + 1 from end_episode


def test_close_episode_multiple() -> None:
    """多局累积统计（create_episode 复制上一局统计）。"""
    mc = MatchContext(seat=0)

    ep1 = mc.create_episode()
    ep1.match_stats.wins = 1
    ep1.match_stats.hands = 8
    ep1.end_episode(3000)
    mc.close_episode(ep1)

    ep2 = mc.create_episode()  # copies ep1 stats: wins=1, hands=9, points=3000
    ep2.match_stats.deal_ins = 1
    ep2.end_episode(-2000)
    mc.close_episode(ep2)

    stats = mc.get_stats()
    assert stats.wins == 1
    assert stats.deal_ins == 1
    assert stats.points == 1000  # 3000 + (-2000)


def test_close_episode_with_conversation_logger() -> None:
    """close_episode 关闭 conversation_logger。"""
    mc = MatchContext(seat=0, player_id="test_player")
    ep = mc.create_episode(enable_conversation_logging=True)
    # conversation_logger 应已创建
    assert ep.conversation_logger is not None
    logger = ep.conversation_logger
    mc.close_episode(ep)
    # 关闭后应被清除
    assert ep.conversation_logger is None


def test_close_episode_without_conversation_logger() -> None:
    """无 conversation_logger 时 close_episode 正常工作。"""
    mc = MatchContext(seat=0)
    ep = mc.create_episode(enable_conversation_logging=False)
    assert ep.conversation_logger is None
    mc.close_episode(ep)  # 不抛异常


def test_close_episode_archives_hand_summary() -> None:
    """close_episode 归档局摘要。"""
    mc = MatchContext(seat=0)
    ep = mc.create_episode()
    ep.match_stats.wins = 1
    ep.end_episode(1000)
    mc.close_episode(ep)

    # 创建第二局，其 match_history_archive 应包含第一局摘要
    ep2 = mc.create_episode()
    assert len(ep2.match_history_archive) == 1
    assert "第1局" in ep2.match_history_archive[0]


# ===================================================================
# MatchContext.create_episode
# ===================================================================


def test_create_episode_increments_hand_number() -> None:
    """每次 create_episode 递增局号。"""
    mc = MatchContext(seat=0)
    ep1 = mc.create_episode()
    assert ep1.hand_number == 1
    mc.close_episode(ep1)
    ep2 = mc.create_episode()
    assert ep2.hand_number == 2


def test_create_episode_isolates_match_stats() -> None:
    """EpisodeContext 的 match_stats 是副本，不影响 MatchContext。"""
    mc = MatchContext(seat=0)
    ep = mc.create_episode()
    ep.match_stats.wins = 99
    # MatchContext 内部统计不应被影响
    assert mc.get_stats().wins == 0


def test_seat_property() -> None:
    """seat 属性只读。"""
    mc = MatchContext(seat=2)
    assert mc.seat == 2
