"""端到端实验契约测试 - 使用真实ExperimentRunner验证完整链路。

测试流程：
1. 使用ExperimentSpec.from_yaml()加载配置
2. 使用ExperimentRunner真实运行实验
3. 验证artifact产物完整性
4. 运行aggregate生成metrics
5. 运行rebuild index
6. 使用RunDataSource读取数据

不手动调用MatchRunner或手动写入artifact文件。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from experiments.aggregate import main as aggregate_main
from experiments.index import get_index_path, rebuild_index
from experiments.runner import ExperimentRunner
from experiments.schema import ExperimentSpec
from ui.viewer.data_source import RunDataSource

# 测试配置模板
SMOKE_CONFIG = {
    "experiment": {
        "id": "e2e_smoke",
        "description": "E2E smoke test for artifact contract",
        "tags": ["e2e", "smoke", "test"],
    },
    "rules": {
        "version": "v3.1.3-cleanup",
        "scope_file": "RULE_SCOPE.md",
    },
    "seeds": {
        "start": 0,
        "count": 1,
        "common_walls": True,
    },
    "match": {
        "preset": "tonpuu",
        "max_hands": 4,
        "allow_negative": False,
        "step_limit": 20000,
    },
    "runtime": {
        "mode": "serial",
        "debug_snapshots": False,
        "no_persist": True,
        "resume": False,
        "fail_fast": True,
    },
    "artifacts": {
        "output_root": "runs",
        "save_replay": True,
        "save_events": True,
        "save_decisions": True,
        "save_prompts": False,
        "save_debug_snapshots": False,
        "sqlite_index": True,
    },
    "policies": {
        "seat0": {"type": "first_legal", "id": "first_legal_0", "options": {}},
        "seat1": {"type": "first_legal", "id": "first_legal_1", "options": {}},
        "seat2": {"type": "first_legal", "id": "first_legal_2", "options": {}},
        "seat3": {"type": "first_legal", "id": "first_legal_3", "options": {}},
    },
}


# ============================================================================
# Module-scope fixtures (for read-only tests)
# ============================================================================


@pytest.fixture(scope="module")
def module_e2e_run_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Module-scope fixture: 运行真实ExperimentRunner，返回run目录。

    用于只读测试，整个模块只运行一次实验。
    """
    tmp_path = tmp_path_factory.mktemp("e2e_module")

    # 创建配置文件
    config_path = tmp_path / "smoke_e2e.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(SMOKE_CONFIG, f, default_flow_style=False)

    output_root = tmp_path / "runs"
    output_root.mkdir()

    # 修改配置中的output_root
    config = SMOKE_CONFIG.copy()
    config["artifacts"]["output_root"] = str(output_root)

    config_path = tmp_path / "smoke_e2e_modified.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False)

    # 加载配置并运行
    spec = ExperimentSpec.from_yaml(config_path)
    runner = ExperimentRunner(spec, config_path=config_path)
    runner.run()

    # 返回experiment目录
    return output_root / "e2e_smoke"


@pytest.fixture(scope="module")
def module_e2e_job_dir(module_e2e_run_dir: Path) -> Path:
    """Module-scope fixture: 获取第一个job目录。"""
    jobs_dir = module_e2e_run_dir / "jobs"
    assert jobs_dir.exists(), "jobs目录不存在"

    job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
    assert len(job_dirs) >= 1, "jobs目录下无job子目录"
    return job_dirs[0]


# ============================================================================
# Function-scope fixtures (for modification tests)
# ============================================================================


@pytest.fixture
def smoke_config_path(tmp_path: Path) -> Path:
    """创建smoke配置文件。"""
    config_path = tmp_path / "smoke_e2e.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(SMOKE_CONFIG, f, default_flow_style=False)
    return config_path


