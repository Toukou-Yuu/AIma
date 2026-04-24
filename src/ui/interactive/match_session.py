"""交互式对局会话模型。"""

from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from rich.panel import Panel

from llm.agent.token_budget import PromptDiagnostics
from llm.config import (
    LLMRuntimeConfig,
    MatchEndCondition,
    load_llm_runtime_config,
    load_seat_llm_configs,
)
from llm.protocol import build_seat_clients
from llm.runner import RunResult, run_llm_match
from ui.interactive.stop_reasons import is_error_stop_reason
from ui.interactive.utils import load_profile_data
from ui.match_labels import format_match_target_label
from ui.terminal import LiveMatchViewer

_LOG_REPLAY_DIR = Path("logs") / "replay"
_LOG_DEBUG_DIR = Path("logs") / "debug"
_LOG_SIMPLE_DIR = Path("logs") / "simple"


class MatchSessionState(Enum):
    """对局会话状态。"""

    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class MatchSessionConfig:
    """后台对局会话配置。"""

    label: str
    config_path: Path
    seed: int
    match_end: MatchEndCondition
    dry_run: bool
    watch_enabled: bool
    watch_delay: float
    llm_runtime: LLMRuntimeConfig
    players: list[dict[str, Any]] | None = None
    session_stem: str = ""

    @property
    def target_hands(self) -> int:
        """目标局数。"""
        return self.match_end.value

    @property
    def target_label(self) -> str:
        """面向观战 UI 的对局目标标签。"""
        return format_match_target_label(self.match_end.value)


@dataclass(frozen=True, slots=True)
class MatchLogBundle:
    """对局日志路径。"""

    stem: str
    replay_path: Path
    debug_path: Path
    simple_path: Path


@dataclass(frozen=True, slots=True)
class MatchSessionSnapshot:
    """最新牌桌快照。"""

    panel: Panel | None
    action_label: str
    reason: str
    phase_label: str
    table_summary: str
    score_summary: str
    updated_at: float | None
    callback_steps: int
    prompt_diagnostics: PromptDiagnostics | None


@dataclass(frozen=True, slots=True)
class MatchSessionResult:
    """对局完成结果。"""

    run_result: RunResult | None
    logs: MatchLogBundle
    player_names: dict[int, str]
    duration_seconds: float
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        """是否正常完成。"""
        if self.run_result is None or self.error_message is not None:
            return False
        return not is_error_stop_reason(self.run_result.stopped_reason)


class _FlushingFileHandler(logging.FileHandler):
    """每条日志立即落盘。"""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


class _SessionLoggingContext(AbstractContextManager["_SessionLoggingContext"]):
    """会话日志上下文。"""

    def __init__(self, logs: MatchLogBundle) -> None:
        self._logs = logs
        self._root = logging.getLogger()
        self._previous_root_level = self._root.level
        self._console_levels: list[tuple[logging.Handler, int]] = []
        self._file_handler: _FlushingFileHandler | None = None
        self._simple_file = None

    def __enter__(self) -> "_SessionLoggingContext":
        for path in (self._logs.replay_path, self._logs.debug_path, self._logs.simple_path):
            path.parent.mkdir(parents=True, exist_ok=True)

        self._root.setLevel(logging.DEBUG)
        self._file_handler = _FlushingFileHandler(self._logs.debug_path, encoding="utf-8")
        self._file_handler.setLevel(logging.DEBUG)
        self._file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"),
        )
        self._root.addHandler(self._file_handler)

        for handler in self._root.handlers:
            if handler is self._file_handler:
                continue
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler,
                logging.FileHandler,
            ):
                self._console_levels.append((handler, handler.level))
                handler.setLevel(logging.WARNING)

        self._simple_file = self._logs.simple_path.open("w", encoding="utf-8")
        return self

    @property
    def simple_file(self):
        """可读日志文件对象。"""
        return self._simple_file

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._simple_file is not None:
            self._simple_file.close()
            self._simple_file = None

        if self._file_handler is not None:
            self._root.removeHandler(self._file_handler)
            self._file_handler.close()
            self._file_handler = None

        for handler, level in self._console_levels:
            handler.setLevel(level)
        self._console_levels.clear()
        self._root.setLevel(self._previous_root_level)


