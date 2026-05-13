"""prompt_builder.py 覆盖测试：build_system_prompt / build_*_decision_prompt / build_turn_state_message。"""

from __future__ import annotations

import json

import pytest

from kernel.api.legal_actions import LegalAction
from kernel.engine.actions import ActionKind
from kernel.tiles.model import Suit, Tile
from llm.agent.memory import PlayerMemory
from llm.agent.profile import PlayerProfile
from llm.agent.prompt_builder import (
    build_compressed_decision_prompt,
    build_delta_decision_prompt,
    build_system_prompt,
    build_turn_state_message,
)
from llm.agent.stats import PlayerStats


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _profile(**kw) -> PlayerProfile:
    defaults = dict(
        id="test", name="Test", model="gpt-4o-mini",
        provider="openai", temperature=0.7, max_tokens=1024,
        timeout_sec=120.0, persona_prompt="", strategy_prompt="",
    )
    defaults.update(kw)
    return PlayerProfile(**defaults)


def _observation_minimal():
    """构造最小 Observation 供 prompt_builder 使用。"""
    from collections import Counter
    from kernel.api.observation import Observation
    from kernel.engine.phase import GamePhase
    return Observation(
        seat=0, dealer_seat=0, phase=GamePhase.IN_ROUND,
        hand=Counter({Tile(Suit.MAN, 1, False): 1}),
        melds=(), all_melds=((), (), (), ()),
        river=(), dora_indicators=(), ura_indicators=None,
        riichi_state=(False, False, False, False),
        scores=(25000, 25000, 25000, 25000), honba=0, kyoutaku=0,
        turn_seat=0, last_discard=None, last_discard_seat=None,
        wall_remaining=None, dead_wall=None, hands_by_seat=None,
    )


def _legal_actions_minimal():
    t = Tile(Suit.MAN, 1, False)
    return (LegalAction(kind=ActionKind.DISCARD, seat=0, tile=t, declare_riichi=False),)


# ===================================================================
# build_system_prompt
# ===================================================================


def test_build_system_prompt_basic() -> None:
    """只传 system_prompt 时返回原始提示。"""
    text = build_system_prompt(system_prompt="你是麻将牌手")
    assert text == "你是麻将牌手"


def test_build_system_prompt_no_system_prompt_raises() -> None:
    """未提供 system_prompt 时抛出 ValueError。"""
    with pytest.raises(ValueError, match="未配置 system_prompt"):
        build_system_prompt()


def test_build_system_prompt_with_persona() -> None:
    """含 persona 时注入人格段。"""
    prof = _profile(persona_prompt="我是激进牌手")
    text = build_system_prompt(profile=prof, system_prompt="基础")
    assert "【人格】" in text
    assert "我是激进牌手" in text


def test_build_system_prompt_with_strategy() -> None:
    """含 strategy 时注入策略段。"""
    prof = _profile(strategy_prompt="优先做清一色")
    text = build_system_prompt(profile=prof, system_prompt="基础")
    assert "【策略】" in text
    assert "优先做清一色" in text


def test_build_system_prompt_with_memory() -> None:
    """含 memory 且有内容时注入历史表现段。"""
    mem = PlayerMemory(play_bias="defensive", recent_patterns=["注意安全"])
    text = build_system_prompt(memory=mem, system_prompt="基础")
    assert "【历史表现】" in text
    assert "偏向防守" in text


def test_build_system_prompt_with_neutral_empty_memory() -> None:
    """memory 为 neutral 且无 patterns 时不注入。"""
    mem = PlayerMemory(play_bias="neutral", recent_patterns=[])
    text = build_system_prompt(memory=mem, system_prompt="基础")
    assert "【历史表现】" not in text


def test_build_system_prompt_with_stats() -> None:
    """含 stats 且 total_games>0 时注入统计段。"""
    stats = PlayerStats(total_games=5, total_hands=40, wins=10)
    text = build_system_prompt(stats=stats, system_prompt="基础")
    assert "【统计数据】" in text
    assert "累计对局" in text


def test_build_system_prompt_with_zero_games_stats() -> None:
    """stats.total_games=0 时不注入统计段。"""
    stats = PlayerStats(total_games=0)
    text = build_system_prompt(stats=stats, system_prompt="基础")
    assert "【统计数据】" not in text


def test_build_system_prompt_full_combination() -> None:
    """所有参数组合注入所有段。"""
    prof = _profile(persona_prompt="人设", strategy_prompt="策略")
    mem = PlayerMemory(play_bias="aggressive", recent_patterns=["模式"])
    stats = PlayerStats(total_games=10, total_hands=80, wins=20)
    text = build_system_prompt(
        profile=prof, memory=mem, stats=stats, system_prompt="基础",
    )
    assert "基础" in text
    assert "【人格】" in text
    assert "【策略】" in text
    assert "【历史表现】" in text
    assert "【统计数据】" in text


# ===================================================================
# build_compressed_decision_prompt
# ===================================================================


def test_build_compressed_decision_prompt_returns_json() -> None:
    """返回合法 JSON 且含 observation / legal_actions。"""
    obs = _observation_minimal()
    actions = _legal_actions_minimal()
    text = build_compressed_decision_prompt(obs, actions)
    body = json.loads(text.split("\n\n【输出要求】")[0])
    assert "observation" in body
    assert "legal_actions" in body
    assert len(body["legal_actions"]) == 1


def test_build_compressed_decision_prompt_has_format_hint() -> None:
    """输出含格式说明。"""
    obs = _observation_minimal()
    text = build_compressed_decision_prompt(obs, _legal_actions_minimal())
    assert "【输出要求】" in text
    assert "why" in text


# ===================================================================
# build_delta_decision_prompt
# ===================================================================


def test_build_delta_decision_prompt_returns_json() -> None:
    """返回合法 JSON 且含 frame_type=delta。"""
    delta = {"changed": True}
    actions = _legal_actions_minimal()
    text = build_delta_decision_prompt(delta, actions)
    body = json.loads(text.split("\n\n【输出要求】")[0])
    assert body["frame_type"] == "delta"
    assert body["delta"] == {"changed": True}
    assert len(body["legal_actions"]) == 1


def test_build_delta_decision_prompt_has_format_hint() -> None:
    """输出含格式说明。"""
    text = build_delta_decision_prompt({}, _legal_actions_minimal())
    assert "【输出要求】" in text


# ===================================================================
# build_turn_state_message
# ===================================================================


def test_build_turn_state_message_with_public_summary() -> None:
    """含 public_summary 时展示公开事件摘要。"""
    msg = build_turn_state_message(
        base_prompt="请决策", public_summary="家1立直了",
    )
    assert "【公开事件摘要】" in msg
    assert "家1立直了" in msg
    assert "【当前决策】" in msg
    assert "请决策" in msg


def test_build_turn_state_message_without_public_summary() -> None:
    """无 public_summary 时只有当前决策。"""
    msg = build_turn_state_message(base_prompt="请决策")
    assert "【公开事件摘要】" not in msg
    assert "【当前决策】" in msg
    assert "请决策" in msg