@pytest.fixture
def isolated_e2e_run_dir(tmp_path: Path, smoke_config_path: Path) -> Path:
    """Function-scope fixture: 运行真实ExperimentRunner，返回run目录。

    用于修改数据的测试，每个测试有独立隔离的实验目录。
    """
    output_root = tmp_path / "runs"
    output_root.mkdir()

    # 修改配置中的output_root
    config = SMOKE_CONFIG.copy()
    config["artifacts"]["output_root"] = str(output_root)

    config_path = tmp_path / "smoke_e2e_modified.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False)

    # 加载配置并运行
    spec = ExperimentSpec.from_yaml(config_path)
    runner = ExperimentRunner(spec, config_path=config_path)
    runner.run()

    # 返回experiment目录
    return output_root / "e2e_smoke"


@pytest.fixture
def isolated_e2e_job_dir(isolated_e2e_run_dir: Path) -> Path:
    """Function-scope fixture: 获取第一个job目录。"""
    jobs_dir = isolated_e2e_run_dir / "jobs"
    assert jobs_dir.exists(), "jobs目录不存在"

    job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
    assert len(job_dirs) >= 1, "jobs目录下无job子目录"
    return job_dirs[0]


# ============================================================================
# 验证run目录结构
# ============================================================================

class TestRunDirectoryStructure:
    """验证run目录结构完整性。"""

    def test_manifest_exists(self, module_e2e_run_dir: Path) -> None:
        """manifest.yaml必须存在。"""
        manifest_path = module_e2e_run_dir / "manifest.yaml"
        assert manifest_path.exists(), "manifest.yaml不存在"

    def test_jobs_jsonl_exists(self, module_e2e_run_dir: Path) -> None:
        """jobs.jsonl必须存在且有数据。"""
        jobs_path = module_e2e_run_dir / "jobs.jsonl"
        assert jobs_path.exists(), "jobs.jsonl不存在"

        with open(jobs_path, encoding="utf-8") as f:
            content = f.read()
        assert content.strip(), "jobs.jsonl为空"

    def test_jobs_directory_exists(self, module_e2e_run_dir: Path) -> None:
        """jobs目录必须存在。"""
        jobs_dir = module_e2e_run_dir / "jobs"
        assert jobs_dir.exists(), "jobs目录不存在"

    def test_git_info_exists(self, module_e2e_run_dir: Path) -> None:
        """git_info.json必须存在。"""
        git_info_path = module_e2e_run_dir / "git_info.json"
        assert git_info_path.exists(), "git_info.json不存在"

    def test_env_info_exists(self, module_e2e_run_dir: Path) -> None:
        """env_info.json必须存在。"""
        env_info_path = module_e2e_run_dir / "env_info.json"
        assert env_info_path.exists(), "env_info.json不存在"

    def test_seed_plan_exists(self, module_e2e_run_dir: Path) -> None:
        """seed_plan.json必须存在。"""
        seed_plan_path = module_e2e_run_dir / "seed_plan.json"
        assert seed_plan_path.exists(), "seed_plan.json不存在"


# ============================================================================
# 验证job目录结构
# ============================================================================

class TestJobDirectoryStructure:
    """验证job目录结构完整性。"""

    def test_summary_json_exists(self, module_e2e_job_dir: Path) -> None:
        """summary.json必须存在。"""
        summary_path = module_e2e_job_dir / "summary.json"
        assert summary_path.exists(), "summary.json不存在"

    def test_metrics_json_exists(self, module_e2e_job_dir: Path) -> None:
        """metrics.json必须存在。"""
        metrics_path = module_e2e_job_dir / "metrics.json"
        assert metrics_path.exists(), "metrics.json不存在"

    def test_replay_json_exists(self, module_e2e_job_dir: Path) -> None:
        """replay.json必须存在。"""
        replay_path = module_e2e_job_dir / "replay.json"
        assert replay_path.exists(), "replay.json不存在"

    def test_events_jsonl_exists(self, module_e2e_job_dir: Path) -> None:
        """events.jsonl必须存在。"""
        events_path = module_e2e_job_dir / "events.jsonl"
        assert events_path.exists(), "events.jsonl不存在"

    def test_decisions_jsonl_exists(self, module_e2e_job_dir: Path) -> None:
        """decisions.jsonl必须存在。"""
        decisions_path = module_e2e_job_dir / "decisions.jsonl"
        assert decisions_path.exists(), "decisions.jsonl不存在"


