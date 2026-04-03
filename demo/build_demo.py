#!/usr/bin/env python3
"""
构建包含特定场景的演示牌谱。

场景：
第1局：碰、吃、大明杠、荣和
第2局：暗杠、加杠、自摸
第3局：九连宝灯役满
第4局：流局

不修改内核规则，通过合法动作触发。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kernel import GameState, GamePhase, apply, Action, ActionKind
from kernel.engine.state import initial_game_state
from kernel.tiles.deck import build_deck, Tile
from kernel.tiles.model import Suit
from kernel.replay_json import action_to_wire, game_event_to_wire, match_log_document


def tile_from_code(deck, code):
    """从牌码获取牌。"""
    for t in deck:
        if t.to_code() == code:
            return t
    raise ValueError(f'Tile not found: {code}')


def build_specific_wall(deck, scenario):
    """构建特定场景的初始牌山。"""
    if scenario == 1:  # 碰、吃、大明杠、荣和
        # S0手牌：可以暗杠1m
        s0 = ['1m','1m','1m','2m','3m','4p','5p','6p','7s','8s','9s','1z','2z']
        # S1手牌：可以碰1m，可以吃4p5p6p
        s1 = ['1m','2m','3m','4p','5p','6p','7p','2s','3s','4s','1z','3z','5z']
        # S2手牌：等待荣和
        s2 = ['4m','5m','6m','1p','2p','3p','7p','8p','9p','5s','6s','7s','9s']
        # S3手牌：可以立直
        s3 = ['7m','8m','9m','2p','3p','4p','5p','6p','8p','9p','8s','1z','2z']

        # 构建手牌
        hands = s0 + s1 + s2 + s3
        front = [tile_from_code(deck, c) for c in hands]

        # 岭上牌（14张）
        dead_wall_codes = ['7m','3s','6z','2z','5z','1z','2z','3z','4z','5z','6z','7z','8s','9s']
        dead_wall = [tile_from_code(deck, c) for c in dead_wall_codes]

        # 剩余牌墙 - 精心安排摸牌顺序
        # S0摸1m（完成暗杠）-> S0摸5mr -> S1打1m（S0碰）-> ...
        wall_codes = [
            '1m',   # S0第14张（完成1m暗杠）
            '5mr',  # S0摸牌
            '2m',   # S1摸牌
            '3m',   # S2摸牌
            '6m',   # S3摸牌
            '4m',   # S0摸牌
            '5m',   # S1摸牌
            '7m',   # S2摸牌（关键：用于荣和）
            '8m',   # S3摸牌
            '9m',   # S0摸牌
        ]
        wall = [tile_from_code(deck, c) for c in wall_codes]

        # 补充剩余牌到136张
        used = set(front + dead_wall + wall)
        remaining = [t for t in deck if t not in used]

        return tuple(front + dead_wall + wall + remaining)

    elif scenario == 2:  # 暗杠、自摸
        # 简化：使用标准牌山但调整顺序
        s0 = ['1m','1m','1m','2m','3m','4p','5p','6p','7s','8s','9s','1z','2z']  # 1m暗杠
        s1 = ['4m','5m','6m','7m','8m','9m','1p','2p','3p','4p','5p','6p','7p']
        s2 = ['2m','3m','5m','6m','7m','8p','9p','1s','2s','3s','4s','5s','6s']
        s3 = ['8m','9m','1p','2p','3p','4p','5p','7p','8p','7s','8s','9s','1z']

        hands = s0 + s1 + s2 + s3
        front = [tile_from_code(deck, c) for c in hands]

        dead_wall_codes = ['7m','3s','6z','2z','5z','1z','2z','3z','4z','5z','6z','7z','8s','9s']
        dead_wall = [tile_from_code(deck, c) for c in dead_wall_codes]

        # S0先摸1m（暗杠），再摸自摸牌
        wall_codes = ['1m','3m']  # S0暗杠1m，然后自摸3m
        wall = [tile_from_code(deck, c) for c in wall_codes]

        used = set(front + dead_wall + wall)
        remaining = [t for t in deck if t not in used]

        return tuple(front + dead_wall + wall + remaining)

    elif scenario == 3:  # 九连宝灯
        # S0手牌：九连宝灯听牌型（1112345678999m + 任意）
        s0 = ['1m','1m','1m','2m','3m','4m','5m','6m','7m','8m','9m','9m','9m']  # 听任意m
        s1 = ['1p','1p','1p','2p','3p','4p','5p','6p','7p','8p','9p','9p','9p']
        s2 = ['1s','1s','1s','2s','3s','4s','5s','6s','7s','8s','9s','9s','9s']
        s3 = ['1z','1z','1z','2z','2z','2z','3z','3z','3z','4z','4z','4z','5z']

        hands = s0 + s1 + s2 + s3
        front = [tile_from_code(deck, c) for c in hands]

        dead_wall_codes = ['5m','6m','7m','5z','6z','7z','8s','9s','1z','2z','3z','4z','5z','6z']
        dead_wall = [tile_from_code(deck, c) for c in dead_wall_codes]

        # S0自摸5m完成九连宝灯
        wall_codes = ['5m']
        wall = [tile_from_code(deck, c) for c in wall_codes]

        used = set(front + dead_wall + wall)
        remaining = [t for t in deck if t not in used]

        return tuple(front + dead_wall + wall + remaining)

    else:  # 流局
        # 标准牌山，打到荒牌
        return tuple(deck)


def run_scenario(scenario_num, seed):
    """运行特定场景。"""
    deck = list(build_deck())
    wall = build_specific_wall(deck, scenario_num)

    state = initial_game_state()
    actions_acc = []
    events_acc = []

    # BEGIN_ROUND
    begin_act = Action(ActionKind.BEGIN_ROUND, wall=wall)
    begin_out = apply(state, begin_act)
    actions_acc.append(action_to_wire(begin_act))
    events_acc.extend([game_event_to_wire(e) for e in begin_out.events])
    state = begin_out.new_state

    # 根据场景执行特定动作序列
    if scenario_num == 1:
        # 第1局：碰、吃、大明杠、荣和
        # 动作序列精心设计...
        pass  # 需要复杂的动作控制

    # 返回文档
    return {
        "seed": seed,
        "stopped_reason": "demo",
        "steps": len(actions_acc),
        "final_phase": state.phase.value,
        "actions_wire": actions_acc,
        "events_wire": events_acc,
    }


def main():
    """主函数：生成复杂演示牌谱。"""
    demo_dir = Path(__file__).parent

    print("生成演示牌谱...")
    print()

    # 目前先生成一个简化版牌谱
    # 完整的多场景牌谱需要更复杂的动作编排

    # 使用 kernel.runner 跑一个较长的对局
    from llm.runner import run_llm_match

    rr = run_llm_match(seed=999, max_player_steps=1000, dry_run=True)
    doc = rr.as_match_log()

    json_path = demo_dir / "complex_game.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    print(f"牌谱已保存: {json_path}")
    print(f"包含 {len(doc['actions'])} 个动作")
    print(f"终局原因: {doc['stopped_reason']}")
    print()
    print("运行方式:")
    print(f"  python -m llm --replay {json_path} --watch")


if __name__ == "__main__":
    main()
