"""interactive 模块测试。"""

from __future__ import annotations

import json
from pathlib import Path


def test_load_model_summary_marks_missing_config(tmp_path: Path) -> None:
    """缺少配置文件时返回未配置摘要。"""
    from ui.interactive.data import load_model_summary

    summary = load_model_summary(tmp_path / "missing.yaml")

    assert summary.configured is False
    assert summary.provider_label == "未配置"
    assert "缺少" in summary.note
    assert summary.connection_label == "未连接"


def test_load_model_summary_reports_probe_status(tmp_path: Path, monkeypatch) -> None:
    """模型摘要优先展示缓存结果，并触发后台刷新。"""
    from ui.interactive.data import load_model_summary

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "llm:\n"
        "  provider: openai\n"
        "  api_key: sk-test\n"
        "  base_url: https://example.com/v1\n"
        "  model: gpt-test\n",
        encoding="utf-8",
    )

    calls: list[object] = []

    monkeypatch.setattr(
        "ui.interactive.data._get_cached_probe_status",
        lambda cache_key: ("已连接", "green", "接口可达"),
    )
    monkeypatch.setattr(
        "ui.interactive.data._schedule_probe_refresh",
        lambda **kwargs: calls.append(kwargs),
    )

    summary = load_model_summary(config_path)

    assert summary.connection_label == "已连接"
    assert summary.connection_style == "green"
    assert summary.connection_note == "接口可达"
    assert len(calls) == 1


def test_load_model_summary_without_cache_returns_pending(tmp_path: Path, monkeypatch) -> None:
    """没有缓存时页面先显示探测中，而不是阻塞等待结果。"""
    from ui.interactive.data import load_model_summary

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "llm:\n"
        "  provider: openai\n"
        "  api_key: sk-test\n"
        "  base_url: https://example.com/v1\n"
        "  model: gpt-test\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("ui.interactive.data._get_cached_probe_status", lambda cache_key: None)
    monkeypatch.setattr("ui.interactive.data._schedule_probe_refresh", lambda **kwargs: None)

    summary = load_model_summary(config_path)

    assert summary.connection_label == "探测中"
    assert summary.connection_note == "正在后台刷新"


def test_load_roster_entries_reads_profile_names(tmp_path: Path, monkeypatch) -> None:
    """默认阵容会解析角色名称，没有配置的席位回退到默认 AI。"""
    from ui.interactive.data import load_roster_entries

    monkeypatch.chdir(tmp_path)
    (tmp_path / "configs/players/ichihime").mkdir(parents=True)
    (tmp_path / "configs/players/ichihime/profile.json").write_text(
        json.dumps({"name": "一姬"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "configs/aima_kernel.yaml").write_text(
        "players:\n"
        "  - id: ichihime\n"
        "    seat: 0\n",
        encoding="utf-8",
    )

    entries = load_roster_entries(tmp_path / "configs/aima_kernel.yaml")

    assert entries[0].display_name == "一姬"
    assert entries[0].mode_label == "角色配置"
    assert entries[1].display_name == "默认 AI"
    assert entries[1].mode_label == "Dry-run"


def test_load_replay_summary_extracts_match_result(tmp_path: Path) -> None:
    """牌谱摘要会从 match_end 事件提取名次和分数。"""
    from ui.interactive.data import load_replay_summary

    replay_path = tmp_path / "sample.json"
    replay_path.write_text(
        json.dumps(
            {
                "seed": 42,
                "stopped_reason": "hands_completed:1",
                "final_phase": "match_end",
                "steps": 128,
                "actions": [{}, {}],
                "events": [
                    {
                        "event_type": "match_end",
                        "ranking": [1, 4, 2, 3],
                        "final_scores": [35000, 12000, 28000, 25000],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = load_replay_summary(replay_path)

    assert summary.seed == 42
    assert summary.action_count == 2
    assert summary.ranking_by_seat == (1, 4, 2, 3)
    assert "东家#1" in summary.ranking_label
    assert "35,000" in summary.score_label


def test_replay_detail_run_uses_session_runner(monkeypatch, tmp_path: Path) -> None:
    """回放启动走进程内会话运行器，参数保持 CLI 列表形式。"""
    from ui.interactive.data import ReplaySummary
    from ui.interactive.replay import Prompt, ReplayDetailPage

    replay_path = tmp_path / "with space.json"
    replay_path.write_text("{}", encoding="utf-8")

    summary = ReplaySummary(
        path=replay_path,
        stem="with space",
        modified_at=__import__("datetime").datetime.now(),
        seed=7,
        stopped_reason="hands_completed:1",
        final_phase="match_end",
        action_count=12,
        step_count=34,
        ranking_by_seat=(1, 2, 3, 4),
        final_scores=(32000, 28000, 22000, 18000),
    )
    page = ReplayDetailPage(summary)
    page.config.delay = "0.7"

    captured: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        from ui.interactive.session_runner import SessionRunResult

        return SessionRunResult(returncode=0)

    monkeypatch.setattr(Prompt, "press_any_key", lambda message="按任意键继续...": None)
    monkeypatch.setattr("ui.interactive.replay.run_llm_session", fake_run)

    page._run_replay()

    assert captured["argv"] == [
        "--replay",
        str(replay_path),
        "--watch",
        "--watch-delay",
        "0.7",
    ]
    assert captured["kwargs"] == {}
