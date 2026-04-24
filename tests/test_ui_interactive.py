"""interactive 模块测试。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
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
        "  profiles:\n"
        "    main:\n"
        "      provider: openai\n"
        "      api_key: sk-test\n"
        "      base_url: https://example.com/v1\n"
        "      model: gpt-test\n"
        "  seats:\n"
        "    seat0:\n"
        "      profile: main\n"
        "    seat1:\n"
        "      profile: main\n"
        "    seat2:\n"
        "      profile: main\n"
        "    seat3:\n"
        "      profile: main\n",
        encoding="utf-8",
    )

    calls: list[object] = []

    monkeypatch.setattr(
        "ui.interactive.data.llm_connection.get_cached_probe_status",
        lambda cache_key: ("已连接", "green", "接口可达"),
    )
    monkeypatch.setattr(
        "ui.interactive.data.llm_connection.schedule_probe_refresh",
        lambda **kwargs: calls.append(kwargs),
    )

    summary = load_model_summary(config_path)

    assert summary.connection_label == "main 已连接"
    assert summary.connection_style == "green"
    assert summary.connection_note == "1 个 profile"
    assert summary.profiles[0].connection_note == "接口可达"
    assert summary.headline == "4席 / 1 profiles"
    assert summary.profiles[0].name == "main"
    assert summary.seat_bindings[0].profile_name == "main"
    assert len(calls) == 1


def test_load_model_summary_without_cache_returns_pending(tmp_path: Path, monkeypatch) -> None:
    """没有缓存时页面先显示探测中，而不是阻塞等待结果。"""
    from ui.interactive.data import load_model_summary

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "llm:\n"
        "  profiles:\n"
        "    main:\n"
        "      provider: openai\n"
        "      api_key: sk-test\n"
        "      base_url: https://example.com/v1\n"
        "      model: gpt-test\n"
        "  seats:\n"
        "    seat0:\n"
        "      profile: main\n"
        "    seat1:\n"
        "      profile: main\n"
        "    seat2:\n"
        "      profile: main\n"
        "    seat3:\n"
        "      profile: main\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "ui.interactive.data.llm_connection.get_cached_probe_status",
        lambda cache_key: None,
    )
    monkeypatch.setattr(
        "ui.interactive.data.llm_connection.schedule_probe_refresh",
        lambda **kwargs: None,
    )

    summary = load_model_summary(config_path)

    assert summary.connection_label == "main 探测中"
    assert summary.connection_note == "1 个 profile"
    assert summary.profiles[0].connection_note == "正在后台刷新"


def test_load_model_summary_probes_profiles_not_seats(tmp_path: Path, monkeypatch) -> None:
    """多个座位复用 profile 时只按 profile 探测。"""
    from ui.interactive.data import load_model_summary

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "llm:\n"
        "  profiles:\n"
        "    local:\n"
        "      provider: openai\n"
        "      api_key: sk-local\n"
        "      base_url: http://localhost:8080/v1\n"
        "      model: qwen\n"
        "    deepseek:\n"
        "      provider: openai\n"
        "      api_key: sk-deepseek\n"
        "      base_url: https://api.deepseek.com\n"
        "      model: deepseek-chat\n"
        "  seats:\n"
        "    seat0:\n"
        "      profile: local\n"
        "    seat1:\n"
        "      profile: deepseek\n"
        "    seat2:\n"
        "      profile: local\n"
        "    seat3:\n"
        "      profile: deepseek\n",
        encoding="utf-8",
    )

    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "ui.interactive.data.llm_connection.get_cached_probe_status",
        lambda cache_key: None,
    )
    monkeypatch.setattr(
        "ui.interactive.data.llm_connection.schedule_probe_refresh",
        lambda **kwargs: calls.append(kwargs),
    )

    summary = load_model_summary(config_path)

    assert summary.headline == "4席 / 2 profiles"
    assert {profile.name for profile in summary.profiles} == {"local", "deepseek"}
    assert [binding.profile_name for binding in summary.seat_bindings] == [
        "local",
        "deepseek",
        "local",
        "deepseek",
    ]
    assert len(calls) == 2


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


def test_replay_summary_separates_status_from_stop_reason(tmp_path: Path) -> None:
    """结束状态只表达完成度，结束原因表达为什么结束。"""
    from ui.interactive.data import ReplaySummary

    def make_summary(reason: str, final_phase: str = "hand_over") -> ReplaySummary:
        return ReplaySummary(
            path=tmp_path / "sample.json",
            stem="sample",
            modified_at=datetime.now(),
            seed=1,
            stopped_reason=reason,
            final_phase=final_phase,
            action_count=0,
            step_count=0,
            ranking_by_seat=None,
            final_scores=None,
        )

    hands_completed = make_summary("hands_completed:4")
    assert hands_completed.status_label == "已完成"
    assert hands_completed.reason_label == "局数完成（4局）"

    natural_end = make_summary("match_end", final_phase="match_end")
    assert natural_end.status_label == "已完成"
    assert natural_end.reason_label == "自然终局"

    truncated = make_summary("max_player_steps:500")
    assert truncated.status_label == "已截断"
    assert truncated.reason_label == "步数截断"

    failed = make_summary("step_failed:seat0 缺少 LLM client")
    assert failed.status_label == "异常"
    assert failed.reason_label == "执行失败: seat0 缺少 LLM client"


def test_match_session_result_marks_step_failed_as_failure(tmp_path: Path) -> None:
    """实时对局结果不能把 step_failed 视为正常完成。"""
    from kernel import initial_game_state
    from llm.runner import RunResult
    from ui.interactive.match_session import MatchLogBundle, MatchSessionResult

    run_result = RunResult(
        final_state=initial_game_state(),
        kernel_steps=1,
        player_steps=1,
        stopped_reason="step_failed:furiten: cannot ron",
    )
    result = MatchSessionResult(
        run_result=run_result,
        logs=MatchLogBundle(
            stem="sample",
            replay_path=tmp_path / "sample.json",
            debug_path=tmp_path / "sample.log",
            simple_path=tmp_path / "sample.txt",
        ),
        player_names={},
        duration_seconds=0.0,
    )

    assert result.succeeded is False


def test_match_target_label_uses_match_type_names() -> None:
    """观战目标使用局制语义标签，而不是裸局数。"""
    from ui.match_labels import format_match_target_label

    assert format_match_target_label(1) == "单局演示"
    assert format_match_target_label(4) == "东风战"
    assert format_match_target_label(8) == "半庄/南风战"
    assert format_match_target_label(3) == "3局自定义"


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


def test_match_launch_plan_preserves_dry_run_fallback(monkeypatch) -> None:
    """LLM 配置缺失时切到 dry-run，会进入后台会话配置。"""
    from ui.interactive.match_setup import MatchLaunchPlan, MatchSetupPage

    monkeypatch.setattr(
        "ui.interactive.match_setup.KERNEL_CONFIG_PATH",
        Path("/tmp/non-existent-aima-kernel.yaml"),
    )
    monkeypatch.setattr(
        "ui.interactive.match_setup.Prompt.confirm",
        lambda message, default=True: True,
    )

    page = MatchSetupPage()
    plan = page._build_launch_plan(
        ["ichihime", "default", "default", "default"],
        {
            "seed": "7",
            "max_hands": "4",
            "watch": True,
            "delay": "0.4",
        },
    )

    assert isinstance(plan, MatchLaunchPlan)
    assert plan.dry_run is True


def test_match_session_snapshot_action_label_is_localized(monkeypatch, tmp_path: Path) -> None:
    """正式对局快照里的最近动作必须使用本地化文案。"""
    from types import SimpleNamespace

    from rich.panel import Panel

    from llm.agent.token_budget import PromptDiagnostics
    from llm.config import LLMRuntimeConfig, MatchEndCondition
    from ui.interactive.match_session import MatchSession, MatchSessionConfig

    monkeypatch.setattr(
        "ui.interactive.match_session.resolve_player_names",
        lambda players: {0: "一姬", 1: "二阶堂", 2: "卡维", 3: "默认 AI"},
    )

    runtime = LLMRuntimeConfig(
        prompt_format="natural",
        context_scope="per_hand",
        compression_level="collapse",
        history_budget=10,
        context_budget_tokens=8192,
        reserved_output_tokens=1024,
        safety_margin_tokens=512,
        request_delay=0.0,
        conversation_logging_enabled=False,
    )
    session = MatchSession(
        MatchSessionConfig(
            label="test",
            config_path=tmp_path / "kernel.yaml",
            seed=42,
            match_end=MatchEndCondition(type="hands", value=1, allow_negative=False),
            dry_run=True,
            watch_enabled=False,
            watch_delay=0.0,
            llm_runtime=runtime,
            players=[{"id": "ichihime", "seat": 0}],
            session_stem="test-session",
        ),
    )

    monkeypatch.setattr(session._viewer, "step", lambda *args, **kwargs: Panel("ok"))

    state = SimpleNamespace(phase=SimpleNamespace(value="in_round"))
    diagnostics = PromptDiagnostics(
        estimated_tokens=100,
        prompt_budget_tokens=200,
        context_budget_tokens=300,
        reserved_output_tokens=50,
        safety_margin_tokens=50,
        selected_blocks=(),
        trimmed_blocks=(),
        max_compression_state="full",
        over_budget=False,
    )
    session._on_step(state, (), "家0 discard", None, diagnostics)

    assert session.snapshot.action_label == "一姬 打牌"
    assert session.snapshot.prompt_diagnostics == diagnostics


def test_token_summary_panel_renders_aggregate_diagnostics() -> None:
    """结算页展示整局上下文压力摘要。"""
    from rich.console import Console

    from llm.agent.token_budget import PromptDiagnostics
    from ui.interactive.token_usage import render_token_summary_panel

    diagnostics = PromptDiagnostics(
        estimated_tokens=4800,
        prompt_budget_tokens=6656,
        context_budget_tokens=8192,
        reserved_output_tokens=1024,
        safety_margin_tokens=512,
        selected_blocks=(),
        trimmed_blocks=("public_history",),
        max_compression_state="drop",
        over_budget=False,
    )
    panel = render_token_summary_panel((diagnostics,))
    console = Console(width=90, color_system=None)

    with console.capture() as capture:
        console.print(panel)

    rendered = capture.get()
    assert "上下文诊断" in rendered
    assert "4.8k / 6.7k (72%)" in rendered
    assert "公共事件x1" in rendered


def test_match_setup_summary_shows_seat_model_bindings() -> None:
    """正式对局配置页展示每席角色到 LLM profile 的绑定。"""
    from ui.interactive.data import ModelSummary, SeatModelBinding
    from ui.interactive.view_models import MatchSetupDraft, build_match_setup_rows

    model_summary = ModelSummary(
        provider_label="OpenAI 兼容",
        model="qwen",
        configured=True,
        prompt_format="json",
        conversation_logging=False,
        note="ok",
        connection_label="已连接",
        connection_style="green",
        connection_note="ok",
        seat_bindings=(
            SeatModelBinding(0, "东家", "local", "qwen", "已连接", "green"),
            SeatModelBinding(1, "南家", "deepseek", "deepseek-chat", "探测中", "yellow"),
            SeatModelBinding(2, "西家", "local", "qwen", "已连接", "green"),
            SeatModelBinding(3, "北家", "deepseek", "deepseek-chat", "探测中", "yellow"),
        ),
    )
    rows = build_match_setup_rows(
        MatchSetupDraft(
            selected_player_ids=("ichihime", "default", "default", "default"),
            seed="0",
            max_hands="8",
            watch=True,
            delay="0.5",
        ),
        player_options=[("一姬", "ichihime")],
        model_summary=model_summary,
    )
    rendered = "\n".join(
        value.plain if hasattr(value, "plain") else str(value)
        for _, value in rows
    )

    assert "一姬 -> local · qwen · 已连接" in rendered
    assert "默认 AI (dry-run) -> dry-run" in rendered


def test_home_model_binding_summary_uses_absolute_seat_codes() -> None:
    """主菜单 LLM 绑定摘要使用 S0-S3，避免误解为风位绑定。"""
    from ui.interactive.data import ModelSummary, SeatModelBinding
    from ui.interactive.screens.home import _format_model_binding_summary

    model_summary = ModelSummary(
        provider_label="OpenAI 兼容",
        model="qwen",
        configured=True,
        prompt_format="json",
        conversation_logging=False,
        note="ok",
        connection_label="已连接",
        connection_style="green",
        connection_note="ok",
        seat_bindings=(
            SeatModelBinding(0, "东家", "local", "qwen", "已连接", "green"),
            SeatModelBinding(1, "南家", "deepseek", "deepseek-chat", "已连接", "green"),
            SeatModelBinding(2, "西家", "local", "qwen", "已连接", "green"),
            SeatModelBinding(3, "北家", "deepseek", "deepseek-chat", "已连接", "green"),
        ),
    )

    assert _format_model_binding_summary(model_summary) == "S0/S2 local · S1/S3 deepseek"


def test_textual_app_starts_in_home_screen() -> None:
    """默认启动入口会进入新的 Textual 首页。"""
    from ui.interactive.tui_app import AImaTextualApp

    async def _scenario() -> None:
        app = AImaTextualApp()
        async with app.run_test(headless=True, size=(120, 40)) as pilot:
            await pilot.pause()
            assert type(app.screen).__name__ == "HomeScreen"

    asyncio.run(_scenario())


def test_textual_app_quick_mode_starts_in_quick_screen() -> None:
    """quick 参数直接进入 demo 配置 screen。"""
    from ui.interactive.tui_app import AImaTextualApp

    async def _scenario() -> None:
        app = AImaTextualApp(start_mode="quick")
        async with app.run_test(headless=True, size=(120, 40)) as pilot:
            await pilot.pause()
            assert type(app.screen).__name__ == "QuickStartScreen"

    asyncio.run(_scenario())


def test_textual_quick_start_opens_live_match_screen() -> None:
    """点击开始演示后，新的 TUI 会进入自动刷新的观战 screen。"""
    from ui.interactive.tui_app import AImaTextualApp

    async def _scenario() -> None:
        app = AImaTextualApp(start_mode="quick")
        async with app.run_test(headless=True, size=(140, 45)) as pilot:
            await pilot.pause()
            await pilot.click("#quick-start")
            await pilot.pause(1.0)
            assert type(app.screen).__name__ == "LiveMatchScreen"
            assert not list(app.screen.query("#match-live-status"))
            assert app.screen.query_one("#match-live-panel")

    asyncio.run(_scenario())


def test_textual_quick_start_reaches_settlement_screen() -> None:
    """demo 对局结束后会进入结算 screen，而不是直接回首页。"""
    from ui.interactive.tui_app import AImaTextualApp

    async def _scenario() -> None:
        app = AImaTextualApp(start_mode="quick")
        async with app.run_test(headless=True, size=(140, 45)) as pilot:
            await pilot.pause()
            app.screen.query_one("#quick-delay").value = "0.0"
            await pilot.click("#quick-start")
            for _ in range(30):
                await pilot.pause(0.3)
                if type(app.screen).__name__ == "MatchSettlementScreen":
                    break
            assert type(app.screen).__name__ == "MatchSettlementScreen"

    asyncio.run(_scenario())


def test_textual_quick_home_returns_without_hanging() -> None:
    """demo 配置页返回首页不会再因 screen 自己 pop 自己而卡住。"""
    from ui.interactive.tui_app import AImaTextualApp

    async def _scenario() -> None:
        app = AImaTextualApp(start_mode="quick")
        async with app.run_test(headless=True, size=(140, 45)) as pilot:
            await pilot.pause()
            await pilot.click("#quick-home")
            await pilot.pause(0.5)
            assert type(app.screen).__name__ == "HomeScreen"

    asyncio.run(_scenario())


def test_textual_profile_home_returns_without_hanging() -> None:
    """角色管理返回首页不会卡在错误的 pop/switch 路径上。"""
    from ui.interactive.tui_app import AImaTextualApp

    async def _scenario() -> None:
        app = AImaTextualApp()
        async with app.run_test(headless=True, size=(140, 45)) as pilot:
            await pilot.pause()
            app.screen.query_one("#home-actions").highlighted = 2
            await pilot.click("#action-open")
            await pilot.pause()
            await pilot.click("#profile-home")
            await pilot.pause(0.5)
            assert type(app.screen).__name__ == "HomeScreen"

    asyncio.run(_scenario())


def test_textual_profile_browser_has_no_redundant_detail_button() -> None:
    """角色管理页不再显示冗余的查看详情按钮。"""
    from ui.interactive.tui_app import AImaTextualApp

    async def _scenario() -> None:
        app = AImaTextualApp()
        async with app.run_test(headless=True, size=(140, 45)) as pilot:
            await pilot.pause()
            app.screen.query_one("#home-actions").highlighted = 2
            await pilot.click("#action-open")
            await pilot.pause()
            assert type(app.screen).__name__ == "ProfileBrowserScreen"
            assert list(app.screen.query("#profile-view")) == []

    asyncio.run(_scenario())


def test_textual_match_setup_player_picker_updates_button_label() -> None:
    """开始对局页的角色选择走自定义 picker，而不是空白下拉框。"""
    from ui.interactive.tui_app import AImaTextualApp

    async def _scenario() -> None:
        app = AImaTextualApp()
        async with app.run_test(headless=True, size=(140, 45)) as pilot:
            await pilot.pause()
            app.screen.query_one("#home-actions").highlighted = 1
            await pilot.click("#action-open")
            await pilot.pause()
            await pilot.click("#match-seat-0")
            await pilot.pause()
            await pilot.click("#picker-confirm")
            await pilot.pause()
            assert "默认 AI" in str(app.screen.query_one("#match-seat-0").label)

    asyncio.run(_scenario())


def test_textual_create_profile_template_picker_updates_summary() -> None:
    """创建角色的人格模板选择不再依赖空白 Select。"""
    from ui.interactive.tui_app import AImaTextualApp

    async def _scenario() -> None:
        app = AImaTextualApp()
        async with app.run_test(headless=True, size=(140, 45)) as pilot:
            await pilot.pause()
            app.screen.query_one("#home-actions").highlighted = 2
            await pilot.click("#action-open")
            await pilot.pause()
            await pilot.click("#profile-create")
            await pilot.pause()
            await pilot.click("#profile-template")
            await pilot.pause()
            picker = app.screen.query_one("#picker-options")
            picker.highlighted = 0
            await pilot.click("#picker-confirm")
            await pilot.pause()
            assert "进攻型" in str(app.screen.query_one("#profile-template").label)

    asyncio.run(_scenario())


def test_textual_add_ascii_profile_picker_updates_target() -> None:
    """添加 ASCII 时可切换目标角色，而不是卡在默认第一项。"""
    from textual.containers import HorizontalScroll
    from textual.widgets import Input

    from ui.interactive.tui_app import AImaTextualApp

    async def _scenario() -> None:
        app = AImaTextualApp()
        async with app.run_test(headless=True, size=(140, 45)) as pilot:
            await pilot.pause()
            app.screen.query_one("#home-actions").highlighted = 2
            await pilot.click("#action-open")
            await pilot.pause()
            assert any(
                isinstance(widget, HorizontalScroll)
                for widget in app.screen.query(".profile-card-x-scroll")
            )
            await pilot.click("#profile-ascii")
            await pilot.pause()
            path_input = app.screen.query_one("#ascii-path", Input)
            assert path_input.placeholder == "图片路径：绝对路径，或相对当前启动目录"
            await pilot.click("#ascii-profile")
            await pilot.pause()
            picker = app.screen.query_one("#picker-options")
            target_index = next(
                index
                for index, (label, _value) in enumerate(app.screen.options)
                if "卡维" in label
            )
            picker.highlighted = target_index
            await pilot.click("#picker-confirm")
            await pilot.pause()
            assert "卡维" in str(app.screen.query_one("#ascii-profile").label)

    asyncio.run(_scenario())
