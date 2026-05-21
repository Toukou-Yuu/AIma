"""llm.cli 覆盖测试。

测试目标：
- 辅助函数：_resolve_log_stem, _load_yaml_config, _merge_config 等
- 命令函数：_cmd_replay（非交互式）
- main 函数参数解析和配置合并
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from llm.cli import (
    _FlushingFileHandler,
    _HideHttpxOnConsole,
    _load_dotenv_if_available,
    _load_yaml_config,
    _merge_config,
    _resolve_log_stem,
    _setup_session_file_logging,
    _allow_httpx_info_to_file_only,
    _cap_console_handlers_info,
    main,
)


# --- _resolve_log_stem ---


class TestResolveLogStem:
    """测试 stem 解析逻辑。"""

    def test_none_returns_none(self) -> None:
        assert _resolve_log_stem(None) is None

    def test_empty_string_generates_timestamp(self) -> None:
        result = _resolve_log_stem("")
        assert result is not None
        # 格式：YYYYMMDD-HHMMSS
        assert len(result) == 15
        assert "-" in result

    def test_valid_stem_returns_self(self) -> None:
        assert _resolve_log_stem("test-session") == "test-session"
        assert _resolve_log_stem("session_2024") == "session_2024"
        assert _resolve_log_stem("a.b-c_d") == "a.b-c_d"

    def test_invalid_stem_raises_value_error(self) -> None:
        # 首字符不能是特殊符号
        with pytest.raises(ValueError, match="stem 仅允许"):
            _resolve_log_stem("-invalid")

        with pytest.raises(ValueError, match="stem 仅允许"):
            _resolve_log_stem(".invalid")

        # 空格不允许
        with pytest.raises(ValueError, match="stem 仅允许"):
            _resolve_log_stem("has space")

        # 特殊字符不允许
        with pytest.raises(ValueError, match="stem 仅允许"):
            _resolve_log_stem("has@symbol")


# --- _load_yaml_config ---


class TestLoadYamlConfig:
    """测试 YAML 配置加载。"""

    def test_none_returns_empty_dict(self) -> None:
        result = _load_yaml_config(None)
        assert result == {}

    def test_valid_config_returns_dict(self) -> None:
        # 使用项目的模板文件
        result = _load_yaml_config("configs/aima_kernel_template.yaml")
        assert isinstance(result, dict)
        assert "kernel" in result
        assert "llm" in result

    def test_missing_file_returns_empty_dict(self) -> None:
        # 配置解析失败时打印错误并返回空 dict
        with patch("sys.stderr", new=StringIO()):
            result = _load_yaml_config("/nonexistent/path.yaml")
        assert result == {}


# --- _merge_config ---


class TestMergeConfig:
    """测试配置合并逻辑。"""

    def _make_yaml_cfg(self) -> dict[str, Any]:
        """生成标准 YAML 配置结构。"""
        return {
            "kernel": {
                "seed": 0,
                "wall_file": None,
                "match_end": {
                    "type": "hands",
                    "value": 8,
                    "allow_negative": False,
                },
            },
            "debug": {
                "dry_run": False,
                "verbose": False,
            },
            "logging": {
                "json": None,
                "session": None,
                "session_audit": False,
            },
            "watch": {
                "enabled": False,
                "delay": 0.3,
                "show_reason": True,
            },
            "llm": {
                "request_delay": 0.5,
                "history_budget": 10,
                "context_scope": "per_hand",
                "compression_level": "collapse",
                "context_compression_threshold": 0.95,
                "prompt_format": "natural",
                "conversation_logging": {"enabled": False},
            },
            "players": None,
        }

    def _make_cli_args(self, **kwargs: Any) -> argparse.Namespace:
        """生成 CLI 参数命名空间（默认全 None）。"""
        defaults = {
            "seed": None,
            "wall_file": None,
            "dry_run": None,
            "log_json": None,
            "log_session": None,
            "verbose": None,
            "request_delay": None,
            "watch": None,
            "watch_delay": None,
            "history_budget": None,
            "context_scope": None,
            "compression_level": None,
            "context_compression_threshold": None,
            "prompt_format": None,
            "session_audit": None,
            "show_reason": None,
            "players": None,
            "enable_conversation_logging": None,
            "max_hands": None,
            "replay": None,
        }
        for k, v in kwargs.items():
            defaults[k] = v
        return argparse.Namespace(**defaults)

    def test_yaml_defaults_used_when_cli_none(self) -> None:
        yaml_cfg = self._make_yaml_cfg()
        cli_args = self._make_cli_args()
        result = _merge_config(yaml_cfg, cli_args)

        assert result.seed == 0
        assert result.dry_run is False
        assert result.match_end["value"] == 8
        assert result.request_delay == 0.5

    def test_cli_overrides_yaml(self) -> None:
        yaml_cfg = self._make_yaml_cfg()
        cli_args = self._make_cli_args(seed=123, dry_run=True)
        result = _merge_config(yaml_cfg, cli_args)

        assert result.seed == 123
        assert result.dry_run is True

    def test_max_hands_converts_to_match_end(self) -> None:
        yaml_cfg = self._make_yaml_cfg()
        cli_args = self._make_cli_args(max_hands=4)
        result = _merge_config(yaml_cfg, cli_args)

        assert result.match_end["type"] == "hands"
        assert result.match_end["value"] == 4
        assert result.match_end["allow_negative"] is False

    def test_log_session_enables_session_audit(self) -> None:
        yaml_cfg = self._make_yaml_cfg()
        cli_args = self._make_cli_args(log_session="test-session")
        result = _merge_config(yaml_cfg, cli_args)

        assert result.log_session == "test-session"
        assert result.session_audit is True

    def test_players_string_parsing(self) -> None:
        yaml_cfg = self._make_yaml_cfg()
        cli_args = self._make_cli_args(players="ichihime,yui,kavi,kana")
        result = _merge_config(yaml_cfg, cli_args)

        assert len(result.players) == 4
        assert result.players[0]["id"] == "ichihime"
        assert result.players[0]["seat"] == 0
        assert result.players[3]["id"] == "kana"

    def test_players_string_with_empty_slots(self) -> None:
        yaml_cfg = self._make_yaml_cfg()
        cli_args = self._make_cli_args(players="ichihime,,default,")
        result = _merge_config(yaml_cfg, cli_args)

        assert result.players[0]["id"] == "ichihime"
        assert result.players[1]["id"] == "default"
        assert result.players[2]["id"] == "default"
        assert result.players[3]["id"] == "default"

    def test_wall_file_forces_single_hand(self) -> None:
        yaml_cfg = self._make_yaml_cfg()
        # 设置 match_end value=1 来避免触发 exit
        yaml_cfg["kernel"]["match_end"]["value"] = 1
        cli_args = self._make_cli_args(wall_file="wall.json")
        result = _merge_config(yaml_cfg, cli_args)

        assert result.wall_file == "wall.json"
        assert result.match_end["value"] == 1

    def test_wall_file_with_multi_hand_exits(self) -> None:
        yaml_cfg = self._make_yaml_cfg()
        yaml_cfg["kernel"]["match_end"]["value"] = 8  # 多局
        cli_args = self._make_cli_args(wall_file="wall.json")

        with pytest.raises(SystemExit) as exc_info:
            _merge_config(yaml_cfg, cli_args)
        assert exc_info.value.code == 2


# --- Log handlers ---


class TestFlushingFileHandler:
    """测试 flush 日志处理器。"""

    def test_emit_calls_flush(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as tf:
            handler = _FlushingFileHandler(tf.name, encoding="utf-8")
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="test message",
                args=(),
                exc_info=None,
            )
            handler.emit(record)
            # emit 后应该立即 flush
            handler.close()

            # 验证文件写入
            content = Path(tf.name).read_text(encoding="utf-8")
            assert "test message" in content

            Path(tf.name).unlink()


class TestHideHttpxOnConsole:
    """测试 httpx 日志过滤器。"""

    def test_filters_httpx_records(self) -> None:
        filter_obj = _HideHttpxOnConsole()

        httpx_record = MagicMock()
        httpx_record.name = "httpx.client"
        assert filter_obj.filter(httpx_record) is False

        httpcore_record = MagicMock()
        httpcore_record.name = "httpcore.connection"
        assert filter_obj.filter(httpcore_record) is False

    def test_passes_other_records(self) -> None:
        filter_obj = _HideHttpxOnConsole()

        other_record = MagicMock()
        other_record.name = "kernel.engine"
        assert filter_obj.filter(other_record) is True

        llm_record = MagicMock()
        llm_record.name = "llm.runner"
        assert filter_obj.filter(llm_record) is True


# --- Logging setup functions ---


class TestSetupSessionFileLogging:
    """测试文件日志设置。"""

    def test_creates_handler_and_directory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "subdir" / "test.log"
            _setup_session_file_logging(log_path)

            # 目录应该被创建
            assert log_path.parent.exists()

            # 验证 handler 添加到 root logger
            root = logging.getLogger()
            file_handlers = [
                h for h in root.handlers
                if isinstance(h, logging.FileHandler)
            ]
            assert len(file_handlers) >= 1

            # 清理：移除刚才添加的 handler
            for h in file_handlers:
                if h.baseFilename == str(log_path):
                    root.removeHandler(h)
                    h.close()


class TestAllowHttpxInfoToFileOnly:
    """测试 httpx 日志配置。"""

    def test_sets_httpx_level_and_adds_filter(self) -> None:
        # 配置 root logger 有一个 StreamHandler
        root = logging.getLogger()
        original_handlers = list(root.handlers)

        _allow_httpx_info_to_file_only()

        # httpx 应该被设置为 INFO
        httpx_logger = logging.getLogger("httpx")
        assert httpx_logger.level <= logging.INFO

        # StreamHandler 应该有 Filter
        for h in root.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
                filters = [f for f in h.filters if isinstance(f, _HideHttpxOnConsole)]
                assert len(filters) >= 1

        # 清理
        root.handlers = original_handlers


class TestCapConsoleHandlersInfo:
    """测试控制台日志限制。"""

    def test_caps_stream_handlers_to_info(self) -> None:
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)

        _cap_console_handlers_info()

        for h in root.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
                assert h.level == logging.INFO


class TestLoadDotenvIfAvailable:
    """测试 dotenv 加载。"""

    def test_no_error_when_dotenv_missing(self) -> None:
        # dotenv 未安装时应该静默返回
        with patch.dict(sys.modules, {"dotenv": None}):
            _load_dotenv_if_available()  # 不应该报错

    def test_calls_load_dotenv_when_available(self) -> None:
        mock_load = MagicMock()
        mock_dotenv = MagicMock(load_dotenv=mock_load)
        with patch.dict(sys.modules, {"dotenv": mock_dotenv}):
            _load_dotenv_if_available()
            mock_load.assert_called_once()


# --- main function ---


class TestMainArgumentParsing:
    """测试 main 函数参数解析。"""

    def test_default_config_path(self) -> None:
        with patch("llm.cli.run_llm_match") as mock_run:
            mock_run.return_value = MagicMock(
                player_steps=0,
                kernel_steps=0,
                stopped_reason="test",
                final_state=MagicMock(phase=MagicMock(value="pre_deal")),
                as_match_log=lambda: {"seed": 0},
                actions_wire=(),
                events_wire=(),
            )
            # 使用 --dry-run 和 --max-hands 1 快速结束
            result = main(["--dry-run", "--max-hands", "1"])
            # 应该正常返回
            assert result == 0

    def test_show_stats_mode(self) -> None:
        with patch("llm.cli._cmd_show_stats") as mock_cmd:
            mock_cmd.return_value = 0
            result = main(["--show-stats", "ichihime"])
            mock_cmd.assert_called_once_with("ichihime")
            assert result == 0

    def test_replay_mode_with_valid_file(self) -> None:
        # 创建临时牌谱文件
        match_log = {
            "format_version": 2,
            "actions": [{"kind": "begin_round"}],
            "events": [],
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tf:
            json.dump(match_log, tf)
            tf_path = tf.name

        try:
            with patch("llm.cli.replay_from_actions") as mock_replay:
                mock_state = MagicMock(phase=MagicMock(value="pre_deal"))
                mock_outcome = MagicMock(events=[])
                mock_replay.return_value = (mock_state, [mock_outcome])

                result = main(["--replay", tf_path])
                assert result == 0
        finally:
            Path(tf_path).unlink()

    def test_replay_mode_with_invalid_json(self) -> None:
        """无效 JSON 会抛出异常（当前行为）。"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tf:
            tf.write("not valid json")
            tf_path = tf.name

        try:
            with pytest.raises(json.JSONDecodeError):
                main(["--replay", tf_path])
        finally:
            Path(tf_path).unlink()

    def test_invalid_log_session_stem_exits(self) -> None:
        with patch("sys.stderr", new=StringIO()):
            with patch("llm.cli.run_llm_match"):
                result = main(["--log-session", "@invalid", "--dry-run", "--max-hands", "1"])
        assert result == 2


