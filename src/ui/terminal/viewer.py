"""Rich 终端实时观战：纯文本动态渲染，无需图片资源。

用法::

    from ui.terminal import LiveMatchViewer
    from llm.runner import run_llm_match

    viewer = LiveMatchViewer(delay=0.5)
    viewer.run(run_llm_match(...))

或命令行::

    python -m llm --dry-run --seed 0 --watch

依赖: ``pip install rich``
"""

from __future__ import annotations

import re
import shutil
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.console import Console
from rich.live import Live
from rich.panel import Panel

from ui.match_labels import format_match_target_label
from ui.terminal.components import (
    EventFormatter,
    HandDisplay,
    LayoutBuilder,
    NameResolver,
    StatsTracker,
    TileRenderer,
)
from ui.terminal.components.tiles import localize_tile_codes

if TYPE_CHECKING:
    from kernel.engine.state import GameState
    from llm.agent.token_budget import PromptDiagnostics
    from llm.runner import RunResult


_WIND_NAMES = ["东", "南", "西", "北"]
_ACTION_KIND_LABELS = {
    "begin_round": "开局配牌",
    "draw": "摸牌",
    "discard": "打牌",
    "pass_call": "过牌",
    "call_pass_drain": "连续过牌",
    "ron": "荣和",
    "tsumo": "自摸和了",
    "open_meld": "鸣牌",
    "ankan": "暗杠",
    "shankuminkan": "加杠",
    "noop": "无操作",
}


@dataclass(frozen=True, slots=True)
class TableSummary:
    """当前牌桌的紧凑摘要。"""

    summary_line: str
    score_line: str


