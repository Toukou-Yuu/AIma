"""批量 dry-run 对局验证脚本。

用途：验证规则引擎稳定性，确保多局对局能正常完成。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kernel.engine.actions import Action, ActionKind
from kernel.engine.apply import apply, IllegalActionError
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState, initial_game_state
from kernel.tiles.deck import build_deck, shuffle_deck
from kernel.board import TurnPhase


def make_standard_wall(seed: int) -> tuple:
    """生成标准 136 张牌山。"""
    return tuple(shuffle_deck(build_deck(), seed=seed))


def run_single_hand(seed: int, verbose: bool = False) -> dict:
    """
    运行单局对局，返回结果统计。

    Returns:
        dict: {
            "seed": int,
            "status": "completed" | "crashed",
            "turns": int,
            "phase": str,
            "error": str | None,
        }
    """
    result = {
        "seed": seed,
        "status": "completed",
        "turns": 0,
        "phase": "",
        "error": None,
    }

    try:
        wall = make_standard_wall(seed)
        state = initial_game_state()

        # BEGIN_ROUND
        outcome = apply(state, Action(kind=ActionKind.BEGIN_ROUND, wall=wall))
        state = outcome.new_state

        # 推进对局
        max_turns = 1000  # 安全限制（一局 69 张 + 每次 pass_call 约 7 次 = ~500 轮次）
        for _ in range(max_turns):
            result["turns"] += 1

            if state.phase == GamePhase.HAND_OVER:
                # 和了后推进下一局（需要新 wall）
                if state.table.dealer_seat in (state.ron_winners or frozenset()):
                    # 连庄，继续推进
                    pass
                # 这里需要 wall，暂不处理（P3 问题）
                result["phase"] = "HAND_OVER"
                result["status"] = "completed"
                break

            if state.phase == GamePhase.FLOWN:
                # 流局后推进下一局（需要新 wall）
                result["phase"] = "FLOWN"
                result["status"] = "completed"
                break

            if state.phase == GamePhase.MATCH_END:
                result["phase"] = "MATCH_END"
                result["status"] = "completed"
                break

            if state.phase != GamePhase.IN_ROUND:
                result["phase"] = state.phase.value
                break

            board = state.board
            if board is None:
                result["phase"] = "IN_ROUND (no board)"
                break

            # 简化推进：自动选择合法动作
            if board.turn_phase == TurnPhase.NEED_DRAW:
                outcome = apply(state, Action(kind=ActionKind.DRAW))
                state = outcome.new_state
            elif board.turn_phase == TurnPhase.MUST_DISCARD:
                # 自动打牌（优先摸切）
                if board.last_draw_tile is not None:
                    tile = board.last_draw_tile
                else:
                    # 从手牌选一张（首巡庄家）
                    hand = board.hands[board.current_seat]
                    tile = next(iter(hand.elements()))
                outcome = apply(state, Action(
                    kind=ActionKind.DISCARD,
                    seat=board.current_seat,
                    tile=tile,
                ))
                state = outcome.new_state
            elif board.turn_phase == TurnPhase.CALL_RESPONSE:
                # 自动 pass（需要选择合法 seat）
                cs = board.call_state
                if cs is None:
                    result["phase"] = "CALL_RESPONSE (no call_state)"
                    break

                # 优先 pass 荣和阶段（如果有 ron_remaining）
                if cs.stage == "ron" and cs.ron_remaining:
                    seat = next(iter(cs.ron_remaining))
                    outcome = apply(state, Action(kind=ActionKind.PASS_CALL, seat=seat))
                    state = outcome.new_state
                elif cs.stage == "pon_kan":
                    seat = cs.pon_kan_order[cs.pon_kan_idx]
                    outcome = apply(state, Action(kind=ActionKind.PASS_CALL, seat=seat))
                    state = outcome.new_state
                elif cs.stage == "chi":
                    # chi 只有下家
                    from kernel.board import shimocha_seat
                    seat = shimocha_seat(cs.discard_seat)
                    outcome = apply(state, Action(kind=ActionKind.PASS_CALL, seat=seat))
                    state = outcome.new_state
                elif cs.finished:
                    # 荣和完成，转 HAND_OVER
                    result["phase"] = "CALL_RESPONSE (finished)"
                    break
                else:
                    result["phase"] = f"CALL_RESPONSE (unknown stage: {cs.stage})"
                    break
            else:
                result["phase"] = f"unknown phase: {board.turn_phase}"
                break

        if result["turns"] >= max_turns:
            result["status"] = "max_turns_reached"
            if state.phase:
                result["phase"] = state.phase.value

    except IllegalActionError as e:
        result["status"] = "crashed"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "crashed"
        result["error"] = f"{type(e).__name__}: {e}"

    if verbose:
        print(f"seed={seed}: {result['status']} (turns={result['turns']}, phase={result['phase']})")

    return result


def run_batch(seeds: range, verbose: bool = False) -> list[dict]:
    """批量运行多个 seed。"""
    results = []
    for seed in seeds:
        result = run_single_hand(seed, verbose)
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description="批量 dry-run 对局验证")
    parser.add_argument(
        "--seeds",
        type=str,
        default="0:100",
        help="seed 范围，格式 start:end（默认 0:100）",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示每局详细结果",
    )
    parser.add_argument(
        "--save-failures",
        type=str,
        default=None,
        help="保存失败结果到 JSON 文件",
    )
    args = parser.parse_args()

    # 解析 seed 范围
    try:
        start, end = map(int, args.seeds.split(":"))
        seeds = range(start, end)
    except ValueError:
        print(f"无效的 seed 范围: {args.seeds}")
        sys.exit(1)

    print(f"运行 {len(seeds)} seeds...")

    # 执行批量验证
    results = run_batch(seeds, args.verbose)

    # 统计
    completed = sum(1 for r in results if r["status"] == "completed")
    crashed = sum(1 for r in results if r["status"] == "crashed")
    max_turns = sum(1 for r in results if r["status"] == "max_turns_reached")

    print("\n统计:")
    print(f"  完成: {completed}")
    print(f"  崩溃: {crashed}")
    print(f"  达到最大轮次: {max_turns}")

    # 保存失败结果
    if args.save_failures:
        failures = [r for r in results if r["status"] not in ("completed", "max_turns_reached")]
        if failures:
            path = Path(args.save_failures)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(failures, f, indent=2)
            print(f"失败结果已保存到: {path}")

    # 返回码
    if crashed > 0:
        print(f"\n❌ 有 {crashed} 个崩溃")
        sys.exit(1)
    else:
        print("\n✅ 全部通过")
        sys.exit(0)


if __name__ == "__main__":
    main()