def create_session_stem(prefix: str) -> str:
    """生成会话日志 stem。"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_prefix = "".join(ch if ch.isalnum() else "-" for ch in prefix).strip("-") or "match"
    return f"{safe_prefix}-{timestamp}"


def build_match_logs(stem: str) -> MatchLogBundle:
    """构建会话日志路径。"""
    return MatchLogBundle(
        stem=stem,
        replay_path=_LOG_REPLAY_DIR / f"{stem}.json",
        debug_path=_LOG_DEBUG_DIR / f"{stem}.log",
        simple_path=_LOG_SIMPLE_DIR / f"{stem}.txt",
    )


def load_runtime_options(config_path: Path) -> LLMRuntimeConfig:
    """读取交互式对局运行参数。"""
    return load_llm_runtime_config(config_path=config_path)


def resolve_player_names(players: list[dict[str, Any]] | None) -> dict[int, str]:
    """将 seat -> 展示名。"""
    names = {seat: "默认 AI" for seat in range(4)}
    if not players:
        return names

    for entry in players:
        seat = int(entry.get("seat", 0))
        player_id = entry.get("id")
        if not player_id or player_id == "default":
            names[seat] = "默认 AI"
            continue
        profile = load_profile_data(player_id)
        names[seat] = (
            str(profile.get("name"))
            if profile and profile.get("name")
            else str(player_id)
        )
    return names


class MatchSession:
    """后台对局会话。"""

    def __init__(self, config: MatchSessionConfig) -> None:
        self.config = config
        self.logs = build_match_logs(config.session_stem)
        self.player_names = resolve_player_names(config.players)
        self._viewer = LiveMatchViewer(
            delay=config.watch_delay,
            show_reason=not config.dry_run,
            target_hands=config.target_hands,
        )
        self._viewer.set_session_summary(
            seed=config.seed,
            target_label=config.target_label,
        )
        self._viewer.set_player_names(self.player_names)
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._thread: threading.Thread | None = None
        self._state = MatchSessionState.PENDING
        self._snapshot = MatchSessionSnapshot(
            panel=None,
            action_label="等待对局启动",
            reason="",
            phase_label="pending",
            table_summary="等待牌桌快照",
            score_summary="",
            updated_at=None,
            callback_steps=0,
            prompt_diagnostics=None,
        )
        self._result: MatchSessionResult | None = None
        self._started_at: float | None = None
        self._finished_at: float | None = None

    @property
    def state(self) -> MatchSessionState:
        """当前状态。"""
        with self._lock:
            return self._state

    @property
    def result(self) -> MatchSessionResult | None:
        """最终结果。"""
        with self._lock:
            return self._result

    @property
    def snapshot(self) -> MatchSessionSnapshot:
        """最新牌桌快照。"""
        with self._lock:
            return self._snapshot

    @property
    def started_at(self) -> float | None:
        """启动时间戳。"""
        with self._lock:
            return self._started_at

    @property
    def finished_at(self) -> float | None:
        """结束时间戳。"""
        with self._lock:
            return self._finished_at

    @property
    def is_running(self) -> bool:
        """是否仍在运行。"""
        return self.state == MatchSessionState.RUNNING

    @property
    def is_finished(self) -> bool:
        """是否已结束。"""
        return self.state in (MatchSessionState.FINISHED, MatchSessionState.FAILED)

    def start(self) -> None:
        """启动后台线程。"""
        if self._thread is not None:
            raise RuntimeError("match session already started")

        with self._lock:
            self._state = MatchSessionState.RUNNING
            self._started_at = time.time()

        self._thread = threading.Thread(
            target=self._run,
            name=f"match-session-{self.config.session_stem}",
            daemon=True,
        )
        self._thread.start()

    def wait(self, timeout: float | None = None) -> bool:
        """等待会话结束。"""
        return self._done.wait(timeout=timeout)

    def _set_snapshot(
        self,
        *,
        panel: Panel | None,
        action_label: str,
        reason: str,
        phase_label: str,
        table_summary: str,
        score_summary: str,
        callback_steps: int,
        prompt_diagnostics: PromptDiagnostics | None,
    ) -> None:
        with self._lock:
            self._snapshot = MatchSessionSnapshot(
                panel=panel,
                action_label=action_label,
                reason=reason,
                phase_label=phase_label,
                table_summary=table_summary,
                score_summary=score_summary,
                updated_at=time.time(),
                callback_steps=callback_steps,
                prompt_diagnostics=prompt_diagnostics,
            )

    def _on_step(
        self,
        state,
        events: tuple,
        action_str: str = "",
        reason: str | None = "",
        prompt_diagnostics: PromptDiagnostics | None = None,
    ) -> None:
        panel = self._viewer.step(
            state,
            events,
            action_str,
            reason or "",
            prompt_diagnostics,
        )
        display_action = self._viewer.format_action_label(action_str or "等待动作")
        table_summary = self._viewer.describe_table(state)
        self._set_snapshot(
            panel=panel,
            action_label=display_action,
            reason=reason or "",
            phase_label=state.phase.value,
            table_summary=table_summary.summary_line,
            score_summary=table_summary.score_line,
            callback_steps=self.snapshot.callback_steps + 1,
            prompt_diagnostics=prompt_diagnostics,
        )
        if self.config.watch_enabled and self.config.watch_delay > 0:
            time.sleep(self.config.watch_delay)

    def _run(self) -> None:
        duration = 0.0
        try:
            with _SessionLoggingContext(self.logs) as log_context:
                seat_clients = None
                seat_llm_configs = None
                if not self.config.dry_run:
                    seat_llm_configs = load_seat_llm_configs(config_path=self.config.config_path)
                    seat_clients = build_seat_clients(seat_llm_configs)
                system_prompt = next(
                    (
                        cfg.system_prompt
                        for cfg in (seat_llm_configs or {}).values()
                        if cfg is not None
                    ),
                    None,
                )

                run_result = run_llm_match(
                    seed=self.config.seed,
                    match_end=self.config.match_end,
                    seat_clients=seat_clients,
                    dry_run=self.config.dry_run,
                    verbose=False,
                    session_audit=True,
                    simple_log_file=log_context.simple_file,
                    request_delay_seconds=(
                        0.0 if self.config.dry_run else self.config.llm_runtime.request_delay
                    ),
                    on_step_callback=self._on_step,
                    history_budget=self.config.llm_runtime.history_budget,
                    context_scope=self.config.llm_runtime.context_scope,
                    compression_level=self.config.llm_runtime.compression_level,
                    context_budget_tokens=self.config.llm_runtime.context_budget_tokens,
                    reserved_output_tokens=self.config.llm_runtime.reserved_output_tokens,
                    safety_margin_tokens=self.config.llm_runtime.safety_margin_tokens,
                    players=self.config.players,
                    system_prompt=system_prompt,
                    prompt_format=self.config.llm_runtime.prompt_format,
                    enable_conversation_logging=self.config.llm_runtime.conversation_logging_enabled,
                )
                self.logs.replay_path.write_text(
                    json.dumps(run_result.as_match_log(), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                duration = time.time() - (self.started_at or time.time())
                with self._lock:
                    self._result = MatchSessionResult(
                        run_result=run_result,
                        logs=self.logs,
                        player_names=dict(self.player_names),
                        duration_seconds=duration,
                    )
                    self._state = MatchSessionState.FINISHED
                    self._finished_at = time.time()
        except Exception as exc:
            duration = time.time() - (self.started_at or time.time())
            with self._lock:
                self._result = MatchSessionResult(
                    run_result=None,
                    logs=self.logs,
                    player_names=dict(self.player_names),
                    duration_seconds=duration,
                    error_message=str(exc),
                )
                self._state = MatchSessionState.FAILED
                self._finished_at = time.time()
        finally:
            self._done.set()