class LiveMatchViewer:
    """Rich 实时观战器（组件化架构）。

    使用依赖注入的组件进行渲染：
    - TileRenderer: 牌面渲染
    - StatsTracker: 统计追踪
    - EventFormatter: 事件格式化
    - HandDisplay: 手牌显示
    - LayoutBuilder: 布局构建
    - NameResolver: 名字解析
    """

    def __init__(
        self,
        delay: float = 0.5,
        show_reason: bool = True,
        target_hands: int = 8,
    ) -> None:
        """初始化观战器。

        Args:
            delay: 每步之间的延迟（秒）
            show_reason: 是否显示模型的决策理由
            target_hands: 目标局数（用于显示进度，如半庄=8）
        """
        self.delay = delay
        self.show_reason = show_reason
        self.target_hands = target_hands
        self.console = Console()

        # 初始化组件
        self._renderer = TileRenderer()
        self._name_resolver = NameResolver()
        self._stats_tracker = StatsTracker()
        self._event_formatter = EventFormatter(self._name_resolver)
        self._hand_display = HandDisplay(self._renderer, self._name_resolver)
        self._layout_builder = LayoutBuilder(
            self._renderer,
            self._stats_tracker,
            self._event_formatter,
            self._hand_display,
            self._name_resolver,
        )

        # 状态追踪
        self._last_action_str: str = ""
        self._last_reason: str = ""
        self._step = 0
        self._last_actor_seat: int | None = None
        self._seat_reasons: dict[int, str] = {}
        self._seat_names: dict[int, str] = {}
        self._table_summary = TableSummary("", "")
        self._seat_prompt_diagnostics: dict[int, PromptDiagnostics] = {}
        self._seat_cumulative_tokens: dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0}
        self._active_context_seat: int | None = None
        self._event_history: deque = deque(maxlen=64)

    def set_session_summary(self, *, seed: int, target_label: str) -> None:
        """设置观战场况区使用的会话摘要。"""
        self._layout_builder.set_session_summary(seed=seed, target_label=target_label)

    def set_player_names(self, names: dict[int, str]) -> None:
        """设置各席玩家名字（同步到所有组件）。

        Args:
            names: 座位 -> 名字映射，如 {0: "一姬", 1: "八木唯", ...}
        """
        self._seat_names = names
        self._name_resolver.set_seat_names(names)
        self._stats_tracker.set_seat_names(names)

    def format_action_label(self, action_str: str) -> str:
        """将内部动作标签格式化为面向 UI 的中文文案。"""
        if not action_str:
            return ""

        step_match = re.match(r"^(Step\s+\d+:\s*)(.+)$", action_str)
        if step_match:
            prefix, tail = step_match.groups()
            return prefix + self.format_action_label(tail)

        seat_match = re.match(r"^家([0-3])\s+(.+)$", action_str)
        if seat_match:
            seat = int(seat_match.group(1))
            tail = self._normalize_action_body(seat_match.group(2).strip())
            actor = self._name_resolver.get_name(seat, f"家{seat}")
            return f"{actor} {tail}".strip()

        return self._normalize_action_body(action_str.strip())

    def _normalize_action_body(self, body: str) -> str:
        """规范化动作正文。"""
        if not body:
            return ""
        if body in _ACTION_KIND_LABELS:
            return _ACTION_KIND_LABELS[body]
        if body.startswith("打 "):
            return f"打牌 {localize_tile_codes(body[2:].strip())}".strip()
        if body.startswith("摸 "):
            return f"摸牌 {localize_tile_codes(body[2:].strip())}".strip()
        if body.startswith("discard "):
            return f"打牌 {localize_tile_codes(body[len('discard '):].strip())}".strip()
        if body.startswith("draw "):
            return f"摸牌 {localize_tile_codes(body[len('draw '):].strip())}".strip()
        return localize_tile_codes(body)

    def step(
        self,
        state: GameState,
        events: tuple,
        action_str: str = "",
        reason: str = "",
        prompt_diagnostics: "PromptDiagnostics | None" = None,
    ) -> Panel:
        """单步渲染（供外部调用）。

        Args:
            state: 游戏状态
            events: 事件元组
            action_str: 动作描述
            reason: 决策理由
            prompt_diagnostics: 当前模型上下文 token 诊断

        Returns:
            Panel 对象（可用于 Live 更新）
        """
        self._step += 1
        self._last_action_str = self.format_action_label(action_str)
        self._last_reason = reason
        self._active_context_seat = None

        # 解析 action_str 获取行动者座位
        self._last_actor_seat = None
        seat_match = re.match(r"^家([0-3])\s+", action_str)
        if seat_match:
            self._last_actor_seat = int(seat_match.group(1))

        if self._last_actor_seat is not None and prompt_diagnostics is not None:
            self._seat_prompt_diagnostics[self._last_actor_seat] = prompt_diagnostics
            self._active_context_seat = self._last_actor_seat
            # 累计 tokens 更新
            self._seat_cumulative_tokens[self._last_actor_seat] += prompt_diagnostics.estimated_tokens

        # 只有真实 LLM 请求才更新理由；缺失 why 时显式展示状态，避免误判为 UI 丢失。
        if self._last_actor_seat is not None and prompt_diagnostics is not None:
            self._seat_reasons[self._last_actor_seat] = reason.strip() or "未提供理由"

        # 使用组件更新统计
        self._stats_tracker.update_from_events(events)
        self._event_history.extend(events)

        self._table_summary = self.describe_table(state)

        terminal_size = shutil.get_terminal_size(fallback=(160, 44))
        viewport_width = max(96, terminal_size.columns - 8)
        viewport_height = max(24, terminal_size.lines - 10)

        # 使用 LayoutBuilder 构建面板
        return self._layout_builder.build_panel(
            state,
            events,
            self._last_action_str,
            self._last_actor_seat,
            self._seat_reasons,
            self.show_reason,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            seat_prompt_diagnostics=self._seat_prompt_diagnostics,
            seat_cumulative_tokens=self._seat_cumulative_tokens,
            active_context_seat=self._active_context_seat,
            event_history=tuple(self._event_history),
        )

    def run_from_replay(
        self,
        actions: list,
        states: list,
        events_list: list,
        action_strs: list,
        reasons: list | None = None,
        token_diagnostics: list | None = None,
    ) -> None:
        """从回放数据运行动态观战。

        Args:
            actions: 动作列表
            states: 状态列表
            events_list: 事件列表
            action_strs: 动作描述列表
            reasons: 决策理由列表（可选）
            token_diagnostics: token 诊断列表（可选）
        """
        reasons = reasons or []
        token_diagnostics = token_diagnostics or []
        with Live(console=self.console, refresh_per_second=4) as live:
            for i, (state, events, action_str) in enumerate(zip(states, events_list, action_strs)):
                reason = reasons[i] if i < len(reasons) else ""
                diagnostics = token_diagnostics[i] if i < len(token_diagnostics) else None
                panel = self.step(state, events, action_str, reason, prompt_diagnostics=diagnostics)
                live.update(panel)
                time.sleep(self.delay)

    def run(self, result: RunResult) -> None:
        """从 RunResult 运行回放观战。

        注意：RunResult 只包含最终状态和 action wire，不包含中间状态。
        要完整观战，需要在 runner 中集成实时回调。
        """
        self.console.print(
            "[dim]提示: RunResult 不包含中间状态，请使用 run_with_callback 或从 replay 运行[/]"
        )
        self.console.print(f"终局: {result.final_state.phase.value}")

    def run_from_replay_file(
        self,
        replay_path: str,
        delay: float | None = None,
    ) -> None:
        """从牌谱 JSON 文件运行动态回放。

        Args:
            replay_path: 牌谱文件路径
            delay: 覆盖默认的 delay
        """
        import json
        from pathlib import Path

        from kernel import apply
        from kernel.engine.state import initial_game_state
        from kernel.replay import ReplayError
        from kernel.replay_json import actions_from_match_log

        path = Path(replay_path)
        if not path.exists():
            self.console.print(f"[red]牌谱文件不存在: {replay_path}[/]")
            return

        data = json.loads(path.read_text(encoding="utf-8"))
        reasons = data.get("reasons", [])
        raw_token_diagnostics = data.get("token_diagnostics", [])

        try:
            actions = actions_from_match_log(data)
        except (ValueError, KeyError, TypeError) as e:
            self.console.print(f"[red]牌谱解析失败: {e}[/]")
            return

        try:
            with Live(console=self.console, refresh_per_second=4) as live:
                state = initial_game_state()
                live.update(self.step(state, (), "开始回放"))
                time.sleep(self.delay if delay is None else delay)

                for i, action in enumerate(actions):
                    try:
                        outcome = apply(state, action)
                        state = outcome.new_state

                        action_str = f"Step {i+1}: {action.kind.value}"
                        reason = reasons[i] if i < len(reasons) else None
                        diagnostics = None
                        if i < len(raw_token_diagnostics):
                            diagnostics = _parse_prompt_diagnostics(raw_token_diagnostics[i])
                        live.update(
                            self.step(
                                state,
                                outcome.events,
                                action_str,
                                reason,
                                prompt_diagnostics=diagnostics,
                            )
                        )
                        time.sleep(self.delay if delay is None else delay)
                    except Exception as e:
                        self.console.print(f"[red]回放错误 at step {i}: {e}[/]")
                        break

                live.update(self.step(state, (), f"回放完成: {state.phase.value}"))

        except ReplayError as e:
            self.console.print(f"[red]回放失败: {e}[/]")

    def describe_table(self, state: GameState) -> TableSummary:
        """返回牌桌摘要，供会话快照复用。"""
        line1, line2 = self._layout_builder.describe_table_lines(state, self._last_actor_seat)
        return TableSummary(summary_line=line1.plain, score_line=line2.plain)


