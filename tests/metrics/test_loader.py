"""测试 metrics/loader.py。

测试 load_run_data, load_single_job 等函数。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from metrics.loader import (
    DecisionRecord,
    EventRecord,
    JobSummary,
    RunData,
    _load_json,
    _load_jsonl,
    _parse_decision,
    _parse_event,
    _parse_summary,
    load_run_data,
    load_single_job,
)


class TestLoadJsonl:
    """_load_jsonl 测试。"""

    def test_loads_existing_file(self) -> None:
        """加载存在的 JSONL 文件。"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"a": 1}\n')
            f.write('{"b": 2}\n')
            f.flush()
            path = Path(f.name)

        result = _load_jsonl(path)
        assert len(result) == 2
        assert result[0] == {"a": 1}
        assert result[1] == {"b": 2}

        path.unlink()

    def test_returns_empty_for_nonexistent_file(self) -> None:
        """不存在文件返回空列表。"""
        result = _load_jsonl(Path("/nonexistent/file.jsonl"))
        assert result == []

    def test_skips_empty_lines(self) -> None:
        """跳过空行。"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"a": 1}\n')
            f.write("\n")
            f.write('{"b": 2}\n')
            f.write("   \n")
            f.flush()
            path = Path(f.name)

        result = _load_jsonl(path)
        assert len(result) == 2

        path.unlink()

    def test_skips_invalid_json(self) -> None:
        """跳过无效 JSON。"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"a": 1}\n')
            f.write("not json\n")
            f.write('{"b": 2}\n')
            f.flush()
            path = Path(f.name)

        result = _load_jsonl(path)
        assert len(result) == 2

        path.unlink()

    def test_handles_empty_file(self) -> None:
        """空文件返回空列表。"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.flush()
            path = Path(f.name)

        result = _load_jsonl(path)
        assert result == []

        path.unlink()


class TestLoadJson:
    """_load_json 测试。"""

    def test_loads_existing_file(self) -> None:
        """加载存在的 JSON 文件。"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"key": "value"}, f)
            f.flush()
            path = Path(f.name)

        result = _load_json(path)
        assert result == {"key": "value"}

        path.unlink()

    def test_returns_none_for_nonexistent_file(self) -> None:
        """不存在文件返回 None。"""
        result = _load_json(Path("/nonexistent/file.json"))
        assert result is None

    def test_returns_none_for_invalid_json(self) -> None:
        """无效 JSON 返回 None。"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json")
            f.flush()
            path = Path(f.name)

        result = _load_json(path)
        assert result is None

        path.unlink()

    def test_returns_none_for_os_error(self) -> None:
        """OS 错误返回 None。"""
        # 创建一个目录而不是文件，会导致 OSError
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _load_json(Path(tmpdir))
            assert result is None


class TestParseDecision:
    """_parse_decision 测试。"""

    def test_parses_full_record(self) -> None:
        """解析完整记录。"""
        record = {
            "match_id": "m1",
            "step_index": 10,
            "seat": 0,
            "action": {"kind": "discard", "tile": "1m"},
            "parse_status": "ok",
            "fallback_used": False,
            "latency_ms": 100.5,
            "diagnostics": {"prompt_tokens": 1000},
        }

        result = _parse_decision(record)
        assert result.match_id == "m1"
        assert result.step_index == 10
        assert result.seat == 0
        assert result.action == {"kind": "discard", "tile": "1m"}
        assert result.parse_status == "ok"
        assert result.fallback_used is False
        assert result.latency_ms == 100.5
        assert result.diagnostics == {"prompt_tokens": 1000}

    def test_handles_missing_fields(self) -> None:
        """处理缺失字段。"""
        record = {}

        result = _parse_decision(record)
        assert result.match_id == ""
        assert result.step_index == 0
        assert result.seat == 0
        assert result.action == {}
        assert result.parse_status == "ok"
        assert result.fallback_used is False
        assert result.latency_ms is None

    def test_handles_none_latency(self) -> None:
        """处理 None latency。"""
        record = {"latency_ms": None}

        result = _parse_decision(record)
        assert result.latency_ms is None

    def test_handles_non_dict_action(self) -> None:
        """处理非字典 action。"""
        record = {"action": "not a dict"}

        result = _parse_decision(record)
        assert result.action == {}


class TestParseEvent:
    """_parse_event 测试。"""

    def test_parses_full_record(self) -> None:
        """解析完整记录。"""
        record = {
            "match_id": "m1",
            "step_index": 10,
            "event": {"event_type": "discard_tile", "seat": 0},
        }

        result = _parse_event(record)
        assert result.match_id == "m1"
        assert result.step_index == 10
        assert result.event == {"event_type": "discard_tile", "seat": 0}

    def test_handles_missing_fields(self) -> None:
        """处理缺失字段。"""
        record = {}

        result = _parse_event(record)
        assert result.match_id == ""
        assert result.step_index == 0
        assert result.event == {}

    def test_handles_non_dict_event(self) -> None:
        """处理非字典 event。"""
        record = {"event": "not a dict"}

        result = _parse_event(record)
        assert result.event == {}


class TestParseSummary:
    """_parse_summary 测试。"""

    def test_parses_full_data(self) -> None:
        """解析完整数据。"""
        data = {
            "match_id": "m1",
            "outcome": "completed",
            "step_count": 100,
            "hand_count": 10,
            "final_points": [35000, 28000, 22000, 15000],
            "point_delta": [10000, 3000, -3000, -10000],
            "starting_points": [25000, 25000, 25000, 25000],
            "duration_ms": 5000.0,
            "stopped_reason": "exhaustive",
        }

        result = _parse_summary(data, "j1", 42)
        assert result.match_id == "m1"
        assert result.job_id == "j1"
        assert result.seed == 42
        assert result.outcome == "completed"
        assert result.step_count == 100
        assert result.hand_count == 10
        assert result.final_points == (35000, 28000, 22000, 15000)
        assert result.point_delta == (10000, 3000, -3000, -10000)
        assert result.starting_points == (25000, 25000, 25000, 25000)
        assert result.duration_ms == 5000.0
        assert result.stopped_reason == "exhaustive"

    def test_uses_defaults_for_missing_fields(self) -> None:
        """缺失字段使用默认值。"""
        data = {}

        result = _parse_summary(data, "j1", 42)
        assert result.match_id == "j1"  # 使用 job_id
        assert result.outcome == "completed"
        assert result.step_count == 0
        assert result.hand_count == 0
        assert result.final_points == (25000, 25000, 25000, 25000)
        assert result.point_delta == (0, 0, 0, 0)
        assert result.starting_points == (25000, 25000, 25000, 25000)
        assert result.duration_ms is None
        assert result.stopped_reason is None

    def test_converts_point_values_to_int(self) -> None:
        """转换 point 值为 int。"""
        data = {
            "final_points": [35000.0, 28000.0, 22000.0, 15000.0],
        }

        result = _parse_summary(data, "j1", 42)
        assert result.final_points == (35000, 28000, 22000, 15000)
        assert all(isinstance(p, int) for p in result.final_points)


class TestLoadSingleJob:
    """load_single_job 测试。"""

    def test_loads_all_data(self) -> None:
        """加载所有数据。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)

            # 创建 decisions.jsonl
            with (job_dir / "decisions.jsonl").open("w") as f:
                f.write(json.dumps({
                    "match_id": "m1",
                    "step_index": 10,
                    "seat": 0,
                    "action": {"kind": "discard"},
                    "parse_status": "ok",
                    "fallback_used": False,
                }) + "\n")

            # 创建 events.jsonl
            with (job_dir / "events.jsonl").open("w") as f:
                f.write(json.dumps({
                    "match_id": "m1",
                    "step_index": 100,
                    "event": {"event_type": "match_end"},
                }) + "\n")

            # 创建 summary.json
            with (job_dir / "summary.json").open("w") as f:
                json.dump({
                    "match_id": "m1",
                    "outcome": "completed",
                    "step_count": 100,
                    "hand_count": 5,
                    "final_points": [25000, 25000, 25000, 25000],
                }, f)

            result = load_single_job(job_dir, "j1", 42)

            assert result.match_id == "m1"
            assert result.job_id == "j1"
            assert result.seed == 42
            assert len(result.decisions) == 1
            assert len(result.events) == 1
            assert result.summary is not None
            assert result.summary.match_id == "m1"

    def test_handles_missing_files(self) -> None:
        """处理缺失文件。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            # 不创建任何文件

            result = load_single_job(job_dir, "j1", 42)

            assert result.match_id == "j1"  # 使用 job_id
            assert result.job_id == "j1"
            assert result.decisions == []
            assert result.events == []
            assert result.summary is None

    def test_handles_partial_files(self) -> None:
        """处理部分文件缺失。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)

            # 只创建 decisions.jsonl
            with (job_dir / "decisions.jsonl").open("w") as f:
                f.write(json.dumps({
                    "match_id": "m1",
                    "step_index": 10,
                    "seat": 0,
                    "action": {},
                    "parse_status": "ok",
                    "fallback_used": False,
                }) + "\n")

            result = load_single_job(job_dir, "j1", 42)

            assert len(result.decisions) == 1
            assert result.events == []
            assert result.summary is None