# ============================================================================
# 验证summary.json契约
# ============================================================================

SUMMARY_REQUIRED_FIELDS = [
    "schema_version",
    "experiment_id",
    "match_id",
    "job_id",
    "seed",
    "match_index",
    "preset",
    "step_count",
    "outcome",
    "final_phase",
    "decision_count",
    "event_count",
    "hand_count",
    "completed_hands",
    "truncated_after_completed_hand",
    "starting_points",
    "final_points",
    "point_delta",
    "rank",
    "start_time",
    "end_time",
    "started_at",
    "finished_at",
    "duration_ms",
]


class TestSummaryContract:
    """验证summary.json契约。"""

    def test_summary_has_all_required_fields(self, module_e2e_job_dir: Path) -> None:
        """summary.json必须包含所有契约定义的字段。"""
        summary_path = module_e2e_job_dir / "summary.json"
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        missing_fields = [field for field in SUMMARY_REQUIRED_FIELDS if field not in summary]
        assert not missing_fields, (
            f"summary.json缺少必需字段: {missing_fields}. "
            f"现有字段: {list(summary.keys())}"
        )

    def test_summary_field_types(self, module_e2e_job_dir: Path) -> None:
        """summary.json字段类型正确。"""
        summary_path = module_e2e_job_dir / "summary.json"
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        # schema_version 应为整数
        assert isinstance(summary.get("schema_version"), int), "schema_version应为整数"

        # 计数字段应为非负整数
        for field in ["decision_count", "event_count", "hand_count", "step_count"]:
            value = summary.get(field)
            assert isinstance(value, int), f"{field}应为整数，实际为{type(value)}"
            assert value >= 0, f"{field}应为非负整数，实际为{value}"

        # final_phase 应为字符串
        assert isinstance(summary.get("final_phase"), str), "final_phase应为字符串"

        # final_points 应为4元素列表
        final_points = summary.get("final_points")
        assert isinstance(final_points, list), "final_points应为列表"
        assert len(final_points) == 4, f"final_points应有4个元素，实际为{len(final_points)}"

        # rank 应为4元素列表
        rank = summary.get("rank")
        assert isinstance(rank, list), "rank应为列表"
        assert len(rank) == 4, f"rank应有4个元素，实际为{len(rank)}"

        # duration_ms 应为非负数
        duration_ms = summary.get("duration_ms")
        assert isinstance(duration_ms, (int, float)), "duration_ms应为数值"
        assert duration_ms >= 0, f"duration_ms应为非负数，实际为{duration_ms}"

    def test_summary_outcome_semantics(self, module_e2e_job_dir: Path) -> None:
        """summary.json的outcome语义正确。"""
        summary_path = module_e2e_job_dir / "summary.json"
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        outcome = summary.get("outcome")
        assert outcome in ["completed", "truncated", "step_limit_reached"], (
            f"outcome应为completed/truncated/step_limit_reached，实际为{outcome}"
        )

    def test_summary_decision_count_matches_file(self, module_e2e_job_dir: Path) -> None:
        """summary.json的decision_count与decisions.jsonl行数一致。"""
        summary_path = module_e2e_job_dir / "summary.json"
        decisions_path = module_e2e_job_dir / "decisions.jsonl"

        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        with open(decisions_path, encoding="utf-8") as f:
            actual_count = sum(1 for _ in f)

        assert summary["decision_count"] == actual_count, (
            f"decision_count不一致: summary={summary['decision_count']}, "
            f"decisions.jsonl行数={actual_count}"
        )

    def test_summary_event_count_matches_file(self, module_e2e_job_dir: Path) -> None:
        """summary.json的event_count与events.jsonl行数一致。"""
        summary_path = module_e2e_job_dir / "summary.json"
        events_path = module_e2e_job_dir / "events.jsonl"

        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        with open(events_path, encoding="utf-8") as f:
            actual_count = sum(1 for _ in f)

        assert summary["event_count"] == actual_count, (
            f"event_count不一致: summary={summary['event_count']}, "
            f"events.jsonl行数={actual_count}"
        )


