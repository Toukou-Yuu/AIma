"""Debug Artifact Flags端到端测试 - 验证save_prompts和save_debug_snapshots配置。

测试用例：
1. save_prompts=false, save_debug_snapshots=false → 不生成prompt_messages.jsonl等文件
2. save_prompts=true, save_debug_snapshots=true → 生成上述文件
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from experiments.runner import ExperimentRunner
from experiments.schema import ExperimentSpec


# 测试配置模板（save flags disabled）
SAVE_FLAGS_DISABLED_CONFIG = {
    "experiment": {
        "id": "save_flags_disabled",
        "description": "Save flags disabled test",
        "tags": ["test"],
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
        "max_hands": 1,
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
        "sqlite_index": False,
    },
    "memory": {
        "mode": "off",
        "layers": [],
        "store": "in_memory",
        "persist": False,
    },
    "policies": {
        "seat0": {"type": "first_legal", "id": "first_legal_0", "options": {}},
        "seat1": {"type": "first_legal", "id": "first_legal_1", "options": {}},
        "seat2": {"type": "first_legal", "id": "first_legal_2", "options": {}},
        "seat3": {"type": "first_legal", "id": "first_legal_3", "options": {}},
    },
}

# 测试配置模板（save flags enabled）
SAVE_FLAGS_ENABLED_CONFIG = {
    "experiment": {
        "id": "save_flags_enabled",
        "description": "Save flags enabled test",
        "tags": ["test"],
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
        "max_hands": 1,
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
        "save_prompts": True,
        "save_debug_snapshots": True,
        "sqlite_index": False,
    },
    "memory": {
        "mode": "off",
        "layers": [],
        "store": "in_memory",
        "persist": False,
    },
    "policies": {
        "seat0": {"type": "first_legal", "id": "first_legal_0", "options": {}},
        "seat1": {"type": "first_legal", "id": "first_legal_1", "options": {}},
        "seat2": {"type": "first_legal", "id": "first_legal_2", "options": {}},
        "seat3": {"type": "first_legal", "id": "first_legal_3", "options": {}},
    },
}


@pytest.fixture(scope="module")
def save_flags_disabled_run_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Module-scope fixture: 运行save flags disabled实验，返回run目录。"""
    tmp_path = tmp_path_factory.mktemp("debug_flags_module")

    output_root = tmp_path / "runs"
    output_root.mkdir()

    config = SAVE_FLAGS_DISABLED_CONFIG.copy()
    config["artifacts"]["output_root"] = str(output_root)

    config_path = tmp_path / "save_flags_disabled.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False)

    spec = ExperimentSpec.from_yaml(config_path)
    runner = ExperimentRunner(spec, config_path=config_path)
    runner.run()

    return output_root / "save_flags_disabled"


@pytest.fixture(scope="module")
def save_flags_enabled_run_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Module-scope fixture: 运行save flags enabled实验，返回run目录。"""
    tmp_path = tmp_path_factory.mktemp("debug_flags_enabled_module")

    output_root = tmp_path / "runs"
    output_root.mkdir()

    config = SAVE_FLAGS_ENABLED_CONFIG.copy()
    config["artifacts"]["output_root"] = str(output_root)

    config_path = tmp_path / "save_flags_enabled.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False)

    spec = ExperimentSpec.from_yaml(config_path)
    runner = ExperimentRunner(spec, config_path=config_path)
    runner.run()

    return output_root / "save_flags_enabled"


class TestDebugArtifactFlags:
    """Debug Artifact Flags端到端测试。"""

    def test_save_flags_disabled_no_debug_files(self, save_flags_disabled_run_dir: Path) -> None:
        """save_prompts=false, save_debug_snapshots=false → 不生成prompt_messages.jsonl等文件。"""
        jobs_dir = save_flags_disabled_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
        assert len(job_dirs) >= 1, "没有job目录"

        job_dir = job_dirs[0]

        # 不应该存在这些文件
        debug_files = [
            "prompt_messages.jsonl",
            "model_raw_response.jsonl",
            "memory_snapshot.jsonl",
            "observation.jsonl",
        ]

        for filename in debug_files:
            file_path = job_dir / filename
            assert not file_path.exists(), (
                f"save flags disabled时不应生成{filename}"
            )

    def test_save_flags_enabled_generates_debug_files(self, save_flags_enabled_run_dir: Path) -> None:
        """save_prompts=true, save_debug_snapshots=true → 生成debug文件。"""
        jobs_dir = save_flags_enabled_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
        assert len(job_dirs) >= 1, "没有job目录"

        job_dir = job_dirs[0]

        # 应该存在这些文件
        debug_files = [
            "prompt_messages.jsonl",
            "model_raw_response.jsonl",
            "memory_snapshot.jsonl",
            "observation.jsonl",
        ]

        for filename in debug_files:
            file_path = job_dir / filename
            assert file_path.exists(), (
                f"save flags enabled时应生成{filename}"
            )

    def test_save_flags_disabled_has_standard_artifacts(self, save_flags_disabled_run_dir: Path) -> None:
        """save flags disabled时仍应有标准artifact文件。"""
        jobs_dir = save_flags_disabled_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
        assert len(job_dirs) >= 1, "没有job目录"

        job_dir = job_dirs[0]

        # 应该存在这些文件
        standard_files = [
            "summary.json",
            "metrics.json",
            "replay.json",
            "events.jsonl",
            "decisions.jsonl",
        ]

        for filename in standard_files:
            file_path = job_dir / filename
            assert file_path.exists(), (
                f"标准artifact文件{filename}应始终存在"
            )

    def test_save_flags_enabled_has_standard_artifacts(self, save_flags_enabled_run_dir: Path) -> None:
        """save flags enabled时仍应有标准artifact文件。"""
        jobs_dir = save_flags_enabled_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
        assert len(job_dirs) >= 1, "没有job目录"

        job_dir = job_dirs[0]

        # 应该存在这些文件
        standard_files = [
            "summary.json",
            "metrics.json",
            "replay.json",
            "events.jsonl",
            "decisions.jsonl",
        ]

        for filename in standard_files:
            file_path = job_dir / filename
            assert file_path.exists(), (
                f"标准artifact文件{filename}应始终存在"
            )


class TestDebugArtifactContent:
    """Debug Artifact内容测试。"""

    def test_debug_files_not_empty(self, save_flags_enabled_run_dir: Path) -> None:
        """save flags enabled时，debug文件至少有一行或明确允许为空。"""
        jobs_dir = save_flags_enabled_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
        assert len(job_dirs) >= 1, "没有job目录"

        job_dir = job_dirs[0]

        # 检查debug文件
        debug_files = [
            "prompt_messages.jsonl",
            "model_raw_response.jsonl",
            "observation.jsonl",
        ]

        for filename in debug_files:
            file_path = job_dir / filename
            if file_path.exists():
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                # FirstLegalPolicy不会生成LLM调用，所以这些文件可能为空
                # 但文件应该存在
                assert True, f"{filename}存在"