class TestLoadRunData:
    """load_run_data 测试。"""

    def test_loads_from_jobs_jsonl(self) -> None:
        """从 jobs.jsonl 加载。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            jobs_dir = run_dir / "jobs"

            # 创建 jobs.jsonl
            with (run_dir / "jobs.jsonl").open("w") as f:
                f.write(json.dumps({"job_id": "j1", "seed": 42}) + "\n")
                f.write(json.dumps({"job_id": "j2", "seed": 43}) + "\n")

            # 创建 jobs 目录和子目录
            jobs_dir.mkdir()
            for job_id, seed in [("j1", 42), ("j2", 43)]:
                job_subdir = jobs_dir / job_id
                job_subdir.mkdir()

                # 创建 summary.json
                with (job_subdir / "summary.json").open("w") as f:
                    json.dump({
                        "match_id": f"m{job_id}",
                        "outcome": "completed",
                        "step_count": 100,
                        "hand_count": 5,
                        "final_points": [25000, 25000, 25000, 25000],
                    }, f)

            results = load_run_data(run_dir)

            assert len(results) == 2
            job_ids = {r.job_id for r in results}
            assert job_ids == {"j1", "j2"}
            seeds = {r.seed for r in results}
            assert seeds == {42, 43}

    def test_scans_jobs_dir_when_no_jobs_jsonl(self) -> None:
        """无 jobs.jsonl 时扫描 jobs 目录。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            jobs_dir = run_dir / "jobs"

            # 不创建 jobs.jsonl
            jobs_dir.mkdir()

            # 创建两个 job 子目录
            for job_id in ["j1", "j2"]:
                job_subdir = jobs_dir / job_id
                job_subdir.mkdir()

                # 创建 summary.json
                with (job_subdir / "summary.json").open("w") as f:
                    json.dump({"match_id": f"m{job_id}"}, f)

            results = load_run_data(run_dir)

            assert len(results) == 2
            job_ids = {r.job_id for r in results}
            assert job_ids == {"j1", "j2"}
            # 没有 jobs.jsonl 时 seed 为 0
            assert all(r.seed == 0 for r in results)

    def test_returns_empty_for_nonexistent_dir(self) -> None:
        """不存在目录返回空列表。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "nonexistent"
            results = load_run_data(run_dir)
            assert results == []

    def test_returns_empty_for_empty_jobs_dir(self) -> None:
        """空 jobs 目录返回空列表。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            (run_dir / "jobs").mkdir()

            results = load_run_data(run_dir)
            assert results == []

    def test_skips_nonexistent_job_dirs(self) -> None:
        """跳过不存在的 job 目录。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            jobs_dir = run_dir / "jobs"

            # 创建 jobs.jsonl，包含不存在的 job
            with (run_dir / "jobs.jsonl").open("w") as f:
                f.write(json.dumps({"job_id": "j1", "seed": 42}) + "\n")
                f.write(json.dumps({"job_id": "j2_missing", "seed": 43}) + "\n")

            # 只创建 j1
            jobs_dir.mkdir()
            job1_dir = jobs_dir / "j1"
            job1_dir.mkdir()
            with (job1_dir / "summary.json").open("w") as f:
                json.dump({"match_id": "m1"}, f)

            results = load_run_data(run_dir)

            # 只加载 j1
            assert len(results) == 1
            assert results[0].job_id == "j1"