class LiveMatchCallback:
    """用于集成到 runner 的实时回调类。"""

    def __init__(
        self,
        delay: float = 0.5,
        show_reason: bool = True,
        target_hands: int = 8,
        seed: int | None = None,
    ) -> None:
        self.viewer = LiveMatchViewer(
            delay=delay,
            show_reason=show_reason,
            target_hands=target_hands,
        )
        if seed is not None:
            self.viewer.set_session_summary(
                seed=seed,
                target_label=format_match_target_label(target_hands),
            )
        self.live: Live | None = None
        self._start_sequence: int = 0
        self._decision_start_time: float | None = None

    def __enter__(self) -> LiveMatchCallback:
        self.live = Live(
            console=self.viewer.console,
            refresh_per_second=2,
            screen=True,
            transient=True,
        )
        self.live.__enter__()
        self.live.update(
            Panel(
                "[dim]正在初始化对局，等待 LLM 响应...",
                title="AIma",
                border_style="bright_blue",
            )
        )
        self._decision_start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.live:
            self.live.__exit__(exc_type, exc_val, exc_tb)

    def set_player_names(self, names: dict[int, str]) -> None:
        """设置各席玩家名字。"""
        self.viewer.set_player_names(names)

    def on_step(
        self,
        state: GameState,
        events: tuple,
        action_str: str = "",
        reason: str = "",
        prompt_diagnostics: "PromptDiagnostics | None" = None,
    ) -> None:
        """每步调用。"""
        if self._decision_start_time is not None:
            self._decision_start_time = time.time()

        panel = self.viewer.step(
            state,
            events,
            action_str,
            reason,
            prompt_diagnostics,
        )
        if self.live:
            self.live.update(panel)

        time.sleep(self.viewer.delay)


