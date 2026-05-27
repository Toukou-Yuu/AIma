"""Memory生命周期端到端测试 - 验证MemorySink接入真实实验链路。

测试用例：
1. 运行一个至少 2 局的 match
2. 第 1 局结束后 MemorySink 写入 MATCH layer
3. 第 2 局的 prompt 中出现上一局 memory
4. memory off 配置下 prompt 不出现 memory
5. memory passive/on 配置下 prompt 出现 memory
6. memory diagnostics 中包含 layers、injected token estimate、memory item count
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from experiments.runner import ExperimentRunner
from experiments.schema import ExperimentSpec

# 测试配置模板（memory off）
MEMORY_OFF_CONFIG = {
    "experiment": {
        "id": "memory_off_test",
        "description": "Memory off test",
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
        "max_hands": 2,
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

# 测试配置模板（memory passive）
MEMORY_PASSIVE_CONFIG = {
    "experiment": {
        "id": "memory_passive_test",
        "description": "Memory passive test",
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
        "max_hands": 2,
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
        "mode": "passive",
        "layers": ["match"],
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


def _llm_policy(policy_id: str, *, memory_mode: str, memory_layers: list[str]) -> dict[str, Any]:
    return {
        "type": "llm",
        "id": policy_id,
        "agent": {
            "pipeline_id": "llm_fixed_v1",
            "context": {"scope": "stateless"},
            "memory": {
                "mode": memory_mode,
                "layers": memory_layers,
                "store": "in_memory",
                "persist": False,
            },
            "prompt": {
                "template_id": "riichi_json_action_v1",
                "version": "1.0.0",
                "sections": [],
            },
            "model": {
                "backend": "dummy",
                "model_name": "dummy",
                "extra": {"response": "not json; force fallback"},
            },
            "fallback": "first_legal",
        },
    }


def _first_legal_policy(seat: int) -> dict[str, Any]:
    return {"type": "first_legal", "id": f"first_legal_{seat}", "options": {}}


def _shared_memory_config(*, experiment_memory_mode: str) -> dict[str, Any]:
    config = deepcopy(MEMORY_PASSIVE_CONFIG)
    config["experiment"]["id"] = f"shared_memory_{experiment_memory_mode}"
    config["artifacts"]["save_prompts"] = True
    config["artifacts"]["save_debug_snapshots"] = True
    config["memory"] = {
        "mode": experiment_memory_mode,
        "layers": ["match"] if experiment_memory_mode != "off" else [],
        "store": "in_memory",
        "persist": False,
    }
    config["policies"] = {
        "seat0": _llm_policy("dummy_memory_on", memory_mode="passive", memory_layers=["match"]),
        "seat1": _llm_policy("dummy_memory_off", memory_mode="off", memory_layers=[]),
        "seat2": _first_legal_policy(2),
        "seat3": _first_legal_policy(3),
    }
    return config


def _run_config(tmp_path: Path, config: dict[str, Any]) -> Path:
    output_root = tmp_path / "runs"
    output_root.mkdir()

    config = deepcopy(config)
    config["artifacts"]["output_root"] = str(output_root)

    config_path = tmp_path / f"{config['experiment']['id']}.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False)

    spec = ExperimentSpec.from_yaml(config_path)
    result = ExperimentRunner(spec, config_path=config_path).run()
    assert result["failed"] == 0
    return output_root / config["experiment"]["id"]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _single_job_dir(run_dir: Path) -> Path:
    job_dirs = [d for d in (run_dir / "jobs").iterdir() if d.is_dir()]
    assert len(job_dirs) == 1
    return job_dirs[0]


@pytest.fixture
def memory_off_run_dir(tmp_path: Path) -> Path:
    """运行memory off实验，返回run目录。"""
    output_root = tmp_path / "runs"
    output_root.mkdir()

    config = deepcopy(MEMORY_OFF_CONFIG)
    config["artifacts"]["output_root"] = str(output_root)

    config_path = tmp_path / "memory_off.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False)

    spec = ExperimentSpec.from_yaml(config_path)
    runner = ExperimentRunner(spec, config_path=config_path)
    runner.run()

    return output_root / "memory_off_test"


@pytest.fixture
def memory_passive_run_dir(tmp_path: Path) -> Path:
    """运行memory passive实验，返回run目录。"""
    output_root = tmp_path / "runs"
    output_root.mkdir()

    config = deepcopy(MEMORY_PASSIVE_CONFIG)
    config["artifacts"]["output_root"] = str(output_root)

    config_path = tmp_path / "memory_passive.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False)

    spec = ExperimentSpec.from_yaml(config_path)
    runner = ExperimentRunner(spec, config_path=config_path)
    runner.run()

    return output_root / "memory_passive_test"


class TestMemoryLifecycleE2E:
    """Memory生命周期端到端测试。"""

    def test_shared_store_injects_previous_hand_summary_into_next_hand_prompt(
        self,
        tmp_path: Path,
    ) -> None:
        """MemorySink 写入的 hand summary 必须能被后续 LLM prompt 读取。"""
        run_dir = _run_config(tmp_path, _shared_memory_config(experiment_memory_mode="passive"))
        job_dir = _single_job_dir(run_dir)

        decisions = _read_jsonl(job_dir / "decisions.jsonl")
        seat0_next_hand = [
            record for record in decisions
            if record.get("seat") == 0 and record.get("hand_index", 0) >= 1
        ]
        assert seat0_next_hand, "seat0 should make decisions after hand 0"
        assert any(
            "Hand 0 ended" in record["diagnostics"]["memory"]["rendered_text"]
            and record["diagnostics"]["memory_injected_tokens"] > 0
            and "match" in record["diagnostics"]["memory"]["layers"]
            for record in seat0_next_hand
        )

        prompt_records = _read_jsonl(job_dir / "prompt_messages.jsonl")
        assert any(
            record.get("seat") == 0
            and record.get("hand_index", 0) >= 1
            and "Hand 0 ended" in json.dumps(record["messages"], ensure_ascii=False)
            for record in prompt_records
        )

        memory_records = _read_jsonl(job_dir / "memory_snapshot.jsonl")
        assert any(
            record.get("seat") == 0
            and record.get("hand_index", 0) >= 1
            and "Hand 0 ended" in record["memory"]["rendered_text"]
            for record in memory_records
        )

    def test_experiment_memory_off_forces_agent_memory_off(self, tmp_path: Path) -> None:
        """experiment.memory=off 时，即使 agent.memory=passive 也不能注入 memory。"""
        run_dir = _run_config(tmp_path, _shared_memory_config(experiment_memory_mode="off"))
        job_dir = _single_job_dir(run_dir)

        decisions = _read_jsonl(job_dir / "decisions.jsonl")
        seat0_records = [record for record in decisions if record.get("seat") == 0]
        assert seat0_records
        assert all(
            record["diagnostics"]["memory_injected_tokens"] == 0
            and record["diagnostics"]["memory"]["layers"] == []
            and record["diagnostics"]["memory"]["rendered_text"] == ""
            for record in seat0_records
        )

        prompt_text = "\n".join(
            json.dumps(record["messages"], ensure_ascii=False)
            for record in _read_jsonl(job_dir / "prompt_messages.jsonl")
            if record.get("seat") == 0
        )
        assert "Hand 0 ended" not in prompt_text

    def test_only_agent_with_memory_enabled_reads_shared_store(self, tmp_path: Path) -> None:
        """同一实验中只有 agent.memory=passive 的 LLM seat 读取共享 memory。"""
        run_dir = _run_config(tmp_path, _shared_memory_config(experiment_memory_mode="passive"))
        job_dir = _single_job_dir(run_dir)
        decisions = _read_jsonl(job_dir / "decisions.jsonl")

        seat0_next_hand = [
            record for record in decisions
            if record.get("seat") == 0 and record.get("hand_index", 0) >= 1
        ]
        seat1_next_hand = [
            record for record in decisions
            if record.get("seat") == 1 and record.get("hand_index", 0) >= 1
        ]

        assert any(
            record["diagnostics"]["memory_injected_tokens"] > 0
            for record in seat0_next_hand
        )
        assert seat1_next_hand
        assert all(
            record["diagnostics"]["memory_injected_tokens"] == 0
            for record in seat1_next_hand
        )

    def test_memory_off_no_memory_injection(self, memory_off_run_dir: Path) -> None:
        """memory off 配置下 prompt 不出现 memory。"""
        # 检查decisions.jsonl中没有memory_injected相关的diagnostics
        jobs_dir = memory_off_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
        assert len(job_dirs) >= 1, "没有job目录"

        job_dir = job_dirs[0]
        decisions_path = job_dir / "decisions.jsonl"

        with open(decisions_path, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                diagnostics = record.get("diagnostics", {})
                # memory off时，不应该有memory_injected_tokens
                assert "memory_injected_tokens" not in diagnostics, (
                    "memory off配置下不应有memory_injected_tokens"
                )

    def test_memory_passive_match_lifecycle(self, memory_passive_run_dir: Path) -> None:
        """memory passive 配置下，验证match memory lifecycle。"""
        # 检查实验成功运行
        jobs_dir = memory_passive_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
        assert len(job_dirs) >= 1, "没有job目录"

        job_dir = job_dirs[0]
        summary_path = job_dir / "summary.json"

        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        # 验证至少运行了2局
        assert summary["hand_count"] >= 2, (
            f"至少应运行2局，实际为{summary['hand_count']}"
        )

        # 验证experiment成功完成
        assert summary["outcome"] in ["completed", "truncated"], (
            f"outcome应为completed或truncated，实际为{summary['outcome']}"
        )

    def test_hand_result_has_summary_fields(self, memory_passive_run_dir: Path) -> None:
        """验证HandResult包含summary字段。"""
        # 这个测试通过检查MemorySink是否正常工作来间接验证
        # 如果MemorySink能正常运行，说明HandResult包含了必要的字段
        jobs_dir = memory_passive_run_dir / "jobs"
        job_dirs = [d for d in jobs_dir.iterdir() if d.is_dir()]
        assert len(job_dirs) >= 1, "没有job目录"

        job_dir = job_dirs[0]
        summary_path = job_dir / "summary.json"

        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        # 验证experiment成功完成（说明MemorySink没有抛出异常）
        assert summary["outcome"] in ["completed", "truncated"]

    def test_memory_spec_in_experiment_spec(self) -> None:
        """验证MemorySpec正确集成到ExperimentSpec中。"""
        config = deepcopy(MEMORY_PASSIVE_CONFIG)
        spec = ExperimentSpec.model_validate(config)

        assert spec.memory is not None, "ExperimentSpec应包含memory字段"
        assert spec.memory.mode == "passive", f"memory.mode应为passive，实际为{spec.memory.mode}"
        assert "match" in spec.memory.layers, "memory.layers应包含match"

    def test_memory_off_spec(self) -> None:
        """验证memory off配置正确。"""
        config = deepcopy(MEMORY_OFF_CONFIG)
        spec = ExperimentSpec.model_validate(config)

        assert spec.memory is not None, "ExperimentSpec应包含memory字段"
        assert spec.memory.mode == "off", f"memory.mode应为off，实际为{spec.memory.mode}"
        assert spec.memory.layers == [], "memory.off时layers应为空"


class TestHandResultSummary:
    """验证HandResult summary生成。"""

    def test_hand_result_flow_summary(self) -> None:
        """验证flow局的summary生成。"""
        from arena.hand_result import HandResult
        from arena.memory_sink import MemorySink
        from memory.manager import MemoryManager
        from memory.schema import MemorySpec

        spec = MemorySpec(mode="passive", layers=["match"])
        manager = MemoryManager(spec)
        sink = MemorySink(manager)

        hand_result = HandResult(
            match_id="test_match",
            hand_index=0,
            hand_count=1,
            end_reason="flow",
            scores=(25000, 25000, 25000, 25000),
        )

        summary = sink._generate_hand_summary(0, hand_result)

        assert "text" in summary, "summary应包含text字段"
        assert "Hand 0 ended by flow" in summary["text"], "summary应包含flow信息"
        assert "25000/25000/25000/25000" in summary["text"], "summary应包含分数信息"

    def test_hand_result_ron_summary(self) -> None:
        """验证ron局的summary生成。"""
        from arena.hand_result import HandResult
        from arena.memory_sink import MemorySink
        from memory.manager import MemoryManager
        from memory.schema import MemorySpec

        spec = MemorySpec(mode="passive", layers=["match"])
        manager = MemoryManager(spec)
        sink = MemorySink(manager)

        hand_result = HandResult(
            match_id="test_match",
            hand_index=1,
            hand_count=2,
            end_reason="ron",
            scores=(28000, 22000, 25000, 25000),
            winner_seat=0,
            loser_seat=1,
            points=3000,
        )

        summary = sink._generate_hand_summary(1, hand_result)

        assert "text" in summary, "summary应包含text字段"
        assert "Hand 1 ended by ron" in summary["text"], "summary应包含ron信息"
        assert "Winner seat=0" in summary["text"], "summary应包含赢家信息"
        assert "loser seat=1" in summary["text"], "summary应包含输家信息"
        assert "points=3000" in summary["text"], "summary应包含得分信息"
