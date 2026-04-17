"""牌谱回放会话模型。"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from rich.panel import Panel

from kernel import apply
from kernel.engine.state import initial_game_state
from kernel.replay_json import actions_from_match_log
from ui.interactive.data import ReplaySummary, load_replay_summary
from ui.terminal import LiveMatchViewer


class ReplaySessionState(Enum):
    """回放会话状态。"""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class ReplaySessionConfig:
    """回放会话配置。"""

    replay_path: Path
    delay_seconds: float = 0.5
    label: str = "牌谱回放"


@dataclass(frozen=True, slots=True)
class ReplaySessionSnapshot:
    """当前回放画面快照。"""

    panel: Panel | None
    action_label: str
    phase_label: str
    table_summary: str
    score_summary: str
    current_step: int
    total_steps: int
    updated_at: float | None


@dataclass(frozen=True, slots=True)
class ReplaySessionResult:
    """回放结束结果。"""

    summary: ReplaySummary
    duration_seconds: float
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        """是否正常完成。"""
        return self.error_message is None


class ReplaySession:
    """后台牌谱回放会话。"""

    def __init__(self, config: ReplaySessionConfig) -> None:
        self.config = config
        self.summary = load_replay_summary(config.replay_path)
        self._viewer = LiveMatchViewer(delay=0.0, show_reason=False, target_hands=max(1, self.summary.action_count))
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._pause = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._state = ReplaySessionState.PENDING
        self._result: ReplaySessionResult | None = None
        self._started_at: float | None = None
        self._finished_at: float | None = None
        self._snapshot = ReplaySessionSnapshot(
            panel=None,
            action_label="等待回放启动",
            phase_label="pending",
            table_summary="等待牌桌快照",
            score_summary="",
            current_step=0,
            total_steps=max(0, self.summary.action_count),
            updated_at=None,
        )

    @property
    def state(self) -> ReplaySessionState:
        """当前状态。"""
        with self._lock:
            return self._state

    @property
    def snapshot(self) -> ReplaySessionSnapshot:
        """最新快照。"""
        with self._lock:
            return self._snapshot

    @property
    def result(self) -> ReplaySessionResult | None:
        """结束结果。"""
        with self._lock:
            return self._result

    @property
    def started_at(self) -> float | None:
        """开始时间。"""
        with self._lock:
            return self._started_at

    @property
    def finished_at(self) -> float | None:
        """结束时间。"""
        with self._lock:
            return self._finished_at

    @property
    def is_finished(self) -> bool:
        """是否已结束。"""
        return self.state in {
            ReplaySessionState.FINISHED,
            ReplaySessionState.FAILED,
            ReplaySessionState.STOPPED,
        }

    @property
    def is_running(self) -> bool:
        """是否正在运行。"""
        return self.state == ReplaySessionState.RUNNING

    @property
    def is_paused(self) -> bool:
        """是否暂停中。"""
        return self.state == ReplaySessionState.PAUSED

    def start(self) -> None:
        """启动回放。"""
        if self._thread is not None:
            raise RuntimeError("replay session already started")

        with self._lock:
            self._state = ReplaySessionState.RUNNING
            self._started_at = time.time()

        self._thread = threading.Thread(
            target=self._run,
            name=f"replay-session-{self.summary.stem}",
            daemon=True,
        )
        self._thread.start()

    def wait(self, timeout: float | None = None) -> bool:
        """等待回放结束。"""
        return self._done.wait(timeout=timeout)

    def pause(self) -> None:
        """暂停回放。"""
        if self.is_finished:
            return
        self._pause.set()
        with self._lock:
            self._state = ReplaySessionState.PAUSED

    def resume(self) -> None:
        """恢复回放。"""
        if self.is_finished:
            return
        self._pause.clear()
        with self._lock:
            self._state = ReplaySessionState.RUNNING

    def toggle_pause(self) -> None:
        """切换暂停状态。"""
        if self.is_paused:
            self.resume()
        else:
            self.pause()

    def stop(self) -> None:
        """主动停止回放。"""
        self._stop.set()
        self._pause.clear()

    def set_delay(self, delay_seconds: float) -> None:
        """更新回放速度。"""
        self.config = ReplaySessionConfig(
            replay_path=self.config.replay_path,
            delay_seconds=max(0.0, delay_seconds),
            label=self.config.label,
        )

    def _set_snapshot(
        self,
        *,
        panel: Panel | None,
        action_label: str,
        phase_label: str,
        table_summary: str,
        score_summary: str,
        current_step: int,
        total_steps: int,
    ) -> None:
        with self._lock:
            self._snapshot = ReplaySessionSnapshot(
                panel=panel,
                action_label=action_label,
                phase_label=phase_label,
                table_summary=table_summary,
                score_summary=score_summary,
                current_step=current_step,
                total_steps=total_steps,
                updated_at=time.time(),
            )

    def _sleep_with_controls(self, duration: float) -> bool:
        """可响应暂停/停止的等待。"""
        deadline = time.time() + max(0.0, duration)
        while time.time() < deadline:
            if self._stop.is_set():
                return False
            while self._pause.is_set():
                if self._stop.is_set():
                    return False
                time.sleep(0.05)
            time.sleep(min(0.05, max(0.0, deadline - time.time())))
        return not self._stop.is_set()

    def _run(self) -> None:
        duration = 0.0
        try:
            import json

            data = json.loads(self.config.replay_path.read_text(encoding="utf-8"))
            actions = actions_from_match_log(data)
            reasons = data.get("reasons", [])
            total_steps = len(actions)

            state = initial_game_state()
            opening_panel = self._viewer.step(state, (), "开始回放", "")
            table_summary = self._viewer.describe_table(state)
            self._set_snapshot(
                panel=opening_panel,
                action_label=self._viewer.format_action_label("开始回放"),
                phase_label=state.phase.value,
                table_summary=table_summary.summary_line,
                score_summary=table_summary.score_line,
                current_step=0,
                total_steps=total_steps,
            )
            if not self._sleep_with_controls(self.config.delay_seconds):
                raise RuntimeError("replay stopped")

            for index, action in enumerate(actions, start=1):
                if self._stop.is_set():
                    raise RuntimeError("replay stopped")
                while self._pause.is_set():
                    if self._stop.is_set():
                        raise RuntimeError("replay stopped")
                    time.sleep(0.05)

                outcome = apply(state, action)
                state = outcome.new_state
                reason = reasons[index - 1] if index - 1 < len(reasons) else ""
                raw_action_label = f"Step {index}: {action.kind.value}"
                panel = self._viewer.step(
                    state,
                    outcome.events,
                    raw_action_label,
                    reason,
                )
                table_summary = self._viewer.describe_table(state)
                self._set_snapshot(
                    panel=panel,
                    action_label=self._viewer.format_action_label(raw_action_label),
                    phase_label=state.phase.value,
                    table_summary=table_summary.summary_line,
                    score_summary=table_summary.score_line,
                    current_step=index,
                    total_steps=total_steps,
                )
                if index != total_steps and not self._sleep_with_controls(self.config.delay_seconds):
                    raise RuntimeError("replay stopped")

            duration = time.time() - (self.started_at or time.time())
            with self._lock:
                self._result = ReplaySessionResult(
                    summary=self.summary,
                    duration_seconds=duration,
                )
                self._state = ReplaySessionState.FINISHED
                self._finished_at = time.time()
        except Exception as exc:
            duration = time.time() - (self.started_at or time.time())
            with self._lock:
                self._result = ReplaySessionResult(
                    summary=self.summary,
                    duration_seconds=duration,
                    error_message=None if str(exc) == "replay stopped" else str(exc),
                )
                self._state = ReplaySessionState.STOPPED if str(exc) == "replay stopped" else ReplaySessionState.FAILED
                self._finished_at = time.time()
        finally:
            self._done.set()
