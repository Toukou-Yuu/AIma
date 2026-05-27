"""MatchRunner: 对局执行器，编排 GameEngine 与 Policy。"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import TYPE_CHECKING

from arena.errors import IllegalPolicyDecisionError
from arena.hand_result import HandResult
from arena.match_result import MatchResult
from arena.policy import DecisionContext
from arena.result import EngineStepResult
from arena.sinks import EventSink
from context.events import ContextEvent, kernel_event_to_context_event
from kernel import build_deck, shuffle_deck
from kernel.engine.actions import Action, ActionKind
from kernel.engine.phase import GamePhase
from kernel.engine.flow import FlowKind
from kernel.event_log import MatchEndEvent

if TYPE_CHECKING:
    from arena.engine import GameEngine
    from arena.policy import Policy
    from experiments.schema import MatchSpec
    from kernel.api.legal_actions import LegalAction
    from kernel.engine.state import GameState


def _is_action_legal(action: Action, legal_actions: tuple[LegalAction, ...]) -> bool:
    """检查 action 是否在 legal_actions 中。"""
    for legal in legal_actions:
        if action.kind != legal.kind:
            continue
        if action.seat != legal.seat:
            continue
        if action.tile != legal.tile:
            continue
        if action.meld != legal.meld:
            continue
        if action.declare_riichi != legal.declare_riichi:
            continue
        return True
    return False


class MatchRunner:
    """对局执行器，编排 GameEngine 与 Policy。

    核心职责：
    1. 处理 PRE_DEAL -> BEGIN_ROUND 转换（生成牌山）
    2. 处理 HAND_OVER/FLOWN -> NEXT_ROUND 转换（生成牌山）
    3. 在 IN_ROUND 中轮询各席 Policy 决策
    4. 校验 Policy 决策合法性
    5. 收集事件/决策并通过 Sink 输出
    """

    def __init__(
        self,
        engine: GameEngine,
        policies: dict[int, Policy],
        sinks: list[EventSink] | None = None,
        step_limit: int = 20000,
    ) -> None:
        """初始化 MatchRunner。

        Args:
            engine: GameEngine 门面
            policies: 座位 -> Policy 映射（必须包含 0..3 四席）
            sinks: EventSink 列表（默认为空列表）
            step_limit: 最大步数限制
        """
        if len(policies) != 4:
            msg = f"policies must contain exactly 4 entries, got {len(policies)}"
            raise ValueError(msg)
        for seat in range(4):
            if seat not in policies:
                msg = f"policies missing seat {seat}"
                raise ValueError(msg)

        self._engine = engine
        self._policies = policies
        self._sinks = sinks if sinks is not None else []
        self._step_limit = step_limit

    def _get_active_seat(self, state: GameState) -> int | None:
        """获取当前需要决策的座位。

        CALL_RESPONSE 阶段需要根据 call_state 状态确定座位：
        - ron 阶段：min(ron_remaining)
        - pon_kan 阶段：pon_kan_order[pon_kan_idx]
        - chi 阶段：shimocha_seat(discard_seat)
        其他阶段使用 board.current_seat。
        """
        from kernel.board import TurnPhase, shimocha_seat

        board = state.board
        if board is None:
            return None

        if board.turn_phase != TurnPhase.CALL_RESPONSE:
            return board.current_seat

        cs = board.call_state
        if cs is None:
            return None

        if cs.stage == "ron":
            if cs.ron_remaining:
                return min(cs.ron_remaining)
            return None
        elif cs.stage == "pon_kan":
            if cs.pon_kan_idx < len(cs.pon_kan_order):
                return cs.pon_kan_order[cs.pon_kan_idx]
            return None
        elif cs.stage == "chi":
            return shimocha_seat(cs.discard_seat)

        return None

    def run(
        self,
        spec: MatchSpec,
        seed: int,
        job_id: str | None = None,
        match_id: str | None = None,
    ) -> MatchResult:
        """执行对局，返回 MatchResult。

        Args:
            spec: 对局配置（包含 preset, max_hands, step_limit）
            seed: 随机种子
            job_id: 外部指定的 job_id（可选，如未提供则生成确定性 ID）
            match_id: 外部指定的 match_id（可选，如未提供则使用 job_id）

        Returns:
            MatchResult: 对局完整结果
        """
        start_time = time.perf_counter()
        events: list[dict] = []
        decisions: list[dict] = []
        event_history: list[ContextEvent] = []  # v4 native event history for ContextBuilder

        # ID 生成策略：
        # 1. 如果提供 job_id，使用它
        # 2. 否则生成确定性 ID: match_{seed:04d}
        if job_id is None:
            job_id = f"match_{seed:04d}"
        if match_id is None:
            match_id = job_id  # match_id 默认等于 job_id

        # 使用spec中的max_hands（默认8局）
        max_hands = spec.max_hands
        if spec.preset == "tonpuu":
            max_hands = 4  # 东风战固定4局
        elif spec.preset == "hanchan" and max_hands == 0:
            max_hands = 8  # 半庄默认8局

        state = self._engine.new_match(spec, seed)
        step_count = 0
        hand_index = 0
        turn_index = 0
        hand_count = 0  # 已完成局数（在 HAND_OVER/FLOWN 时自增，含流局）

        # 处理 PRE_DEAL -> BEGIN_ROUND
        if state.phase == GamePhase.PRE_DEAL:
            wall = tuple(shuffle_deck(build_deck(), seed=seed))
            action = Action(kind=ActionKind.BEGIN_ROUND, wall=wall)
            result = self._engine.step(state, action)
            state = result.new_state
            step_count += 1
            for ev in result.events:
                events.append({"match_id": match_id, "step_index": step_count, "event": ev})
                event_history.append(
                    kernel_event_to_context_event(
                        kernel_event=ev,
                        match_id=match_id,
                        job_id=job_id,
                        hand_index=hand_index,
                        step_index=step_count,
                        turn_index=turn_index,
                    )
                )

        # 主循环
        while not self._engine.is_terminal(state) and step_count < self._step_limit:
            phase = state.phase

            # HAND_OVER / FLOWN -> NEXT_ROUND
            if phase in (GamePhase.HAND_OVER, GamePhase.FLOWN):
                # 判断是否中途流局连庄（不计入局数）
                abortive_flow = False
                if phase == GamePhase.FLOWN and state.flow_result is not None:
                    abortive_kinds = {
                        FlowKind.NINE_NINE,
                        FlowKind.FOUR_WINDS,
                        FlowKind.FOUR_KANS,
                        FlowKind.FOUR_RIICHI,
                    }
                    abortive_flow = state.flow_result.kind in abortive_kinds

                # 局结束：中途流局连庄不计入 hand_count
                if not abortive_flow:
                    hand_count += 1

                # 调用 sinks 的 on_hand_end
                hand_result = HandResult(
                    match_id=match_id,
                    hand_index=hand_index,  # 刚完成的局号
                    hand_count=hand_count,  # 已完成局数（不含中途流局）
                )
                for s in self._sinks:
                    s.on_hand_end(hand_index, hand_result)

                hand_index += 1
                turn_index = 0
                wall_seed = seed + hand_index
                wall = tuple(shuffle_deck(build_deck(), seed=wall_seed))
                action = Action(kind=ActionKind.NEXT_ROUND, wall=wall)
                result = self._engine.step(state, action)
                state = result.new_state
                step_count += 1
                for ev in result.events:
                    events.append({"match_id": match_id, "step_index": step_count, "event": ev})
                    event_history.append(
                        kernel_event_to_context_event(
                            kernel_event=ev,
                            match_id=match_id,
                            job_id=job_id,
                            hand_index=hand_index,
                            step_index=step_count,
                            turn_index=turn_index,
                        )
                    )

                # 检查 kernel 是否自然终局
                if state.phase == GamePhase.MATCH_END:
                    break  # kernel 自然终局，outcome 将设为 completed

                # kernel 返回 IN_ROUND，检查是否应截断
                if hand_count >= max_hands:
                    break  # max_hands 截断，outcome 将设为 truncated

                continue

            # IN_ROUND: 策略决策
            if phase == GamePhase.IN_ROUND:
                board = state.board
                if board is None:
                    msg = "IN_ROUND requires board"
                    raise ValueError(msg)

                # 获取活跃座位：CALL_RESPONSE 阶段需要特殊处理
                seat = self._get_active_seat(state)
                if seat is None:
                    # 没有活跃座位，可能是阶段转换问题
                    break

                legal = self._engine.legal_actions(state, seat)
                if not legal:
                    # 无合法动作，可能是阶段转换问题
                    break

                obs = self._engine.observe(state, seat)

                ctx = DecisionContext(
                    match_id=match_id,
                    job_id=job_id,
                    hand_index=hand_index,
                    step_index=step_count,
                    seed=seed,
                    seat=seat,
                    phase=self._engine.phase(state),
                    state=state,
                    observation=obs,
                    legal_actions=legal,
                    event_history=tuple(event_history),  # v4: 注入事件快照
                )

                policy = self._policies[seat]
                decision = policy.decide(ctx)

                # 校验合法性
                if not _is_action_legal(decision.action, legal):
                    raise IllegalPolicyDecisionError(
                        seat=seat,
                        action=decision.action,
                        legal_actions=legal,
                    )

                # 执行动作
                result = self._engine.step(state, decision.action)
                state = result.new_state
                step_count += 1
                turn_index += 1

                # 收集决策/事件
                decisions.append({
                    "match_id": match_id,
                    "step_index": step_count,
                    "seat": seat,
                    "action": decision.action,
                    "parse_status": decision.parse_status,
                    "fallback_used": decision.fallback_used,
                    "latency_ms": decision.latency_ms,
                })
                for ev in result.events:
                    events.append({"match_id": match_id, "step_index": step_count, "event": ev})
                    event_history.append(
                        kernel_event_to_context_event(
                            kernel_event=ev,
                            match_id=match_id,
                            job_id=job_id,
                            hand_index=hand_index,
                            step_index=step_count,
                            turn_index=turn_index,
                        )
                    )

                # 调用 sinks
                for s in self._sinks:
                    s.on_step(ctx, decision, result)
                continue

            # 未知阶段
            msg = f"Unhandled phase: {phase}"
            raise ValueError(msg)

        # 检查停止原因
        stopped_reason = None
        outcome = "completed"

        if self._engine.is_terminal(state):
            # 自然终局：stopped_reason=None, outcome="completed"
            pass
        elif step_count >= self._step_limit:
            # step_limit 截断
            stopped_reason = "step_limit_exceeded"
            outcome = "step_limit_reached"
        else:
            # max_hands 截断：当前局已经结束（hand_count 已在循环中计入）
            stopped_reason = "max_hands_reached"
            outcome = "truncated"

        # 计算统计数据
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000

        # hand_count 已在主循环中按 HAND_OVER/FLOWN局结束时自增
        # （运行时就统计局数，不再靠 HandOverEvent 统计，避免漏计流局）

        # 获取 final_phase
        final_phase = state.phase.value

        # 从 MatchEndEvent 获取 final_points 和 rank
        final_points: tuple[int, int, int, int] = (25000, 25000, 25000, 25000)
        rank: tuple[int, int, int, int] = (1, 1, 1, 1)
        for ev in events:
            if isinstance(ev.get("event"), MatchEndEvent):
                match_end = ev["event"]
                final_points = match_end.final_scores
                rank = match_end.ranking
                break

        # 计算点数变化
        starting_points = (25000, 25000, 25000, 25000)
        point_delta = tuple(fp - sp for fp, sp in zip(final_points, starting_points, strict=True))

        result = MatchResult(
            match_id=match_id,
            job_id=job_id,
            seed=seed,
            final_state=state,
            step_count=step_count,
            events=tuple(events),
            decisions=tuple(decisions),
            stopped_reason=stopped_reason,
            outcome=outcome,
            decision_count=len(decisions),
            event_count=len(events),
            hand_count=hand_count,
            duration_ms=duration_ms,
            final_phase=final_phase,
            final_points=final_points,
            point_delta=point_delta,
            rank=rank,
        )

        for s in self._sinks:
            s.on_match_end(result)

        return result

    def iterate(
        self,
        spec: MatchSpec,
        seed: int,
    ) -> Iterator[tuple[GameState, Action, EngineStepResult]]:
        """迭代执行对局，每步返回（state, action, result）。

        用于测试和调试。

        Args:
            spec: 对局配置
            seed: 随机种子

        Yields:
            (state, action, result) 元组
        """
        state = self._engine.new_match(spec, seed)
        hand_index = 0
        step_count = 0

        # PRE_DEAL -> BEGIN_ROUND
        if state.phase == GamePhase.PRE_DEAL:
            wall = tuple(shuffle_deck(build_deck(), seed=seed))
            action = Action(kind=ActionKind.BEGIN_ROUND, wall=wall)
            result = self._engine.step(state, action)
            yield (state, action, result)
            state = result.new_state
            step_count += 1

        while not self._engine.is_terminal(state) and step_count < self._step_limit:
            phase = state.phase

            if phase in (GamePhase.HAND_OVER, GamePhase.FLOWN):
                hand_index += 1
                wall_seed = seed + hand_index
                wall = tuple(shuffle_deck(build_deck(), seed=wall_seed))
                action = Action(kind=ActionKind.NEXT_ROUND, wall=wall)
                result = self._engine.step(state, action)
                yield (state, action, result)
                state = result.new_state
                step_count += 1
                continue

            if phase == GamePhase.IN_ROUND:
                board = state.board
                if board is None:
                    msg = "IN_ROUND requires board"
                    raise ValueError(msg)

                seat = self._get_active_seat(state)
                if seat is None or not self._engine.legal_actions(state, seat):
                    step_count += 1
                    continue

                legal = self._engine.legal_actions(state, seat)
                obs = self._engine.observe(state, seat)

                ctx = DecisionContext(
                    match_id="test",
                    job_id="test",
                    hand_index=hand_index,
                    step_index=step_count,
                    seed=seed,
                    seat=seat,
                    phase=self._engine.phase(state),
                    state=state,
                    observation=obs,
                    legal_actions=legal,
                )

                policy = self._policies[seat]
                decision = policy.decide(ctx)

                if not _is_action_legal(decision.action, legal):
                    raise IllegalPolicyDecisionError(
                        seat=seat,
                        action=decision.action,
                        legal_actions=legal,
                    )

                result = self._engine.step(state, decision.action)
                yield (state, decision.action, result)
                state = result.new_state
                step_count += 1
                continue

            msg = f"Unhandled phase: {phase}"
            raise ValueError(msg)
