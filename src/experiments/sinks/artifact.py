"""ArtifactWriter: Writes match artifacts to files."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kernel.replay_json import game_event_to_wire

if TYPE_CHECKING:
    from arena.match_result import MatchResult
    from arena.policy import DecisionContext, PolicyDecision
    from arena.result import EngineStepResult


class ArtifactWriter:
    """EventSink that writes match artifacts to files.

    在 on_step 时写入 events.jsonl 和 decisions.jsonl，
    在 on_match_end 时写入 summary.json 和 replay.json。

    文件写入采用 per-record flush 策略，确保崩溃安全。
    """

    def __init__(
        self,
        job_dir: Path,
        match_id: str,
        job_id: str,
        seed: int,
        *,
        experiment_id: str | None = None,
        match_index: int | None = None,
        preset: str | None = None,
        started_at: str | None = None,
    ) -> None:
        """初始化 ArtifactWriter。

        Args:
            job_dir: 任务目录（用于存放 artifacts）
            match_id: 对局唯一标识符
            job_id: 批处理任务标识符
            seed: 随机种子
        """
        self._job_dir = job_dir
        self._match_id = match_id
        self._job_id = job_id
        self._seed = seed
        self._experiment_id = experiment_id
        self._match_index = match_index
        self._preset = preset
        self._started_at = started_at

        # 确保目录存在
        job_dir.mkdir(parents=True, exist_ok=True)

        # 打开文件句柄
        self._events_file = (job_dir / "events.jsonl").open("a", encoding="utf-8")
        self._decisions_file = (job_dir / "decisions.jsonl").open("a", encoding="utf-8")

    def _write_event(self, step_index: int, hand_index: int, event: dict[str, Any]) -> None:
        """写入单个事件记录到 events.jsonl。

        Args:
            step_index: 步数索引
            hand_index: 手牌索引
            event: 事件字典
        """
        record = {
            "schema_version": 1,
            "match_id": self._match_id,
            "job_id": self._job_id,
            "step_index": step_index,
            "hand_index": hand_index,
            "seed": self._seed,
            "event": event,
        }
        self._events_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._events_file.flush()

    def _write_decision(
        self,
        step_index: int,
        hand_index: int,
        seat: int,
        action: dict[str, Any],
        parse_status: str,
        fallback_used: bool,
        latency_ms: float | None,
        raw_output: str | None,
        diagnostics: dict[str, Any],
    ) -> None:
        """写入单个决策记录到 decisions.jsonl。

        Args:
            step_index: 步数索引
            seat: 玩家座位
            action: 动作字典
            parse_status: 解析状态
            fallback_used: 是否使用 fallback
            latency_ms: 决策耗时
            raw_output: 原始输出
            diagnostics: 诊断信息
        """
        record: dict[str, Any] = {
            "schema_version": 1,
            "match_id": self._match_id,
            "job_id": self._job_id,
            "step_index": step_index,
            "hand_index": hand_index,
            "seat": seat,
            "action": action,
            "parse_status": parse_status,
            "fallback_used": fallback_used,
        }
        if latency_ms is not None:
            record["latency_ms"] = latency_ms
        if raw_output is not None:
            record["raw_output"] = raw_output
        if diagnostics:
            record["diagnostics"] = diagnostics

        self._decisions_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._decisions_file.flush()

    def on_step(
        self,
        ctx: DecisionContext,
        decision: PolicyDecision,
        result: EngineStepResult,
    ) -> None:
        """每步决策后调用，写入事件和决策记录。

        Args:
            ctx: 决策上下文
            decision: 策略决策结果
            result: 引擎步进结果
        """
        # 写入所有事件
        for event in result.events:
            event_wire = game_event_to_wire(event)
            self._write_event(ctx.step_index, ctx.hand_index, event_wire)

        # 写入决策记录
        action_wire = {
            "kind": decision.action.kind.value,
        }
        if decision.action.seat is not None:
            action_wire["seat"] = decision.action.seat
        if decision.action.tile is not None:
            action_wire["tile"] = decision.action.tile.to_code()
        if decision.action.declare_riichi:
            action_wire["declare_riichi"] = True
        if decision.action.meld is not None:
            # meld 序列化需要特殊处理
            from kernel.replay_json import meld_to_wire

            action_wire["meld"] = meld_to_wire(decision.action.meld)

        self._write_decision(
            step_index=ctx.step_index,
            hand_index=ctx.hand_index,
            seat=ctx.seat,
            action=action_wire,
            parse_status=decision.parse_status,
            fallback_used=decision.fallback_used,
            latency_ms=decision.latency_ms,
            raw_output=decision.raw_output,
            diagnostics=decision.diagnostics,
        )

    def on_match_end(self, result: MatchResult) -> None:
        """对局结束时调用，写入 summary.json、metrics.json 和 replay.json。

        Args:
            result: 对局完整结果
        """
        from kernel.replay_json import action_to_wire, match_log_document

        # 统计实际写入的事件数（从 events.jsonl）
        events_path = self._job_dir / "events.jsonl"
        actual_event_count = 0
        if events_path.exists():
            with open(events_path, encoding="utf-8") as f:
                actual_event_count = sum(1 for _ in f)

        # 统计实际写入的决策数（从 decisions.jsonl）
        decisions_path = self._job_dir / "decisions.jsonl"
        actual_decision_count = 0
        if decisions_path.exists():
            with open(decisions_path, encoding="utf-8") as f:
                actual_decision_count = sum(1 for _ in f)

        # 写入 summary.json（使用实际统计值）
        ending_points = list(result.final_points)
        starting_points = [25000, 25000, 25000, 25000]
        summary = {
            "schema_version": 1,
            "experiment_id": self._experiment_id,
            "match_id": result.match_id,
            "job_id": result.job_id,
            "seed": result.seed,
            "match_index": self._match_index,
            "preset": self._preset,
            "step_count": result.step_count,
            "stopped_reason": result.stopped_reason,
            "outcome": result.outcome,
            "final_phase": result.final_phase,
            "decision_count": actual_decision_count,
            "event_count": actual_event_count,
            "hand_count": result.hand_count,
            "starting_points": starting_points,
            "final_points": ending_points,
            "point_delta": list(result.point_delta),
            "rank": list(result.rank),
            "start_time": self._started_at,
            "end_time": datetime.now(tz=timezone.utc).isoformat(),
            "duration_ms": result.duration_ms,
        }
        summary = {key: value for key, value in summary.items() if value is not None}
        summary_path = self._job_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        # 写入 metrics.json（使用实际统计值）
        metrics = {
            "schema_version": 1,
            "match_id": result.match_id,
            "job_id": result.job_id,
            "per_match": {
                "step_count": result.step_count,
                "decision_count": actual_decision_count,
                "event_count": actual_event_count,
                "hand_count": result.hand_count,
                "duration_ms": result.duration_ms,
                "final_phase": result.final_phase,
                "outcome": result.outcome,
                "parse_error_count": self._count_parse_errors(decisions_path),
                "fallback_count": self._count_fallbacks(decisions_path),
            },
            "per_seat": [
                {
                    "seat": seat,
                    "final_points": result.final_points[seat],
                    "point_delta": result.point_delta[seat],
                    "rank": result.rank[seat],
                    "win_count": 0,
                    "deal_in_count": 0,
                    "riichi_count": 0,
                    "fallback_count": self._count_fallbacks(decisions_path, seat=seat),
                    "parse_error_count": self._count_parse_errors(decisions_path, seat=seat),
                    "avg_latency_ms": self._avg_decision_field(decisions_path, "latency_ms", seat=seat),
                    "avg_prompt_tokens": self._avg_diag_field(decisions_path, "prompt_tokens", seat=seat),
                    "avg_completion_tokens": self._avg_diag_field(decisions_path, "completion_tokens", seat=seat),
                }
                for seat in range(4)
            ],
        }
        metrics_path = self._job_dir / "metrics.json"
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

        # 从 decisions 中提取 Action 对象并序列化
        actions_wire = tuple(action_to_wire(d["action"]) for d in result.decisions)

        # events 中每个 dict 的 "event" 键包含原始 GameEvent，需要序列化
        events_wire = tuple(game_event_to_wire(ev_dict["event"]) for ev_dict in result.events)

        replay = match_log_document(
            seed=result.seed,
            stopped_reason=result.stopped_reason or "normal",
            steps=result.step_count,
            final_phase=result.final_state.phase.value,
            actions_wire=actions_wire,
            events_wire=events_wire,
        )
        replay_path = self._job_dir / "replay.json"
        replay_path.write_text(json.dumps(replay, ensure_ascii=False, indent=2), encoding="utf-8")

        # 关闭文件句柄
        self._events_file.close()
        self._decisions_file.close()

    @staticmethod
    def _iter_decision_records(path: Path):
        if not path.exists():
            return
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    @classmethod
    def _count_parse_errors(cls, path: Path, *, seat: int | None = None) -> int:
        count = 0
        for record in cls._iter_decision_records(path) or ():
            if seat is not None and record.get("seat") != seat:
                continue
            if record.get("parse_status") in {"parse_failed", "match_failed", "error"}:
                count += 1
        return count

    @classmethod
    def _count_fallbacks(cls, path: Path, *, seat: int | None = None) -> int:
        count = 0
        for record in cls._iter_decision_records(path) or ():
            if seat is not None and record.get("seat") != seat:
                continue
            if record.get("fallback_used"):
                count += 1
        return count

    @classmethod
    def _avg_decision_field(cls, path: Path, field: str, *, seat: int | None = None) -> float | None:
        values: list[float] = []
        for record in cls._iter_decision_records(path) or ():
            if seat is not None and record.get("seat") != seat:
                continue
            value = record.get(field)
            if isinstance(value, int | float):
                values.append(float(value))
        return sum(values) / len(values) if values else None

    @classmethod
    def _avg_diag_field(cls, path: Path, field: str, *, seat: int | None = None) -> float | None:
        values: list[float] = []
        for record in cls._iter_decision_records(path) or ():
            if seat is not None and record.get("seat") != seat:
                continue
            diagnostics = record.get("diagnostics", {})
            if not isinstance(diagnostics, dict):
                continue
            value = diagnostics.get(field)
            if isinstance(value, int | float):
                values.append(float(value))
        return sum(values) / len(values) if values else None