# ============================================================================
# 验证aggregate流程
# ============================================================================

class TestAggregateContract:
    """验证aggregate流程。"""

    def test_aggregate_generates_reports(self, isolated_e2e_run_dir: Path) -> None:
        """aggregate必须生成报告文件。"""
        # 运行aggregate
        aggregate_dir = isolated_e2e_run_dir / "aggregate"
        aggregate_dir.mkdir(exist_ok=True)

        # 模拟aggregate_main的参数
        import sys
        old_argv = sys.argv
        try:
            sys.argv = [
                "experiments.aggregate",
                "--run", str(isolated_e2e_run_dir),
                "--output", str(aggregate_dir),
            ]
            aggregate_main()
        finally:
            sys.argv = old_argv

        # 验证报告文件生成
        expected_files = [
            "match_metrics.csv",
            "decision_metrics.csv",
            "player_metrics.csv",
            "reliability_summary.json",
            "report.md",
        ]

        for filename in expected_files:
            file_path = aggregate_dir / filename
            assert file_path.exists(), f"aggregate未生成{filename}"


# ============================================================================
# 验证rebuild index流程
# ============================================================================

class TestRebuildIndexContract:
    """验证rebuild index流程。"""

    def test_rebuild_index_creates_database(self, isolated_e2e_run_dir: Path) -> None:
        """rebuild index必须创建SQLite数据库。"""
        # 删除现有数据库（如果存在）
        db_path = get_index_path(isolated_e2e_run_dir)
        if db_path.exists():
            db_path.unlink()

        # 运行rebuild
        rebuild_index(isolated_e2e_run_dir)

        # 验证数据库创建
        assert db_path.exists(), "rebuild index未创建数据库"

    def test_rebuild_index_has_required_tables(self, isolated_e2e_run_dir: Path) -> None:
        """rebuild index创建的数据库必须有必需的表。"""
        import sqlite3

        db_path = get_index_path(isolated_e2e_run_dir)
        if not db_path.exists():
            rebuild_index(isolated_e2e_run_dir)

        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}

            required_tables = ["experiments", "jobs", "matches", "artifact_paths"]
            for table in required_tables:
                assert table in tables, f"数据库缺少{table}表"
        finally:
            conn.close()


# ============================================================================
# 验证RunDataSource流程
# ============================================================================

class TestRunDataSourceContract:
    """验证RunDataSource能读取数据。"""

    def test_data_source_lists_experiments(self, isolated_e2e_run_dir: Path) -> None:
        """RunDataSource必须能列出实验。"""
        # 先rebuild index
        rebuild_index(isolated_e2e_run_dir)

        # RunDataSource需要接收output_root，而不是experiment目录
        output_root = isolated_e2e_run_dir.parent
        data_source = RunDataSource(output_root)
        experiments = data_source.list_experiments()

        assert len(experiments) >= 1, "RunDataSource未列出任何实验"

        # 验证实验信息
        exp = experiments[0]
        assert exp.experiment_id == "e2e_smoke"
        assert exp.job_count >= 1

    def test_data_source_lists_jobs(self, isolated_e2e_run_dir: Path) -> None:
        """RunDataSource必须能列出job。"""
        # 先rebuild index
        rebuild_index(isolated_e2e_run_dir)

        # RunDataSource需要接收output_root，而不是experiment目录
        output_root = isolated_e2e_run_dir.parent
        data_source = RunDataSource(output_root)
        jobs = data_source.get_jobs("e2e_smoke")

        assert len(jobs) >= 1, "RunDataSource未列出任何job"

    def test_data_source_reads_job_summary(self, isolated_e2e_run_dir: Path) -> None:
        """RunDataSource必须能读取job summary。"""
        # 先rebuild index
        rebuild_index(isolated_e2e_run_dir)

        # RunDataSource需要接收output_root，而不是experiment目录
        output_root = isolated_e2e_run_dir.parent
        data_source = RunDataSource(output_root)
        jobs = data_source.get_jobs("e2e_smoke")

        if not jobs:
            pytest.skip("没有job可测试")

        job = jobs[0]
        run_data = data_source.load_summary(job.job_id)

        assert run_data is not None, "无法读取job summary"
        assert run_data.summary is not None, "RunData缺少summary"
        assert run_data.summary.outcome in ["completed", "truncated", "step_limit_reached"], (
            f"outcome应为completed/truncated/step_limit_reached，实际为{run_data.summary.outcome}"
        )
        assert run_data.summary.hand_count > 0, "hand_count应大于0"