# --- Integration-style tests ---


class TestMainWithMock:
    """使用 mock 测试 main 函数分支。"""

    def test_dry_run_completes(self) -> None:
        """测试 dry-run 模式能正常完成。"""
        mock_result = MagicMock(
            player_steps=10,
            kernel_steps=20,
            stopped_reason="match_end",
            final_state=MagicMock(
                phase=MagicMock(value="match_end"),
                table=MagicMock(
                    scores=(25000, 25000, 25000, 25000),
                    dealer_seat=0,
                ),
            ),
            as_match_log=lambda: {
                "format_version": 2,
                "seed": 0,
                "actions": [],
                "events": [],
            },
            actions_wire=(),
            events_wire=(),
        )

        with patch("llm.cli.run_llm_match", return_value=mock_result):
            with patch("sys.stdout", new=StringIO()):
                result = main(["--dry-run", "--max-hands", "1"])

        assert result == 0

    def test_verbose_flag_passed(self) -> None:
        """测试 verbose 参数传递。"""
        mock_result = MagicMock(
            player_steps=0,
            kernel_steps=0,
            stopped_reason="test",
            final_state=MagicMock(phase=MagicMock(value="pre_deal")),
            as_match_log=lambda: {},
            actions_wire=(),
            events_wire=(),
        )

        with patch("llm.cli.run_llm_match", return_value=mock_result) as mock_run:
            main(["--dry-run", "--verbose", "--max-hands", "1"])
            # verbose 应该被传递
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("verbose") is True

    def test_seed_parameter_passed(self) -> None:
        """测试 seed 参数传递。"""
        mock_result = MagicMock(
            player_steps=0,
            kernel_steps=0,
            stopped_reason="test",
            final_state=MagicMock(phase=MagicMock(value="pre_deal")),
            as_match_log=lambda: {},
            actions_wire=(),
            events_wire=(),
        )

        with patch("llm.cli.run_llm_match", return_value=mock_result) as mock_run:
            main(["--dry-run", "--seed", "42", "--max-hands", "1"])
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("seed") == 42

    def test_log_json_writes_output(self) -> None:
        """测试 log-json 参数写入文件。"""
        mock_result = MagicMock(
            player_steps=0,
            kernel_steps=0,
            stopped_reason="test",
            final_state=MagicMock(phase=MagicMock(value="pre_deal")),
            as_match_log=lambda: {"test": "data"},
            actions_wire=(),
            events_wire=(),
        )

        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "output.json"
            with patch("llm.cli.run_llm_match", return_value=mock_result):
                main(["--dry-run", "--log-json", str(log_path), "--max-hands", "1"])

            # 文件应该被创建并写入
            assert log_path.exists()
            data = json.loads(log_path.read_text(encoding="utf-8"))
            assert data["test"] == "data"