def demo_dry_run(seed: int = 0, steps: int = 100, delay: float = 0.3) -> None:
    """演示：dry-run 模式实时观战。"""
    import random

    from kernel import apply, shuffle_deck
    from kernel.engine.actions import Action, ActionKind
    from kernel.engine.state import initial_game_state
    from kernel.play.model import TurnPhase
    from kernel.tiles.deck import build_deck
    from llm.turns import pending_actor_seats

    viewer = LiveMatchViewer(delay=delay, show_reason=False)

    with Live(console=viewer.console, refresh_per_second=4) as live:
        state = initial_game_state()

        # BEGIN_ROUND
        deck = tuple(shuffle_deck(build_deck(), seed=seed))
        action = Action(ActionKind.BEGIN_ROUND, wall=deck)
        outcome = apply(state, action)
        state = outcome.new_state

        live.update(viewer.step(state, outcome.events, "开局配牌"))
        time.sleep(delay)

        # 模拟摸打循环
        while viewer._step < steps:
            if state.phase.value != "in_round":
                break

            board = state.board
            if not board:
                break

            pending = pending_actor_seats(state)
            if not pending:
                break

            seat = pending[0]
            turn_phase = board.turn_phase

            if turn_phase == TurnPhase.NEED_DRAW:
                if not board.live_wall:
                    break
                action = Action(ActionKind.DRAW, seat=seat)
                action_str = f"家{seat} 摸牌"

            elif turn_phase == TurnPhase.MUST_DISCARD:
                hand = board.hands[seat]
                if not hand:
                    break
                tile = random.choice(list(hand.elements()))
                action = Action(ActionKind.DISCARD, seat=seat, tile=tile)
                action_str = f"家{seat} 打牌 {tile.to_code()}"

            elif turn_phase == TurnPhase.CALL_RESPONSE:
                from kernel.api.legal_actions import legal_actions

                legals = legal_actions(state, seat)
                has_real_choice = any(la.kind.name != "PASS_CALL" for la in legals)
                action = Action(ActionKind.PASS_CALL, seat=seat)
                if has_real_choice:
                    action_str = f"家{seat} 过牌"
                else:
                    outcome = apply(state, action)
                    state = outcome.new_state
                    continue
            else:
                break

            try:
                outcome = apply(state, action)
                state = outcome.new_state
                live.update(viewer.step(state, outcome.events, action_str))
                time.sleep(delay)
            except Exception as e:
                viewer.console.print(f"[red]错误: {e}[/]")
                break

    viewer.console.print(
        f"\n[bold green]演示结束[/] 步数: {viewer._step}, 终局状态: {state.phase.value}"
    )


def _parse_prompt_diagnostics(raw: object) -> "PromptDiagnostics | None":
    """Parse replay prompt diagnostics when present."""
    if not isinstance(raw, dict):
        return None
    from llm.agent.token_budget import PromptDiagnostics

    try:
        return PromptDiagnostics.from_wire(raw)
    except (KeyError, TypeError, ValueError):
        return None


if __name__ == "__main__":
    demo_dry_run(seed=42, steps=30, delay=0.2)
