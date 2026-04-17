"""多步对局循环：观测 →（可选）LLM → ``apply``。"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, TextIO

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
from llm.agent import PlayerAgent
from llm.agent.context import EpisodeContext
from llm.agent.event_journal import MatchJournal
from llm.agent.match_context import MatchContext
from llm.observation_format import build_user_prompt
from llm.protocol import CompletionClient
from llm.table_snapshot_text import action_wire_to_cn, write_snapshot_block
from llm.turns import pending_actor_seats
from llm.config import MatchEndCondition

log = logging.getLogger(__name__)


def _live_wall_remaining_tiles(board: Any) -> int | None:
    """本墙剩余可摸张数（``len(live_wall) - live_draw_index``）；无 ``board`` 时为 ``None``。"""
    if board is None:
        return None
    return len(board.live_wall) - board.live_draw_index


def _stderr_progress(verbose: bool, msg: str) -> None:
    if verbose:
        print(msg, file=sys.stderr)


def _format_callback_action_label(action: Action) -> str:
    """为实时 UI 构建简洁中文动作标签。"""
    seat_prefix = f"家{action.seat} " if action.seat is not None else ""

    if action.kind == ActionKind.DRAW:
        return f"{seat_prefix}摸牌".strip()
    if action.kind == ActionKind.DISCARD:
        tile = action.tile.to_code() if action.tile is not None else "?"
        verb = "立直打牌" if action.declare_riichi else "打牌"
        return f"{seat_prefix}{verb} {tile}".strip()
    if action.kind == ActionKind.PASS_CALL:
        return f"{seat_prefix}过牌".strip()
    if action.kind == ActionKind.CALL_PASS_DRAIN:
        return "连续过牌"
    if action.kind == ActionKind.RON:
        return f"{seat_prefix}荣和".strip()
    if action.kind == ActionKind.TSUMO:
        return f"{seat_prefix}自摸和了".strip()
    if action.kind == ActionKind.OPEN_MELD and action.meld is not None:
        meld_kind = {
            "chi": "吃",
            "pon": "碰",
            "daiminkan": "大明杠",
        }.get(action.meld.kind.value, "鸣牌")
        tiles = "".join(tile.to_code() for tile in action.meld.tiles)
        return f"{seat_prefix}{meld_kind} [{tiles}]".strip()
    if action.kind == ActionKind.ANKAN and action.meld is not None:
        tiles = "".join(tile.to_code() for tile in action.meld.tiles)
        return f"{seat_prefix}暗杠 [{tiles}]".strip()
    if action.kind == ActionKind.SHANKUMINKAN and action.meld is not None:
        tiles = "".join(tile.to_code() for tile in action.meld.tiles)
        return f"{seat_prefix}加杠 [{tiles}]".strip()
    if action.kind == ActionKind.BEGIN_ROUND:
        return "开局配牌"
    return f"{seat_prefix}{action.kind.value}".strip()


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


def _update_episode_stats(
    events: tuple[GameEvent, ...],
    seat_contexts: dict[int, EpisodeContext],
) -> None:
    """更新 EpisodeContext 的统计（Ron/Tsumo/DealIn）。"""
    for ev in events:
        if isinstance(ev, RonEvent):
            # 和了者记录 win
            if ev.seat in seat_contexts:
                seat_contexts[ev.seat].record_win(ev.win_tile.to_code())
            # 放铳者记录 deal_in
            if ev.discard_seat in seat_contexts:
                seat_contexts[ev.discard_seat].record_deal_in(ev.win_tile.to_code())
        elif isinstance(ev, TsumoEvent):
            if ev.seat in seat_contexts:
                seat_contexts[ev.seat].record_win(ev.win_tile.to_code())


def _finalize_agents_episode(
    events: tuple[GameEvent, ...],
    seat_agents: dict[int, PlayerAgent],
    seat_contexts: dict[int, EpisodeContext],
    match_contexts: dict[int, MatchContext],
    client: CompletionClient | None = None,
) -> None:
    """局结束时更新所有 Agent 的 memory 并关闭 EpisodeContext."""
    for ev in events:
        if isinstance(ev, (HandOverEvent, FlowEvent)):
            for seat in range(4):
                if seat in seat_agents and seat in seat_contexts:
                    points = ev.payments[seat] if isinstance(ev, HandOverEvent) else 0
                    seat_contexts[seat].end_episode(points)
                    # 关闭本局（更新 MatchContext 的跨局统计）
                    match_contexts[seat].close_episode(seat_contexts[seat])
                    seat_agents[seat].update_memory(seat_contexts[seat], client)


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
    discarded_tile: Tile | None = None,
    llm_why: str | None = None,
    llm_why_seat: int | None = None,
) -> None:
    """``logs/simple``：全桌快照 + 「执行」行（相对当前亲席风位 + 绝对座位 S0–S3）。"""
    if fp is None:
        return
    # 合并 PASS 不产生局面变化，跳过整块牌桌以减小日志体积
    if wire is not None and wire.get("kind") == "call_pass_drain":
        return
    # 摸打合并为一块：只在本家打牌后输出，跳过摸牌步；
    # 若本步摸牌触发流局（事件中含 FlowEvent），仍输出一块以便显示「本局流局」摘要。
    if wire is not None and wire.get("kind") == "draw":
        if events and any(isinstance(e, FlowEvent) for e in events):
            pass
        else:
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
        discarded_tile=discarded_tile,
        llm_why=llm_why,
        llm_why_seat=llm_why_seat,
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
    kernel_steps: int
    player_steps: int
    stopped_reason: str
    seed: int = 0
    actions_wire: tuple[dict[str, Any], ...] = ()
    events_wire: tuple[dict[str, Any], ...] = ()
    reasons: tuple[str | None, ...] = ()  # 每个动作的决策理由

    def as_match_log(self) -> dict[str, Any]:
        """可 ``json.dump`` 的牌谱顶层结构。"""
        return match_log_document(
            seed=self.seed,
            stopped_reason=self.stopped_reason,
            steps=self.kernel_steps,
            final_phase=self.final_state.phase.value,
            actions_wire=self.actions_wire,
            events_wire=self.events_wire,
            reasons=self.reasons,
        )


def run_llm_match(
    *,
    seed: int,
    match_end: MatchEndCondition,
    request_delay_seconds: float,
    history_budget: int,
    context_scope: str,
    compression_level: str,
    context_budget_tokens: int,
    reserved_output_tokens: int,
    safety_margin_tokens: int,
    prompt_format: str,  # natural 或 json
    enable_conversation_logging: bool,
    client: CompletionClient | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    session_audit: bool = False,
    simple_log_file: TextIO | None = None,
    on_step_callback: Callable[[GameState, tuple[GameEvent, ...], str, str | None], None] | None = None,
    players: list[dict[str, Any]] | None = None,
    system_prompt: str | None = None,
) -> RunResult:
    """
    从 ``PRE_DEAL`` 开局到 ``MATCH_END`` 或满足结束条件。

    - ``dry_run``：每步取 ``legal_actions`` 首项（确定性，无网络）。
    - 局间 ``HAND_OVER`` / ``FLOWN``：自动 ``NOOP`` + 新牌山（``shuffle_deck`` 递增种子）。
    - ``verbose``：每步 ``apply`` 后向 stderr 打一行阶段摘要（CLI ``--verbose``）。
    - ``session_audit``：向 logging 写每步内核动作摘要；
      非 dry-run 时另写模型解析结果（CLI ``--log-session``）；
      遇 ``ron`` / ``tsumo`` / ``hand_over`` / ``match_end`` 等时另写 ``settlement …`` 行。
    - ``history_budget``：历史预算。
    - ``context_scope``：AIma 本地上下文边界（``stateless``/``per_hand``/``per_match``）。
    - ``compression_level``：历史压缩级别（``none``/``snip``/``micro``/``collapse``/``autocompact``）。
    - ``context_budget_tokens``：Prompt 输入预算。
    - ``reserved_output_tokens``：预留输出预算。
    - ``safety_margin_tokens``：安全冗余预算。
    - ``simple_log_file``：若给定，按内核事件写简体中文可读对局（与 JSON 牌谱并行）。
    - ``request_delay_seconds``：每次调用 LLM 前休眠秒数（减压控/防连接被掐）；``dry_run`` 时不请求，不休眠。
    - ``on_step_callback``：可选回调，每步玩家决策后调用（用于实时 UI 观战）。
    - ``match_end``：对局结束条件（局数制/负分结束）。
    - ``players``：可选，指定对战玩家列表，格式 [{"id": "player_id", "seat": 0}, ...]。
    - ``enable_conversation_logging``：是否启用对话日志记录（需要 player_id）。
    """
    if simple_log_file is not None:
        simple_log_file.write(f"# AIma 对局可读日志（简体中文） seed={seed}\n\n")

    hand_number = 0
    win_counts: list[int] = [0, 0, 0, 0]
    hands_finished: list[int] = [0]
    effective_history_budget = history_budget
    effective_context_scope = context_scope

    # 每席 Agent 实例（支持 players 配置）
    if players:
        # 按配置创建指定玩家
        seat_agents: dict[int, PlayerAgent] = {}
        for p in players:
            seat = p["seat"]
            player_id = p.get("id")
            seat_agents[seat] = PlayerAgent(
                player_id=player_id,
                history_budget=effective_history_budget,
                system_prompt=system_prompt,
                prompt_mode=prompt_format,
                compression_level=compression_level,
                context_scope=effective_context_scope,
                context_budget_tokens=context_budget_tokens,
                reserved_output_tokens=reserved_output_tokens,
                safety_margin_tokens=safety_margin_tokens,
                use_delta=(prompt_format == "json"),
            )
        # 未指定的座位使用默认
        for s in range(4):
            if s not in seat_agents:
                seat_agents[s] = PlayerAgent(
                    history_budget=effective_history_budget,
                    system_prompt=system_prompt,
                    prompt_mode=prompt_format,
                    compression_level=compression_level,
                    context_scope=effective_context_scope,
                    context_budget_tokens=context_budget_tokens,
                    reserved_output_tokens=reserved_output_tokens,
                    safety_margin_tokens=safety_margin_tokens,
                    use_delta=(prompt_format == "json"),
                )
    else:
        # 全部使用默认
        seat_agents: dict[int, PlayerAgent] = {
            s: PlayerAgent(
                history_budget=effective_history_budget,
                system_prompt=system_prompt,
                prompt_mode=prompt_format,
                compression_level=compression_level,
                context_scope=effective_context_scope,
                context_budget_tokens=context_budget_tokens,
                reserved_output_tokens=reserved_output_tokens,
                safety_margin_tokens=safety_margin_tokens,
                use_delta=(prompt_format == "json"),
            ) for s in range(4)
        }
    # MatchContext：跨局状态管理（Context Object 模式）
    # 需要传递 player_id 以支持对话日志记录
    player_id_map: dict[int, str | None] = {}
    if players:
        for p in players:
            player_id_map[p["seat"]] = p.get("id")
    shared_journal = MatchJournal()
    match_contexts: dict[int, MatchContext] = {
        s: MatchContext(s, player_id=player_id_map.get(s), match_journal=shared_journal) for s in range(4)
    }
    # EpisodeContext：运行时状态管理（由 MatchContext 创建）
    # dry_run 时禁用 conversation_logging（避免创建空文件）
    effective_conversation_logging = enable_conversation_logging and not dry_run
    seat_contexts: dict[int, EpisodeContext] = {
        s: match_contexts[s].create_episode(enable_conversation_logging=effective_conversation_logging)
        for s in range(4)
    }
    state = initial_game_state()
    wall_seed = seed
    wall = tuple(shuffle_deck(build_deck(), seed=wall_seed))
    wall_seed += 1

    actions_acc: list[dict[str, Any]] = []
    events_acc: list[dict[str, Any]] = []
    reasons_acc: list[str | None] = []  # 收集决策理由

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
        shared_journal.start_hand(1, begin_out.events)
        _accumulate_simple_stats(begin_out.events, win_counts, hands_finished)
        hand_number = 1
        # EpisodeContext 已在初始化时创建，无需额外操作
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
        # 初始状态显示（让 UI 先渲染配牌结果）
        if on_step_callback is not None:
            on_step_callback(state, begin_out.events, "开局配牌", None)
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
            kernel_steps=0,
            player_steps=0,
            stopped_reason=f"begin_round_failed:{e}",
            seed=seed,
            actions_wire=(),
            events_wire=(),
            reasons=(),
        )

    kernel_steps = 0
    player_steps = 0
    hands_completed = 0  # 已完成的局数
    reason = "match_end"

    while True:
        # 检查结束条件（每局结束后）
        if hands_completed > 0 and state.phase in (GamePhase.HAND_OVER, GamePhase.FLOWN, GamePhase.MATCH_END):
            should_end, end_reason = match_end.is_match_end(hands_completed, state.table.scores)
            if should_end:
                reason = end_reason
                # Phase 4: 更新所有 Agent 的 stats
                final_scores = state.table.scores
                final_dealer = state.table.dealer_seat
                sorted_seats = sorted(
                    range(4),
                    key=lambda s: (-final_scores[s], (s - final_dealer) % 4)
                )
                placements = {seat: rank + 1 for rank, seat in enumerate(sorted_seats)}
                for seat, agent in seat_agents.items():
                    if agent.player_id is not None and seat in seat_contexts:
                        agent.update_stats(seat_contexts[seat], placements[seat])
                shared_journal.archive_current_hand()
                # 触发 MATCH_END
                break

        if state.phase == GamePhase.MATCH_END:
            reason = "match_end"
            final_scores = state.table.scores
            final_dealer = state.table.dealer_seat
            sorted_seats = sorted(
                range(4),
                key=lambda s: (-final_scores[s], (s - final_dealer) % 4)
            )
            placements = {seat: rank + 1 for rank, seat in enumerate(sorted_seats)}
            for seat, agent in seat_agents.items():
                if agent.player_id is not None and seat in seat_contexts:
                    agent.update_stats(seat_contexts[seat], placements[seat])
            shared_journal.archive_current_hand()
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
                shared_journal.archive_current_hand()
                _accumulate_simple_stats(noop_out.events, win_counts, hands_finished)
                state = noop_out.new_state
                if state.phase == GamePhase.IN_ROUND and old_phase in (
                    GamePhase.HAND_OVER,
                    GamePhase.FLOWN,
                ):
                    hands_completed += 1  # 已完成一局
                    hand_number += 1
                    shared_journal.start_hand(hand_number, noop_out.events)
                    # 新一局开始时，由 MatchContext 创建新的 EpisodeContext（Factory 模式）
                    for s in range(4):
                        seat_contexts[s] = match_contexts[s].create_episode(
                            enable_conversation_logging=effective_conversation_logging
                        )
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
                    f"[match] step={kernel_steps + 1} noop+wall phase={state.phase.value}",
                )
                if session_audit:
                    log.info(
                        "apply step=%s noop wall_next_phase=%s",
                        kernel_steps + 1,
                        state.phase.value,
                    )
            except IllegalActionError as e:
                reason = f"noop_wall_failed:{e}"
                break
            kernel_steps += 1
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
                    shared_journal.append_events(step_out.events)
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
                        f"[match] step={kernel_steps + 1} {drain_act.kind.value} drained={n} "
                        f"phase={state.phase.value} "
                        f"turn_seat={b.current_seat if b else None}",
                    )
                    if session_audit:
                        wr = _live_wall_remaining_tiles(b)
                        log.info(
                            "apply step=%s action=%s drained=%s phase=%s turn_seat=%s "
                            "wall_remaining=%s",
                            kernel_steps + 1,
                            drain_act.kind.value,
                            n,
                            state.phase.value,
                            b.current_seat if b else None,
                            wr,
                        )
                    kernel_steps += n
                    continue

            seat = pending[0]
            agent = seat_agents[seat]
            episode_ctx = seat_contexts[seat]
            decision = agent.decide(
                state,
                seat,
                episode_ctx=episode_ctx,
                client=client,
                dry_run=dry_run,
                session_audit=session_audit,
                request_delay_seconds=request_delay_seconds,
            )
            la, llm_why = decision.action, decision.why
            act = legal_action_to_action(la)
            # 记录立直到 EpisodeContext
            if act.kind == ActionKind.DISCARD and act.declare_riichi:
                episode_ctx.record_riichi()
                # 为其他玩家触发关键帧：任何玩家立直时，其他玩家需要知道
                for other_seat in range(4):
                    if other_seat != seat and other_seat in seat_contexts:
                        seat_contexts[other_seat].record_riichi_trigger()
            turn_draw_tile: Tile | None = None
            discard_seat_for_log: int | None = None
            discarded_tile_for_log: Tile | None = None
            if act.kind == ActionKind.DISCARD and state.board is not None:
                turn_draw_tile = state.board.last_draw_tile
                discard_seat_for_log = act.seat
                discarded_tile_for_log = act.tile
            step_out = apply(state, act)
            actions_acc.append(action_to_wire(act))
            _append_events_with_settlement_log(
                events_acc,
                step_out.events,
                session_audit=session_audit,
                verbose=verbose,
            )
            shared_journal.append_events(step_out.events)
            _accumulate_simple_stats(step_out.events, win_counts, hands_finished)
            # 更新 EpisodeContext 统计
            _update_episode_stats(step_out.events, seat_contexts)
            # 局结束时更新 Agent memory 并关闭 EpisodeContext
            _finalize_agents_episode(step_out.events, seat_agents, seat_contexts, match_contexts, client)
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
                discarded_tile=discarded_tile_for_log,
                llm_why=llm_why,
                llm_why_seat=seat,
            )
            b = state.board
            _stderr_progress(
                verbose,
                f"[match] step={kernel_steps + 1} {act.kind.value} seat={act.seat} "
                f"phase={state.phase.value} "
                f"turn_seat={b.current_seat if b else None}",
            )
            # 实时观战回调
            if on_step_callback is not None:
                try:
                    action_str = _format_callback_action_label(act)
                    on_step_callback(state, step_out.events, action_str, llm_why)
                except Exception:
                    # 回调异常不应中断对局
                    pass
            player_steps += 1  # 玩家决策步数递增（无论回调是否成功）
            reasons_acc.append(llm_why)  # 记录决策理由
            if session_audit:
                wr = _live_wall_remaining_tiles(b)
                log.info(
                    "apply step=%s action=%s seat=%s phase=%s turn_seat=%s "
                    "wall_remaining=%s wire=%s",
                    kernel_steps + 1,
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
                log.error("apply failed step=%s err=%s", kernel_steps + 1, e)
            break
        kernel_steps += 1

    return RunResult(
        state,
        kernel_steps=kernel_steps,
        player_steps=player_steps,
        stopped_reason=reason,
        seed=seed,
        actions_wire=tuple(actions_acc),
        events_wire=tuple(events_acc),
        reasons=tuple(reasons_acc),
    )