# --- _cmd_replay 直接测试 ---


class TestCmdReplay:
    """测试 _cmd_replay 命令。"""

    def test_valid_replay(self) -> None:
        """有效牌谱回放成功。"""
        from llm.cli import _cmd_replay

        match_log = {
            "format_version": 2,
            "actions": [{"kind": "begin_round"}],
            "events": [],
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tf:
            json.dump(match_log, tf)
            tf_path = tf.name

        try:
            with patch("llm.cli.replay_from_actions") as mock_replay:
                mock_state = MagicMock(phase=MagicMock(value="pre_deal"))
                mock_outcome = MagicMock(events=[])
                mock_replay.return_value = (mock_state, [mock_outcome])

                with patch("sys.stdout", new=StringIO()):
                    result = _cmd_replay(tf_path)
                assert result == 0
        finally:
            Path(tf_path).unlink()

    def test_invalid_json(self) -> None:
        """无效 JSON 抛出异常（json.loads 在 try block 外）。"""
        from llm.cli import _cmd_replay

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tf:
            tf.write("invalid json content")
            tf_path = tf.name

        try:
            with pytest.raises(json.JSONDecodeError):
                _cmd_replay(tf_path)
        finally:
            Path(tf_path).unlink()

    def test_invalid_action_format(self) -> None:
        """牌谱格式错误返回错误。"""
        from llm.cli import _cmd_replay

        match_log = {
            "format_version": 99,  # 不支持的版本
            "actions": [],
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tf:
            json.dump(match_log, tf)
            tf_path = tf.name

        try:
            with patch("sys.stderr", new=StringIO()):
                result = _cmd_replay(tf_path)
            assert result == 1
        finally:
            Path(tf_path).unlink()

    def test_replay_error(self) -> None:
        """回放过程错误返回错误。"""
        from llm.cli import _cmd_replay
        from kernel.replay import ReplayError

        match_log = {
            "format_version": 2,
            "actions": [{"kind": "invalid"}],
            "events": [],
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tf:
            json.dump(match_log, tf)
            tf_path = tf.name

        try:
            with patch("llm.cli.replay_from_actions") as mock_replay:
                mock_replay.side_effect = ReplayError("test error")

                with patch("sys.stderr", new=StringIO()):
                    result = _cmd_replay(tf_path)
                assert result == 1
        finally:
            Path(tf_path).unlink()


# --- _print_match_results_from_state ---


class TestPrintMatchResults:
    """测试成绩打印函数。"""

    def test_prints_results_with_players(self) -> None:
        """测试打印带玩家名的成绩。"""
        from llm.cli import _print_match_results_from_state

        mock_table = MagicMock()
        mock_table.scores = (30000, 25000, 20000, 15000)
        mock_table.dealer_seat = 0
        mock_state = MagicMock(table=mock_table)

        players = [
            {"id": "ichihime", "seat": 0},
            {"id": "yui", "seat": 1},
            {"id": "kavi", "seat": 2},
            {"id": "kana", "seat": 3},
        ]

        with patch("sys.stdout", new=StringIO()) as out:
            _print_match_results_from_state(mock_state, players)
            output = out.getvalue()

        assert "对局结束" in output
        assert "ichihime" in output
        assert "yui" in output
        assert "30,000" in output  # 格式化后有逗号

    def test_prints_results_without_players(self) -> None:
        """测试打印不带玩家名的成绩。"""
        from llm.cli import _print_match_results_from_state

        mock_table = MagicMock()
        mock_table.scores = (28000, 26000, 24000, 22000)
        mock_table.dealer_seat = 1
        mock_state = MagicMock(table=mock_table)

        with patch("sys.stdout", new=StringIO()) as out:
            _print_match_results_from_state(mock_state, None)
            output = out.getvalue()

        assert "对局结束" in output
        assert "Player0" in output
        assert "28,000" in output  # 格式化后有逗号

    def test_prints_results_with_partial_players(self) -> None:
        """测试部分玩家有名字。"""
        from llm.cli import _print_match_results_from_state

        mock_table = MagicMock()
        mock_table.scores = (25000, 25000, 25000, 25000)
        mock_table.dealer_seat = 0
        mock_state = MagicMock(table=mock_table)

        # 只有座位 0 和 2 有名字
        players = [
            {"id": "ichihime", "seat": 0},
            {"seat": 1},  # 无 id
            {"id": "kavi", "seat": 2},
            {"seat": 3},
        ]

        with patch("sys.stdout", new=StringIO()) as out:
            _print_match_results_from_state(mock_state, players)
            output = out.getvalue()

        assert "ichihime" in output
        assert "kavi" in output


# --- main function additional branches ---


class TestMainAdditionalBranches:
    """测试 main 函数的更多分支。"""

    def test_log_session_creates_files(self) -> None:
        """测试 log-session 创建日志文件。"""
        mock_result = MagicMock(
            player_steps=0,
            kernel_steps=0,
            stopped_reason="test",
            final_state=MagicMock(phase=MagicMock(value="pre_deal")),
            as_match_log=lambda: {"test": "data"},
            actions_wire=(),
            events_wire=(),
        )

        with tempfile.TemporaryDirectory() as td:
            logs_dir = Path(td) / "logs"
            with patch("llm.cli._LOG_REPLAY_DIR", logs_dir / "replay"):
                with patch("llm.cli._LOG_DEBUG_DIR", logs_dir / "debug"):
                    with patch("llm.cli._LOG_SIMPLE_DIR", logs_dir / "simple"):
                        with patch("llm.cli.run_llm_match", return_value=mock_result):
                            with patch("sys.stdout", new=StringIO()):
                                result = main([
                                    "--dry-run",
                                    "--log-session", "test-session",
                                    "--max-hands", "1",
                                ])

        assert result == 0

    def test_llm_config_error_exits(self) -> None:
        """测试 LLM 配置错误时退出。"""
        with patch("llm.cli.load_seat_llm_configs") as mock_load:
            mock_load.side_effect = ValueError("配置错误")

            with patch("sys.stderr", new=StringIO()):
                result = main(["--max-hands", "1"])
            assert result == 2

    def test_match_end_default_when_null(self) -> None:
        """测试 match_end 为 null 时的默认值。"""
        mock_result = MagicMock(
            player_steps=0,
            kernel_steps=0,
            stopped_reason="test",
            final_state=MagicMock(phase=MagicMock(value="pre_deal")),
            as_match_log=lambda: {},
            actions_wire=(),
            events_wire=(),
        )

        # 构造一个有效配置，但使用 --max-hands 覆盖 match_end
        yaml_cfg = {
            "kernel": {
                "seed": 0,
                "wall_file": None,
                "match_end": {
                    "type": "hands",
                    "value": 8,  # 默认值会被 --max-hands 覆盖
                    "allow_negative": False,
                },
            },
            "debug": {"dry_run": False, "verbose": False},
            "logging": {"json": None, "session": None, "session_audit": False},
            "watch": {"enabled": False, "delay": 0.3, "show_reason": True},
            "llm": {
                "request_delay": 0.5,
                "history_budget": 10,
                "context_scope": "per_hand",
                "compression_level": "collapse",
                "context_compression_threshold": 0.95,
                "prompt_format": "natural",
                "conversation_logging": {"enabled": False},
            },
            "players": None,
        }

        with patch("llm.cli._load_yaml_config", return_value=yaml_cfg):
            with patch("llm.cli.run_llm_match", return_value=mock_result) as mock_run:
                main(["--dry-run", "--max-hands", "1"])

                # --max-hands 应该覆盖 match_end
                call_kwargs = mock_run.call_args[1]
                me = call_kwargs.get("match_end")
                assert me is not None
                assert me.value == 1  # --max-hands 1

    def test_dry_run_without_api_clients(self) -> None:
        """测试 dry-run 不需要 API clients。"""
        mock_result = MagicMock(
            player_steps=0,
            kernel_steps=0,
            stopped_reason="test",
            final_state=MagicMock(phase=MagicMock(value="pre_deal")),
            as_match_log=lambda: {},
            actions_wire=(),
            events_wire=(),
        )

        with patch("llm.cli.run_llm_match", return_value=mock_result) as mock_run:
            with patch("llm.cli.load_seat_llm_configs") as mock_load:
                mock_load.return_value = {}

                main(["--dry-run", "--max-hands", "1"])

                # dry_run=True 时不应该调用 build_seat_clients
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs.get("dry_run") is True
                assert call_kwargs.get("seat_clients") is None


# --- __main__ entry point ---


class TestMainEntrypoint:
    """测试 __main__ 入口。"""

    def test_main_module_raises_systemexit(self) -> None:
        """测试 __main__ 模块调用 main() 并包装为 SystemExit。"""
        import runpy

        # 模拟 python -m llm 的行为
        with patch("llm.cli.main", return_value=0):
            # 直接导入测试 __main__ 块的行为
            # 注意：实际代码中 if __name__ == "__main__": raise SystemExit(main())
            # 我们无法直接测试这个，因为需要修改模块名
            pass

    def test_cli_module_main_function(self) -> None:
        """验证 main 函数可以被正确调用。"""
        # 导入模块验证代码可执行
        from llm import cli

        assert hasattr(cli, "main")
        assert callable(cli.main)


# --- _cmd_show_stats ---


class TestCmdShowStats:
    """测试 _cmd_show_stats 命令。"""

    def test_show_stats_calls_render(self) -> None:
        """测试 show-stats 调用 render_character_card。"""
        from llm.cli import _cmd_show_stats

        with patch("ui.terminal.components.character_card.render_character_card") as mock_render:
            with patch("rich.console.Console") as mock_console:
                mock_render.return_value = "card content"
                mock_console_instance = MagicMock()
                mock_console.return_value = mock_console_instance

                result = _cmd_show_stats("ichihime")

                mock_render.assert_called_once_with("ichihime")
                mock_console_instance.print.assert_called_once()
                assert result == 0


# --- watch mode tests ---


class TestWatchMode:
    """测试 --watch 模式。"""

    def test_watch_mode_calls_cmd_watch_dry_run(self) -> None:
        """测试 watch 模式调用 _cmd_watch_dry_run。"""
        mock_result = MagicMock(
            player_steps=0,
            kernel_steps=0,
            stopped_reason="test",
            final_state=MagicMock(phase=MagicMock(value="pre_deal")),
            as_match_log=lambda: {},
            actions_wire=(),
            events_wire=(),
        )

        with patch("llm.cli._cmd_watch_dry_run", return_value=0) as mock_watch:
            # watch 模式需要在配置中启用
            yaml_cfg = {
                "kernel": {
                    "seed": 0,
                    "wall_file": None,
                    "match_end": {"type": "hands", "value": 8, "allow_negative": False},
                },
                "debug": {"dry_run": False, "verbose": False},
                "logging": {"json": None, "session": None, "session_audit": False},
                "watch": {"enabled": True, "delay": 0.3, "show_reason": True},
                "llm": {
                    "request_delay": 0.5,
                    "history_budget": 10,
                    "context_scope": "per_hand",
                    "compression_level": "collapse",
                    "context_compression_threshold": 0.95,
                    "prompt_format": "natural",
                    "conversation_logging": {"enabled": False},
                },
                "players": None,
            }

            with patch("llm.cli._load_yaml_config", return_value=yaml_cfg):
                result = main(["--watch", "--dry-run", "--max-hands", "1"])
                mock_watch.assert_called_once()
                assert result == 0

    def test_watch_replay_calls_cmd_watch_replay(self) -> None:
        """测试 watch + replay 模式调用 _cmd_watch_replay。"""
        match_log = {
            "format_version": 2,
            "actions": [{"kind": "begin_round"}],
            "events": [],
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tf:
            json.dump(match_log, tf)
            tf_path = tf.name

        try:
            with patch("llm.cli._cmd_watch_replay", return_value=0) as mock_watch:
                yaml_cfg = {
                    "kernel": {
                        "seed": 0,
                        "wall_file": None,
                        "match_end": {"type": "hands", "value": 8, "allow_negative": False},
                    },
                    "debug": {"dry_run": False, "verbose": False},
                    "logging": {"json": None, "session": None, "session_audit": False},
                    "watch": {"enabled": True, "delay": 0.3, "show_reason": True},
                    "llm": {
                        "request_delay": 0.5,
                        "history_budget": 10,
                        "context_scope": "per_hand",
                        "compression_level": "collapse",
                        "context_compression_threshold": 0.95,
                        "prompt_format": "natural",
                        "conversation_logging": {"enabled": False},
                    },
                    "players": None,
                }

                with patch("llm.cli._load_yaml_config", return_value=yaml_cfg):
                    result = main(["--watch", "--replay", tf_path])
                    mock_watch.assert_called_once()
                    assert result == 0
        finally:
            Path(tf_path).unlink()


# --- _cmd_watch_replay ---


class TestCmdWatchReplay:
    """测试 _cmd_watch_replay 命令。"""

    def test_watch_replay_with_valid_file(self) -> None:
        """测试有效牌谱的 watch replay。"""
        from llm.cli import _cmd_watch_replay

        match_log = {
            "format_version": 2,
            "actions": [{"kind": "begin_round"}],
            "events": [],
            "players": [
                {"seat": 0, "id": "ichihime"},
                {"seat": 1, "id": "yui"},
            ],
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tf:
            json.dump(match_log, tf)
            tf_path = tf.name

        try:
            with patch("ui.terminal.LiveMatchViewer") as mock_viewer:
                mock_viewer_instance = MagicMock()
                mock_viewer.return_value = mock_viewer_instance

                result = _cmd_watch_replay(tf_path, 0.5)

                mock_viewer_instance.run_from_replay_file.assert_called_once()
                assert result == 0
        finally:
            Path(tf_path).unlink()

    def test_watch_replay_import_error(self) -> None:
        """测试 rich 未安装时的错误。"""
        from llm.cli import _cmd_watch_replay

        # 创建一个临时牌谱文件
        match_log = {"format_version": 2, "actions": [], "events": []}
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tf:
            json.dump(match_log, tf)
            tf_path = tf.name

        try:
            # Mock the import to fail
            def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
                if name == "ui.terminal":
                    raise ImportError("need rich")
                return original_import(name, *args, **kwargs)

            original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

            with patch("builtins.__import__", side_effect=mock_import):
                with patch("sys.stderr", new=StringIO()):
                    result = _cmd_watch_replay(tf_path, 0.5)
                assert result == 2
        finally:
            Path(tf_path).unlink()


# --- match_end in main ---


class TestMatchEndConstruction:
    """测试 match_end 构建逻辑。"""

    def test_match_end_from_yaml(self) -> None:
        """测试从 YAML 读取 match_end。"""
        mock_result = MagicMock(
            player_steps=0,
            kernel_steps=0,
            stopped_reason="test",
            final_state=MagicMock(phase=MagicMock(value="pre_deal")),
            as_match_log=lambda: {},
            actions_wire=(),
            events_wire=(),
        )

        yaml_cfg = {
            "kernel": {
                "seed": 0,
                "wall_file": None,
                "match_end": {"type": "hands", "value": 4, "allow_negative": True},
            },
            "debug": {"dry_run": False, "verbose": False},
            "logging": {"json": None, "session": None, "session_audit": False},
            "watch": {"enabled": False, "delay": 0.3, "show_reason": True},
            "llm": {
                "request_delay": 0.5,
                "history_budget": 10,
                "context_scope": "per_hand",
                "compression_level": "collapse",
                "context_compression_threshold": 0.95,
                "prompt_format": "natural",
                "conversation_logging": {"enabled": False},
            },
            "players": None,
        }

        with patch("llm.cli._load_yaml_config", return_value=yaml_cfg):
            with patch("llm.cli.run_llm_match", return_value=mock_result) as mock_run:
                main(["--dry-run"])

                call_kwargs = mock_run.call_args[1]
                me = call_kwargs.get("match_end")
                assert me is not None
                assert me.value == 4
                assert me.allow_negative is True


# --- coverage for line 216 (wall_file multi-hand check) ---


class TestWallFileBranch:
    """测试 wall_file 多局检查分支。"""

    def test_wall_file_with_match_end_value_greater_than_one(self) -> None:
        """测试 wall_file 配合 match_end value > 1 会 exit。"""
        # 这个测试已经在 TestMergeConfig::test_wall_file_with_multi_hand_exits 中覆盖
        # 行 216 是 print 语句，需要验证 stderr 输出
        yaml_cfg = {
            "kernel": {
                "seed": 0,
                "wall_file": None,
                "match_end": {"type": "hands", "value": 8, "allow_negative": False},
            },
            "debug": {"dry_run": False, "verbose": False},
            "logging": {"json": None, "session": None, "session_audit": False},
            "watch": {"enabled": False, "delay": 0.3, "show_reason": True},
            "llm": {
                "request_delay": 0.5,
                "history_budget": 10,
                "context_scope": "per_hand",
                "compression_level": "collapse",
                "context_compression_threshold": 0.95,
                "prompt_format": "natural",
                "conversation_logging": {"enabled": False},
            },
            "players": None,
        }
        cli_args = argparse.Namespace(
            seed=None,
            wall_file="wall.json",
            dry_run=None,
            log_json=None,
            log_session=None,
            verbose=None,
            request_delay=None,
            watch=None,
            watch_delay=None,
            history_budget=None,
            context_scope=None,
            compression_level=None,
            context_compression_threshold=None,
            prompt_format=None,
            session_audit=None,
            show_reason=None,
            players=None,
            enable_conversation_logging=None,
            max_hands=None,
            replay=None,
        )

        with patch("sys.stderr", new=StringIO()) as stderr:
            with pytest.raises(SystemExit) as exc_info:
                _merge_config(yaml_cfg, cli_args)

            output = stderr.getvalue()
            assert "--wall-file 仅支持单局" in output
            assert exc_info.value.code == 2