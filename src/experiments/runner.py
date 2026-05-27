"""ExperimentRunner: 执行实验配置的主入口。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from arena.engine import GameEngine
from arena.match_runner import MatchRunner
from experiments.job import JobRecord, JobSpec, JobState
from experiments.schema import ExperimentSpec
from experiments.sinks import ArtifactWriter, IndexSink, TeeSink
from policies.registry import REGISTRY, register_builtin_policies

if TYPE_CHECKING:
    from arena.policy import Policy


class ExperimentRunner:
    """执行实验配置的主入口。

    核心职责：
    1. 创建运行目录结构
    2. 写入元数据（manifest、git info、env info）
    3. 生成种子计划
    4. 执行作业并记录结果
    5. 支持 resume 功能
    """

    def __init__(self, spec: ExperimentSpec, config_path: str | Path | None = None) -> None:
        """初始化 ExperimentRunner。

        Args:
            spec: 实验配置
            config_path: 配置文件路径（用于写入 manifest）
        """
        self._spec = spec
        self._config_path = Path(config_path) if config_path else None
        self._run_dir: Path | None = None

        # 确保内置策略已注册
        register_builtin_policies()

    def _get_run_dir(self) -> Path:
        """获取运行目录，如不存在则创建。

        Returns:
            运行目录路径 runs/{experiment_id}/
        """
        if self._run_dir is None:
            output_root = self._spec.artifacts.output_root
            self._run_dir = Path(output_root) / self._spec.experiment.id
            self._run_dir.mkdir(parents=True, exist_ok=True)
        return self._run_dir

    def _write_manifest(self) -> None:
        """写入 manifest.yaml（配置快照）。"""
        if self._config_path is None:
            return

        run_dir = self._get_run_dir()
        manifest_path = run_dir / "manifest.yaml"

        # 复制配置文件
        shutil.copy2(self._config_path, manifest_path)

    def _write_rule_scope(self) -> None:
        """写入 RULE_SCOPE.md 副本。"""
        run_dir = self._get_run_dir()
        rule_scope_src = Path(self._spec.rules.scope_file)
        rule_scope_dst = run_dir / "RULE_SCOPE.md"

        if rule_scope_src.exists():
            shutil.copy2(rule_scope_src, rule_scope_dst)

    def _write_git_info(self) -> None:
        """写入 git 信息（commit、branch、dirty status）。"""
        run_dir = self._get_run_dir()
        git_info_path = run_dir / "git_info.json"

        git_info: dict[str, Any] = {}

        try:
            # 获取 commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                git_info["commit"] = result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        try:
            # 获取 branch name
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                git_info["branch"] = result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        try:
            # 检查 dirty status
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                git_info["dirty"] = bool(result.stdout.strip())
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        git_info_path.write_text(
            json.dumps(git_info, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_env_info(self) -> None:
        """写入环境变量（过滤敏感信息）。"""
        run_dir = self._get_run_dir()
        env_info_path = run_dir / "env_info.json"

        # 过滤敏感环境变量
        sensitive_patterns = [
            "API_KEY",
            "SECRET",
            "TOKEN",
            "PASSWORD",
            "CREDENTIAL",
            "AUTH",
        ]

        env_info: dict[str, str] = {}
        for key, value in os.environ.items():
            # 检查是否包含敏感关键词
            key_upper = key.upper()
            if any(pattern in key_upper for pattern in sensitive_patterns):
                env_info[key] = "***REDACTED***"
            else:
                env_info[key] = value

        env_info_path.write_text(
            json.dumps(env_info, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _generate_seed_plan(self) -> list[int]:
        """根据 SeedSpec 生成种子列表。

        Returns:
            种子值列表
        """
        seed_spec = self._spec.seeds

        # 如果有显式指定的种子列表，使用它
        if seed_spec.explicit is not None:
            return seed_spec.explicit

        # 否则生成连续种子
        return list(range(seed_spec.start, seed_spec.start + seed_spec.count))

    def _write_seed_plan(self, seeds: list[int]) -> None:
        """写入种子计划文件。

        Args:
            seeds: 种子值列表
        """
        run_dir = self._get_run_dir()
        seed_plan_path = run_dir / "seed_plan.json"

        seed_plan = {
            "schema_version": 1,
            "experiment_id": self._spec.experiment.id,
            "seeds": seeds,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        seed_plan_path.write_text(
            json.dumps(seed_plan, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_existing_jobs(self) -> dict[int, JobRecord]:
        """加载现有作业记录（用于 resume）。

        Returns:
            seed -> JobRecord 的映射
        """
        run_dir = self._get_run_dir()
        jobs_path = run_dir / "jobs.jsonl"

        if not jobs_path.exists():
            return {}

        existing_jobs: dict[int, JobRecord] = {}
        with jobs_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record_dict = json.loads(line)
                record = JobRecord.from_dict(record_dict)
                existing_jobs[record.seed] = record

        return existing_jobs

    def _generate_job_spec(self, seed: int, match_index: int) -> JobSpec:
        """生成作业规格（使用确定性 ID）。

        Args:
            seed: 种子值
            match_index: 对局索引（从0开始）

        Returns:
            JobSpec 实例
        """
        # 确定性 ID 格式: {experiment_id}_seed{seed:04d}_match{match_index:04d}
        job_id = f"{self._spec.experiment.id}_seed{seed:04d}_match{match_index:04d}"
        return JobSpec(
            job_id=job_id,
            experiment_id=self._spec.experiment.id,
            seed=seed,
            match_spec=self._spec.match,
            match_index=match_index,
        )

    def _create_policies(self, job_spec: JobSpec) -> dict[int, "Policy"]:
        """为作业创建策略实例。

        Args:
            job_spec: 作业规格

        Returns:
            座位 -> Policy 映射
        """
        policies: dict[int, Policy] = {}

        for seat_str, policy_spec in self._spec.policies.items():
            # 支持 "seat0" 或 "0" 格式的 key
            if seat_str.startswith("seat"):
                seat = int(seat_str[4:])
            else:
                seat = int(seat_str)
            # 使用 job_spec.seed + seat 作为策略种子，确保可复现性
            policy_seed = job_spec.seed + seat
            policy = REGISTRY.create(policy_spec, policy_seed)
            policies[seat] = policy

        return policies

    def _execute_job(self, job_spec: JobSpec) -> JobRecord:
        """执行单个作业。

        Args:
            job_spec: 作业规格

        Returns:
            JobRecord 实例
        """
        run_dir = self._get_run_dir()
        job_dir = run_dir / "jobs" / job_spec.job_id

        # 创建作业目录
        job_dir.mkdir(parents=True, exist_ok=True)

        started_at = datetime.now(tz=timezone.utc).isoformat()

        try:
            # 创建策略
            policies = self._create_policies(job_spec)

            # 创建引擎和运行器
            engine = GameEngine()

            # 创建 sinks
            artifact_writer = ArtifactWriter(
                job_dir=job_dir,
                match_id=job_spec.job_id,  # 使用 job_id 作为 match_id
                job_id=job_spec.job_id,
                seed=job_spec.seed,
                experiment_id=job_spec.experiment_id,
                match_index=job_spec.match_index,
                preset=job_spec.match_spec.preset,
                started_at=started_at,
                save_prompts=self._spec.artifacts.save_prompts,
                save_debug_snapshots=self._spec.artifacts.save_debug_snapshots,
            )

            sinks = [artifact_writer]

            # 如果启用 SQLite index，添加 IndexSink
            if self._spec.artifacts.sqlite_index:
                from experiments.index import get_index_path
                db_path = get_index_path(self._spec.artifacts.output_root)
                # 确保 index 已创建
                from experiments.index import create_index
                create_index(db_path)
                index_sink = IndexSink(
                    db_path=db_path,
                    job_id=job_spec.job_id,
                    experiment_id=job_spec.experiment_id,
                    seed=job_spec.seed,
                    started_at=started_at,
                    job_dir=job_dir,
                    preset=job_spec.match_spec.preset,
                )
                sinks.append(index_sink)

            # 如果启用 memory，添加 MemorySink
            if self._spec.memory and self._spec.memory.mode != "off":
                from arena.memory_sink import MemorySink
                from memory.manager import MemoryManager

                memory_manager = MemoryManager(self._spec.memory)
                memory_sink = MemorySink(memory_manager)
                sinks.append(memory_sink)

            tee_sink = TeeSink(sinks)

            runner = MatchRunner(
                engine=engine,
                policies=policies,
                sinks=[tee_sink],
                step_limit=self._spec.match.step_limit,
            )

            # 执行对局
            result = runner.run(
                job_spec.match_spec,
                job_spec.seed,
                job_id=job_spec.job_id,
                match_id=job_spec.job_id,  # match_id 与 job_id 相同
            )

            finished_at = datetime.now(tz=timezone.utc).isoformat()

            # 创建成功的 JobRecord
            return JobRecord(
                job_id=job_spec.job_id,
                experiment_id=job_spec.experiment_id,
                seed=job_spec.seed,
                state=JobState.SUCCEEDED,
                started_at=started_at,
                finished_at=finished_at,
                match_id=result.match_id,
                error=None,
            )

        except Exception as e:
            finished_at = datetime.now(tz=timezone.utc).isoformat()

            # 创建失败的 JobRecord
            return JobRecord(
                job_id=job_spec.job_id,
                experiment_id=job_spec.experiment_id,
                seed=job_spec.seed,
                state=JobState.FAILED,
                started_at=started_at,
                finished_at=finished_at,
                match_id=None,
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                },
            )

    def _append_job_record(self, record: JobRecord) -> None:
        """追加作业记录到 jobs.jsonl。

        Args:
            record: JobRecord 实例
        """
        run_dir = self._get_run_dir()
        jobs_path = run_dir / "jobs.jsonl"

        with jobs_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def run(self) -> dict[str, Any]:
        """执行实验的主入口。

        Returns:
            执行摘要字典
        """
        # 创建运行目录
        run_dir = self._get_run_dir()

        # 写入元数据
        self._write_manifest()
        self._write_rule_scope()
        self._write_git_info()
        self._write_env_info()

        if self._spec.artifacts.sqlite_index:
            from experiments.index import create_index, get_index_path, insert_experiment

            db_path = get_index_path(self._spec.artifacts.output_root)
            create_index(db_path)
            insert_experiment(
                db_path=db_path,
                experiment_id=self._spec.experiment.id,
                description=self._spec.experiment.description,
                tags=self._spec.experiment.tags,
                created_at=datetime.now(tz=timezone.utc).isoformat(),
                config_path=str(self._config_path) if self._config_path else None,
                run_dir=str(run_dir),
                rule_version=self._spec.rules.version,
                status="running",
            )

        # 生成种子计划
        seeds = self._generate_seed_plan()
        self._write_seed_plan(seeds)

        # 加载已有作业（用于 resume）
        existing_jobs: dict[int, JobRecord] = {}
        if self._spec.runtime.resume:
            existing_jobs = self._load_existing_jobs()

        # 执行作业
        results: dict[int, JobRecord] = dict(existing_jobs)
        succeeded = 0
        failed = 0
        skipped = 0

        for match_index, seed in enumerate(seeds):
            # 检查是否已完成
            if seed in existing_jobs:
                existing = existing_jobs[seed]
                if existing.state == JobState.SUCCEEDED:
                    skipped += 1
                    continue
                elif existing.state == JobState.FAILED and not self._spec.runtime.fail_fast:
                    # 非 fail_fast 模式下跳过失败的作业
                    skipped += 1
                    continue

            # 生成作业规格并执行
            job_spec = self._generate_job_spec(seed, match_index)
            record = self._execute_job(job_spec)

            # 记录结果
            results[seed] = record
            self._append_job_record(record)

            if record.state == JobState.SUCCEEDED:
                succeeded += 1
            else:
                failed += 1
                if self._spec.runtime.fail_fast:
                    break

        # 更新实验状态
        if self._spec.artifacts.sqlite_index:
            from experiments.index import get_index_path, update_experiment_status

            db_path = get_index_path(self._spec.artifacts.output_root)
            total_executed = succeeded + failed
            if total_executed == 0:
                exp_status = "succeeded"  # 全部跳过视为成功
            elif failed == 0:
                exp_status = "succeeded"
            elif succeeded == 0:
                exp_status = "failed"
            else:
                exp_status = "partial"

            update_experiment_status(
                db_path=db_path,
                experiment_id=self._spec.experiment.id,
                status=exp_status,
                finished_at=datetime.now(tz=timezone.utc).isoformat(),
            )

        # 返回摘要
        return {
            "experiment_id": self._spec.experiment.id,
            "total_jobs": len(seeds),
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "run_dir": str(run_dir),
        }
