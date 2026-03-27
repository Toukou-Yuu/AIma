"""多步对局循环：观测 →（可选）LLM → ``apply``。"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from typing import Any, TextIO

from kernel import (
    Action,
    ActionKind,
    GamePhase,
    GameState,
    IllegalActionError,
    TurnPhase,
    apply,
    build_deck,
    initial_game_state,
    legal_actions,
    observation,
    shuffle_deck,
)
from kernel.api.legal_actions import LegalAction
from kernel.event_log import (
    FlowEvent,
    GameEvent,
    HandOverEvent,
    MatchEndEvent,
    RonEvent,
    TsumoEvent,
)
from kernel.replay_json import action_to_wire, game_event_to_wire, match_log_document
from kernel.tiles.model import Tile
from llm.action_build import legal_action_to_action
from llm.observation_format import SYSTEM_PROMPT, build_user_prompt
from llm.parse import extract_json_object
from llm.protocol import ChatMessage, CompletionClient
from llm.table_snapshot_text import action_wire_to_cn, write_snapshot_block
from llm.turns import pending_actor_seats
from llm.validate import find_matching_legal_action
from llm.wire import legal_action_to_wire

log = logging.getLogger(__name__)


def _live_wall_remaining_tiles(board: Any) -> int | None:
    """本墙剩余可摸张数（``len(live_wall) - live_draw_index``）；无 ``board`` 时为 ``None``。"""
    if board is None:
        return None
    return len(board.live_wall) - board.live_draw_index


def _stderr_progress(verbose: bool, msg: str) -> None:
    if verbose:
        print(msg, file=sys.stderr)


def _accumulate_simple_stats(
    events: tuple[GameEvent, ...],
    win_counts: list[int],
    hands_finished: list[int],
) -> None:
    """根据 ``HandOverEvent`` / ``FlowEvent`` 累计和了次数与已终局数（供 simple 胜率）。"""
    for ev in events:
        if isinstance(ev, HandOverEvent):
            hands_finished[0] += 1
            for w in ev.winners:
                win_counts[w] += 1
        elif isinstance(ev, FlowEvent):
            hands_finished[0] += 1


def _write_simple_snapshot(
    fp: TextIO | None,
    state: GameState,
    hand_number: int,
    wire: dict[str, Any] | None,
    *,
    win_counts: tuple[int, int, int, int],
    hands_finished: int,
    events: tuple[GameEvent, ...] | None = None,
    turn_draw_tile: Tile | None = None,
    discard_seat: int | None = None,
) -> None:
    """``logs/simple``：全桌快照 + 「执行」行（相对当前亲席风位）。"""
    if fp is None:
        return
    # 合并 PASS 不产生局面变化，跳过整块牌桌以减小日志体积
    if wire is not None and wire.get("kind") == "call_pass_drain":
        return
    # 摸打合并为一块：只在本家打牌后输出，跳过摸牌步
    if wire is not None and wire.get("kind") == "draw":
        return
    ds = state.table.dealer_seat
    draw_code = turn_draw_tile.to_code() if turn_draw_tile else None
    last_cn = (
        action_wire_to_cn(wire, dealer_seat=ds, draw_tile_code=draw_code)
        if wire
        else None
    )
    write_snapshot_block(
        fp,
        state,
        hand_number=hand_number,
        last_action_cn=last_cn,
        win_counts=win_counts,
        hands_finished=hands_finished,
        events=events,
        turn_draw_tile=turn_draw_tile,
        discard_seat=discard_seat,
    )


def _append_events_with_settlement_log(
    events_acc: list[dict[str, Any]],
    events: tuple[GameEvent, ...],
    *,
    session_audit: bool,
    verbose: bool,
) -> None:
    """写入牌谱 ``events`` wire，并对荣和/自摸/局收支/终局写审计日志与 ``verbose`` 摘要。"""
    for ev in events:
        events_acc.append(game_event_to_wire(ev))
        if not session_audit and not verbose:
            continue
        if session_audit:
            if isinstance(ev, RonEvent):
                log.info(
                    "settlement ron seq=%s seat=%s win_tile=%s discard_seat=%s",
                    ev.sequence,
                    ev.seat,
                    ev.win_tile.to_code(),
                    ev.discard_seat,
                )
            elif isinstance(ev, TsumoEvent):
                log.info(
                    "settlement tsumo seq=%s seat=%s win_tile=%s rinshan=%s",
                    ev.sequence,
                    ev.seat,
                    ev.win_tile.to_code(),
                    ev.is_rinshan,
                )
            elif isinstance(ev, HandOverEvent):
                log.info(
                    "settlement hand_over seq=%s %s",
                    ev.sequence,
                    json.dumps(game_event_to_wire(ev), ensure_ascii=False),
                )
            elif isinstance(ev, MatchEndEvent):
                log.info(
                    "settlement match_end seq=%s ranking=%s final_scores=%s",
                    ev.sequence,
                    list(ev.ranking),
                    list(ev.final_scores),
                )
        if verbose:
            if isinstance(ev, RonEvent):
                _stderr_progress(
                    True,
                    f"[match] ron seat={ev.seat} win_tile={ev.win_tile.to_code()} "
                    f"discard_seat={ev.discard_seat}",
                )
            elif isinstance(ev, TsumoEvent):
                _stderr_progress(
                    True,
                    f"[match] tsumo seat={ev.seat} win_tile={ev.win_tile.to_code()} "
                    f"rinshan={ev.is_rinshan}",
                )
            elif isinstance(ev, HandOverEvent):
                parts = [
                    (
                        f"s{ln.seat}:{ln.win_kind} {ln.han}番{ln.fu}符 {ln.hand_pattern} "
                        f"[{'/'.join(ln.yakus)}] points={ln.points}"
                    )
                    for ln in ev.win_lines
                ]
                _stderr_progress(
                    True,
                    "[match] hand_over "
                    f"winners={ev.winners} payments={ev.payments} | " + " | ".join(parts),
                )
            elif isinstance(ev, MatchEndEvent):
                _stderr_progress(
                    True,
                    f"[match] match_end ranking={list(ev.ranking)} "
                    f"final_scores={list(ev.final_scores)}",
                )


@dataclass(frozen=True, slots=True)
class RunResult:
    """一轮跑局结果。"""

    final_state: GameState
    steps: int
    stopped_reason: str
    seed: int = 0
    actions_wire: tuple[dict[str, Any], ...] = ()
    events_wire: tuple[dict[str, Any], ...] = ()

    def as_match_log(self) -> dict[str, Any]:
        """可 ``json.dump`` 的牌谱顶层结构。"""
        return match_log_document(
            seed=self.seed,
            stopped_reason=self.stopped_reason,
            steps=self.steps,
            final_phase=self.final_state.phase.value,
            actions_wire=self.actions_wire,
            events_wire=self.events_wire,
        )


def choose_legal_action(
    state: GameState,
    seat: int,
    *,
    client: CompletionClient | None,
    dry_run: bool,
    session_audit: bool = False,
) -> LegalAction:
    acts = legal_actions(state, seat)
    if not acts:
        msg = f"no legal_actions for seat {seat}"
        raise RuntimeError(msg)

    # 唯一合法动作为「过」时不调用 API（内核已判定无荣/当前轮无其它选项）
    if len(acts) == 1 and acts[0].kind == ActionKind.PASS_CALL:
        if session_audit:
            log.info("llm_skipped singleton pass_call seat=%s", seat)
        return acts[0]

    if dry_run or client is None:
        return acts[0]

    obs = observation(state, seat, mode="human")
    user_content = build_user_prompt(obs, acts)
    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_content),
    ]
    raw = client.complete(messages)
    if session_audit:
        head = raw if len(raw) <= 600 else raw[:600] + "…"
        log.debug("llm raw_head seat=%s %r", seat, head)
    try:
        choice = extract_json_object(raw)
    except (ValueError, TypeError) as e:
        log.warning("parse failed, fallback first legal: %s", e)
        return acts[0]
    la = find_matching_legal_action(acts, choice)
    if la is None:
        log.warning("choice not in legal_actions, fallback first: %s", choice)
        return acts[0]
    if session_audit:
        log.info(
            "llm_choice seat=%s %s",
            seat,
            json.dumps(legal_action_to_wire(la), ensure_ascii=False),
        )
    return la


def run_llm_match(
    *,
    seed: int,
    max_steps: int,
    client: CompletionClient | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    session_audit: bool = False,
    simple_log_file: TextIO | None = None,
) -> RunResult:
    """
    从 ``PRE_DEAL`` 开局到 ``MATCH_END`` 或步数上限。

    - ``dry_run``：每步取 ``legal_actions`` 首项（确定性，无网络）。
    - 局间 ``HAND_OVER`` / ``FLOWN``：自动 ``NOOP`` + 新牌山（``shuffle_deck`` 递增种子）。
    - ``verbose``：每步 ``apply`` 后向 stderr 打一行阶段摘要（CLI ``--verbose``）。
    - ``session_audit``：向 logging 写每步内核动作摘要；
      非 dry-run 时另写模型解析结果（CLI ``--log-session``）；
      遇 ``ron`` / ``tsumo`` / ``hand_over`` / ``match_end`` 等时另写 ``settlement …`` 行。
    - ``simple_log_file``：若给定，按内核事件写简体中文可读对局（与 JSON 牌谱并行）。
    """
    if simple_log_file is not None:
        simple_log_file.write(f"# AIma 对局可读日志（简体中文） seed={seed}\n\n")

    hand_number = 0
    win_counts: list[int] = [0, 0, 0, 0]
    hands_finished: list[int] = [0]
    state = initial_game_state()
    wall_seed = seed
    wall = tuple(shuffle_deck(build_deck(), seed=wall_seed))
    wall_seed += 1

    actions_acc: list[dict[str, Any]] = []
    events_acc: list[dict[str, Any]] = []

    begin_act = Action(ActionKind.BEGIN_ROUND, wall=wall)
    try:
        begin_out = apply(state, begin_act)
        actions_acc.append(action_to_wire(begin_act))
        _append_events_with_settlement_log(
            events_acc,
            begin_out.events,
            session_audit=session_audit,
            verbose=verbose,
        )
        _accumulate_simple_stats(begin_out.events, win_counts, hands_finished)
        hand_number = 1
        _write_simple_snapshot(
            simple_log_file,
            begin_out.new_state,
            hand_number,
            action_to_wire(begin_act),
            win_counts=tuple(win_counts),
            hands_finished=hands_finished[0],
            events=begin_out.events,
        )
        state = begin_out.new_state
        _stderr_progress(
            verbose,
            f"[match] begin_round phase={state.phase.value} dealer={state.table.dealer_seat}",
        )
        if session_audit:
            br = _live_wall_remaining_tiles(state.board)
            log.info(
                "apply begin_round phase=%s dealer=%s wall_remaining=%s",
                state.phase.value,
                state.table.dealer_seat,
                br,
            )
    except IllegalActionError as e:
        return RunResult(
            state,
            0,
            f"begin_round_failed:{e}",
            seed=seed,
            actions_wire=(),
            events_wire=(),
        )

    steps = 0
    reason = "max_steps"
    while steps < max_steps:
        if state.phase == GamePhase.MATCH_END:
            reason = "match_end"
            break

        if state.phase in (GamePhase.HAND_OVER, GamePhase.FLOWN):
            nw = tuple(shuffle_deck(build_deck(), seed=wall_seed))
            wall_seed += 1
            noop_act = Action(ActionKind.NOOP, wall=nw)
            old_phase = state.phase
            try:
                noop_out = apply(state, noop_act)
                actions_acc.append(action_to_wire(noop_act))
                _append_events_with_settlement_log(
                    events_acc,
                    noop_out.events,
                    session_audit=session_audit,
                    verbose=verbose,
                )
                _accumulate_simple_stats(noop_out.events, win_counts, hands_finished)
                state = noop_out.new_state
                if state.phase == GamePhase.IN_ROUND and old_phase in (
                    GamePhase.HAND_OVER,
                    GamePhase.FLOWN,
                ):
                    hand_number += 1
                _write_simple_snapshot(
                    simple_log_file,
                    state,
                    hand_number,
                    action_to_wire(noop_act),
                    win_counts=tuple(win_counts),
                    hands_finished=hands_finished[0],
                    events=noop_out.events,
                )
                _stderr_progress(
                    verbose,
                    f"[match] step={steps + 1} noop+wall phase={state.phase.value}",
                )
                if session_audit:
                    log.info(
                        "apply step=%s noop wall_next_phase=%s",
                        steps + 1,
                        state.phase.value,
                    )
            except IllegalActionError as e:
                reason = f"noop_wall_failed:{e}"
                break
            steps += 1
            continue

        pending = pending_actor_seats(state)
        if not pending:
            reason = "no_pending_actor"
            break

        try:
            # 应答窗内先序席只能过时，一条牌谱动作合并多次 PASS_CALL
            if (
                state.phase == GamePhase.IN_ROUND
                and state.board is not None
                and state.board.turn_phase == TurnPhase.CALL_RESPONSE
                and pending
            ):
                la0 = legal_actions(state, pending[0])
                if len(la0) == 1 and la0[0].kind == ActionKind.PASS_CALL:
                    drain_act = Action(ActionKind.CALL_PASS_DRAIN)
                    step_out = apply(state, drain_act)
                    actions_acc.append(action_to_wire(drain_act))
                    _append_events_with_settlement_log(
                        events_acc,
                        step_out.events,
                        session_audit=session_audit,
                        verbose=verbose,
                    )
                    _accumulate_simple_stats(step_out.events, win_counts, hands_finished)
                    state = step_out.new_state
                    _write_simple_snapshot(
                        simple_log_file,
                        state,
                        hand_number,
                        action_to_wire(drain_act),
                        win_counts=tuple(win_counts),
                        hands_finished=hands_finished[0],
                        events=step_out.events,
                    )
                    b = state.board
                    n = step_out.drained_pass_calls
                    _stderr_progress(
                        verbose,
                        f"[match] step={steps + 1} {drain_act.kind.value} drained={n} "
                        f"phase={state.phase.value} "
                        f"turn_seat={b.current_seat if b else None}",
                    )
                    if session_audit:
                        wr = _live_wall_remaining_tiles(b)
                        log.info(
                            "apply step=%s action=%s drained=%s phase=%s turn_seat=%s "
                            "wall_remaining=%s",
                            steps + 1,
                            drain_act.kind.value,
                            n,
                            state.phase.value,
                            b.current_seat if b else None,
                            wr,
                        )
                    steps += n
                    continue

            seat = pending[0]
            la = choose_legal_action(
                state,
                seat,
                client=client,
                dry_run=dry_run,
                session_audit=session_audit,
            )
            act = legal_action_to_action(la)
            turn_draw_tile: Tile | None = None
            discard_seat_for_log: int | None = None
            if act.kind == ActionKind.DISCARD and state.board is not None:
                turn_draw_tile = state.board.last_draw_tile
                discard_seat_for_log = act.seat
            step_out = apply(state, act)
            actions_acc.append(action_to_wire(act))
            _append_events_with_settlement_log(
                events_acc,
                step_out.events,
                session_audit=session_audit,
                verbose=verbose,
            )
            _accumulate_simple_stats(step_out.events, win_counts, hands_finished)
            state = step_out.new_state
            _write_simple_snapshot(
                simple_log_file,
                state,
                hand_number,
                action_to_wire(act),
                win_counts=tuple(win_counts),
                hands_finished=hands_finished[0],
                events=step_out.events,
                turn_draw_tile=turn_draw_tile,
                discard_seat=discard_seat_for_log,
            )
            b = state.board
            _stderr_progress(
                verbose,
                f"[match] step={steps + 1} {act.kind.value} seat={act.seat} "
                f"phase={state.phase.value} "
                f"turn_seat={b.current_seat if b else None}",
            )
            if session_audit:
                wr = _live_wall_remaining_tiles(b)
                log.info(
                    "apply step=%s action=%s seat=%s phase=%s turn_seat=%s "
                    "wall_remaining=%s wire=%s",
                    steps + 1,
                    act.kind.value,
                    act.seat,
                    state.phase.value,
                    b.current_seat if b else None,
                    wr,
                    json.dumps(action_to_wire(act), ensure_ascii=False),
                )
        except (IllegalActionError, ValueError, RuntimeError) as e:
            reason = f"step_failed:{e}"
            if session_audit:
                log.error("apply failed step=%s err=%s", steps + 1, e)
            break
        steps += 1

    return RunResult(
        state,
        steps,
        reason,
        seed=seed,
        actions_wire=tuple(actions_acc),
        events_wire=tuple(events_acc),
    )