# ============================================================================
# 验证ID一致性
# ============================================================================

class TestIDConsistency:
    """验证跨文件ID一致性。"""

    def test_jobs_jsonl_matches_summary(self, module_e2e_run_dir: Path) -> None:
        """jobs.jsonl中的job_id与summary.json一致。"""
        jobs_path = module_e2e_run_dir / "jobs.jsonl"
        with open(jobs_path, encoding="utf-8") as f:
            job_record = json.loads(f.readline())

        jobs_dir = module_e2e_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
        assert len(job_dirs) >= 1

        job_dir = job_dirs[0]
        summary_path = job_dir / "summary.json"
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        assert job_record["job_id"] == summary["job_id"], "job_id不一致"
        assert job_record["match_id"] == summary["match_id"], "match_id不一致"
        assert job_record["seed"] == summary["seed"], "seed不一致"


# ============================================================================
# 验证完整链路
# ============================================================================

class TestFullPipeline:
    """验证完整链路：run -> aggregate -> rebuild -> data_source。"""

    def test_full_pipeline(self, tmp_path: Path, smoke_config_path: Path) -> None:
        """完整链路必须成功执行。"""
        # 1. 运行实验
        output_root = tmp_path / "runs"
        output_root.mkdir()

        config = SMOKE_CONFIG.copy()
        config["artifacts"]["output_root"] = str(output_root)

        config_path = tmp_path / "smoke_e2e_full.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

        spec = ExperimentSpec.from_yaml(config_path)
        runner = ExperimentRunner(spec, config_path=config_path)
        runner.run()

        run_dir = output_root / "e2e_smoke"
        assert run_dir.exists(), "实验运行目录不存在"

        # 2. 运行aggregate
        aggregate_dir = run_dir / "aggregate"
        aggregate_dir.mkdir(exist_ok=True)

        import sys
        old_argv = sys.argv
        try:
            sys.argv = [
                "experiments.aggregate",
                "--run", str(run_dir),
                "--output", str(aggregate_dir),
            ]
            aggregate_main()
        finally:
            sys.argv = old_argv

        # 验证aggregate输出
        assert (aggregate_dir / "reliability_summary.json").exists(), (
            "reliability_summary.json不存在"
        )

        # 3. 运行rebuild index
        rebuild_index(run_dir)

        # 验证数据库
        db_path = get_index_path(run_dir)
        assert db_path.exists(), "数据库不存在"

        # 4. 使用RunDataSource读取
        # RunDataSource需要接收output_root，而不是experiment目录
        data_source = RunDataSource(output_root)
        experiments = data_source.list_experiments()
        assert len(experiments) >= 1, "无法列出实验"

        jobs = data_source.get_jobs("e2e_smoke")
        assert len(jobs) >= 1, "无法列出job"

        # 5. 验证数据一致性
        summary_path = run_dir / "jobs" / jobs[0].job_id / "summary.json"
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        # 检查关键字段
        assert summary["outcome"] in ["completed", "truncated", "step_limit_reached"]
        assert summary["hand_count"] > 0
        assert summary["decision_count"] > 0
        assert summary["event_count"] > 0
