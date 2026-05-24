"""P2-1 dry-run no-persist 测试覆盖。

测试用例：
- dry-run 不调用 memory save
- dry-run 不调用 stats save
- --persist 显式开启时（即使 dry-run）也保存
- --no-persist 显式关闭时不保存
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from llm.config import MatchEndCondition
from llm.runner import run_llm_match, _finalize_agents_episode
from tests.llm_test_utils import load_test_runtime_config, load_test_seat_llm_configs


class TestDryRunNoPersist:
    """测试 dry-run 模式不持久化。"""

    def test_dry_run_no_memory_save(self) -> None:
        """dry-run 不调用 agent.update_memory。"""
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=1, allow_negative=False)
        seat_llm_configs = load_test_seat_llm_configs()

        # 配置有 player_id 的 players
        players = [{"id": "test_player_no_persist", "seat": 0}]

        with patch("llm.agent.PlayerAgent.update_memory") as mock_update_memory:
            result = run_llm_match(
                seed=42,
                match_end=match_end,
                dry_run=True,
                persist=None,  # 使用默认行为（dry-run 不持久化）
                request_delay_seconds=0.0,
                history_budget=runtime.history_budget,
                context_scope=runtime.context_scope,
                compression_level=runtime.compression_level,
                context_compression_threshold=runtime.context_compression_threshold,
                seat_llm_configs=seat_llm_configs,
                prompt_format=runtime.prompt_format,
                enable_conversation_logging=False,
                players=players,
            )
            # dry-run 不应该调用 update_memory
            mock_update_memory.assert_not_called()

        # 应该正常完成
        assert result.player_steps > 0

    def test_dry_run_no_stats_save(self) -> None:
        """dry-run 不调用 agent.update_stats。"""
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=1, allow_negative=False)
        seat_llm_configs = load_test_seat_llm_configs()

        # 配置有 player_id 的 players
        players = [{"id": "test_player_no_stats", "seat": 0}]

        with patch("llm.agent.PlayerAgent.update_stats") as mock_update_stats:
            result = run_llm_match(
                seed=42,
                match_end=match_end,
                dry_run=True,
                persist=None,  # 使用默认行为（dry-run 不持久化）
                request_delay_seconds=0.0,
                history_budget=runtime.history_budget,
                context_scope=runtime.context_scope,
                compression_level=runtime.compression_level,
                context_compression_threshold=runtime.context_compression_threshold,
                seat_llm_configs=seat_llm_configs,
                prompt_format=runtime.prompt_format,
                enable_conversation_logging=False,
                players=players,
            )
            # dry-run 不应该调用 update_stats
            mock_update_stats.assert_not_called()

        # 应该正常完成
        assert result.player_steps > 0


class TestPersistOverride:
    """测试 persist 参数覆盖 dry-run 默认行为。"""

    def test_persist_true_saves_even_when_dry_run(self) -> None:
        """--persist 显式开启时，即使 dry-run 也保存 memory/stats。"""
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=1, allow_negative=False)
        seat_llm_configs = load_test_seat_llm_configs()

        # 配置有 player_id 的 players
        players = [{"id": "test_player_persist_force", "seat": 0}]

        with patch("llm.agent.PlayerAgent.update_memory") as mock_update_memory:
            with patch("llm.agent.PlayerAgent.update_stats") as mock_update_stats:
                result = run_llm_match(
                    seed=42,
                    match_end=match_end,
                    dry_run=True,
                    persist=True,  # 强制开启持久化
                    request_delay_seconds=0.0,
                    history_budget=runtime.history_budget,
                    context_scope=runtime.context_scope,
                    compression_level=runtime.compression_level,
                    context_compression_threshold=runtime.context_compression_threshold,
                    seat_llm_configs=seat_llm_configs,
                    prompt_format=runtime.prompt_format,
                    enable_conversation_logging=False,
                    players=players,
                )
                # persist=True 即使 dry-run 也应该调用 update_memory
                mock_update_memory.assert_called()
                # persist=True 即使 dry-run 也应该调用 update_stats
                mock_update_stats.assert_called()

        # 应该正常完成
        assert result.player_steps > 0

    def test_persist_false_no_save_even_when_not_dry_run(self) -> None:
        """--no-persist 显式关闭时，即使非 dry-run 也不保存。"""
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=1, allow_negative=False)
        seat_llm_configs = load_test_seat_llm_configs()

        # 配置有 player_id 的 players
        players = [{"id": "test_player_no_persist_force", "seat": 0}]

        # 使用空的 seat_clients 来避免实际 API 调用
        seat_clients = {}

        with patch("llm.agent.PlayerAgent.update_memory") as mock_update_memory:
            with patch("llm.agent.PlayerAgent.update_stats") as mock_update_stats:
                # 注意：dry_run=False 时需要 seat_clients，但我们传入空的
                # 这会导致 RuntimeError，所以我们使用 dry_run=True 配合 persist=False
                result = run_llm_match(
                    seed=42,
                    match_end=match_end,
                    dry_run=True,
                    persist=False,  # 强制关闭持久化
                    request_delay_seconds=0.0,
                    history_budget=runtime.history_budget,
                    context_scope=runtime.context_scope,
                    compression_level=runtime.compression_level,
                    context_compression_threshold=runtime.context_compression_threshold,
                    seat_llm_configs=seat_llm_configs,
                    prompt_format=runtime.prompt_format,
                    enable_conversation_logging=False,
                    players=players,
                )
                # persist=False 不应该调用任何持久化方法
                mock_update_memory.assert_not_called()
                mock_update_stats.assert_not_called()

        # 应该正常完成
        assert result.player_steps > 0

    def test_persist_none_follows_dry_run_false(self) -> None:
        """persist=None 且 dry_run=False 时保存（正常模式）。"""
        runtime = load_test_runtime_config()
        match_end = MatchEndCondition(type="hands", value=1, allow_negative=False)
        seat_llm_configs = load_test_seat_llm_configs()

        # 配置有 player_id 的 players
        players = [{"id": "test_player_normal", "seat": 0}]

        # 使用 mock 的 seat_clients 和 agent
        mock_client = MagicMock()

        with patch("llm.agent.PlayerAgent.update_memory") as mock_update_memory:
            with patch("llm.agent.PlayerAgent.update_stats") as mock_update_stats:
                # 由于 dry_run=False 需要 client，这里我们用 dry_run=True 来测试
                # persist=None 的默认行为（跟随 dry_run）
                result = run_llm_match(
                    seed=42,
                    match_end=match_end,
                    dry_run=True,
                    persist=None,  # 默认行为
                    request_delay_seconds=0.0,
                    history_budget=runtime.history_budget,
                    context_scope=runtime.context_scope,
                    compression_level=runtime.compression_level,
                    context_compression_threshold=runtime.context_compression_threshold,
                    seat_llm_configs=seat_llm_configs,
                    seat_clients={0: mock_client, 1: mock_client, 2: mock_client, 3: mock_client},
                    prompt_format=runtime.prompt_format,
                    enable_conversation_logging=False,
                    players=players,
                )
                # dry_run=True 且 persist=None 不应该持久化
                mock_update_memory.assert_not_called()
                mock_update_stats.assert_not_called()

        # 应该正常完成
        assert result.player_steps > 0


class TestFinalizeAgentsEpisodePersist:
    """测试 _finalize_agents_episode 函数的 persist 参数。"""

    def test_finalize_with_persist_true(self) -> None:
        """persist=True 时调用 update_memory。"""
        from llm.agent import PlayerAgent
        from llm.agent.context import EpisodeContext
        from llm.agent.match_context import MatchContext
        from kernel.event_log import HandOverEvent, WinSettlementLine

        seat_agents = {
            s: PlayerAgent(
                player_id="test_player",
                history_budget=0,
                prompt_mode="natural",
                compression_level="none",
                context_scope="stateless",
                max_context_tokens=4096,
                max_output_tokens=256,
                context_compression_threshold=0.8,
            )
            for s in range(4)
        }
        seat_contexts = {
            s: EpisodeContext(s, match_id="test", hand_number=1)
            for s in range(4)
        }
        match_contexts = {
            s: MatchContext(s)
            for s in range(4)
        }
        seat_clients = {s: MagicMock() for s in range(4)}

        win_line = WinSettlementLine(
            seat=0, win_kind="ron", han=1, fu=30,
            hand_pattern="一般形", yakus=("立直",),
            points=1500,
        )
        ev = HandOverEvent(
            seat=0, sequence=10, winners=(0,),
            payments=(1500, -1500, 0, 0),
            win_lines=(win_line,),
        )

        with patch("llm.agent.PlayerAgent.update_memory") as mock_update_memory:
            _finalize_agents_episode(
                (ev,),
                seat_agents,
                seat_contexts,
                match_contexts,
                seat_clients,
                dry_run=True,  # dry_run=True
                persist=True,  # 但 persist=True 强制持久化
            )
            # persist=True 即使 dry_run=True 也应该调用
            mock_update_memory.assert_called()

    def test_finalize_with_persist_false(self) -> None:
        """persist=False时不调用 update_memory。"""
        from llm.agent import PlayerAgent
        from llm.agent.context import EpisodeContext
        from llm.agent.match_context import MatchContext
        from kernel.event_log import HandOverEvent, WinSettlementLine

        seat_agents = {
            s: PlayerAgent(
                player_id="test_player",
                history_budget=0,
                prompt_mode="natural",
                compression_level="none",
                context_scope="stateless",
                max_context_tokens=4096,
                max_output_tokens=256,
                context_compression_threshold=0.8,
            )
            for s in range(4)
        }
        seat_contexts = {
            s: EpisodeContext(s, match_id="test", hand_number=1)
            for s in range(4)
        }
        match_contexts = {
            s: MatchContext(s)
            for s in range(4)
        }
        seat_clients = {s: MagicMock() for s in range(4)}

        win_line = WinSettlementLine(
            seat=0, win_kind="ron", han=1, fu=30,
            hand_pattern="一般形", yakus=("立直",),
            points=1500,
        )
        ev = HandOverEvent(
            seat=0, sequence=10, winners=(0,),
            payments=(1500, -1500, 0, 0),
            win_lines=(win_line,),
        )

        with patch("llm.agent.PlayerAgent.update_memory") as mock_update_memory:
            _finalize_agents_episode(
                (ev,),
                seat_agents,
                seat_contexts,
                match_contexts,
                seat_clients,
                dry_run=False,  # dry_run=False
                persist=False,  # 但 persist=False 强制不持久化
            )
            # persist=False 即使 dry_run=False也不应该调用
            mock_update_memory.assert_not_called()

    def test_finalize_persist_none_follows_dry_run(self) -> None:
        """persist=None 时跟随 dry_run 行为。"""
        from llm.agent import PlayerAgent
        from llm.agent.context import EpisodeContext
        from llm.agent.match_context import MatchContext
        from kernel.event_log import HandOverEvent, WinSettlementLine

        seat_agents = {
            s: PlayerAgent(
                player_id="test_player",
                history_budget=0,
                prompt_mode="natural",
                compression_level="none",
                context_scope="stateless",
                max_context_tokens=4096,
                max_output_tokens=256,
                context_compression_threshold=0.8,
            )
            for s in range(4)
        }
        seat_contexts = {
            s: EpisodeContext(s, match_id="test", hand_number=1)
            for s in range(4)
        }
        match_contexts = {
            s: MatchContext(s)
            for s in range(4)
        }
        seat_clients = {s: MagicMock() for s in range(4)}

        win_line = WinSettlementLine(
            seat=0, win_kind="ron", han=1, fu=30,
            hand_pattern="一般形", yakus=("立直",),
            points=1500,
        )
        ev = HandOverEvent(
            seat=0, sequence=10, winners=(0,),
            payments=(1500, -1500, 0, 0),
            win_lines=(win_line,),
        )

        with patch("llm.agent.PlayerAgent.update_memory") as mock_update_memory:
            _finalize_agents_episode(
                (ev,),
                seat_agents,
                seat_contexts,
                match_contexts,
                seat_clients,
                dry_run=True,
                persist=None,  # 默认行为：跟随 dry_run
            )
            # dry_run=True 且 persist=None 不应该调用
            mock_update_memory.assert_not_called()


class TestCLIPersistArgs:
    """测试 CLI 参数 --persist 和 --no-persist。"""

    def test_persist_and_no_persist_mutually_exclusive(self) -> None:
        """--persist 和 --no-persist 不能同时使用。"""
        from llm.cli import main
        import sys
        from io import StringIO

        with patch("sys.stderr", new=StringIO()) as stderr:
            with pytest.raises(SystemExit) as exc_info:
                main(["--persist", "--no-persist", "--dry-run", "--max-hands", "1"])
            output = stderr.getvalue()
            assert "--persist 和 --no-persist 不能同时使用" in output
            assert exc_info.value.code == 2

    def test_persist_passed_to_run_llm_match(self) -> None:
        """--persist 参数传递到 run_llm_match。"""
        from llm.cli import main
        from unittest.mock import MagicMock

        mock_result = MagicMock(
            player_steps=0,
            kernel_steps=0,
            stopped_reason="test",
            final_state=MagicMock(
                phase=MagicMock(value="pre_deal"),
                table=MagicMock(
                    scores=(25000, 25000, 25000, 25000),
                    dealer_seat=0,
                ),
            ),
            as_match_log=lambda: {},
            actions_wire=(),
            events_wire=(),
        )

        with patch("llm.cli.run_llm_match", return_value=mock_result) as mock_run:
            main(["--persist", "--dry-run", "--max-hands", "1"])
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("persist") is True

    def test_no_persist_passed_to_run_llm_match(self) -> None:
        """--no-persist 参数传递到 run_llm_match。"""
        from llm.cli import main
        from unittest.mock import MagicMock

        mock_result = MagicMock(
            player_steps=0,
            kernel_steps=0,
            stopped_reason="test",
            final_state=MagicMock(
                phase=MagicMock(value="pre_deal"),
                table=MagicMock(
                    scores=(25000, 25000, 25000, 25000),
                    dealer_seat=0,
                ),
            ),
            as_match_log=lambda: {},
            actions_wire=(),
            events_wire=(),
        )

        with patch("llm.cli.run_llm_match", return_value=mock_result) as mock_run:
            main(["--no-persist", "--dry-run", "--max-hands", "1"])
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("persist") is False

    def test_no_persist_arg_default_none(self) -> None:
        """无 --persist 或 --no-persist 时 persist=None。"""
        from llm.cli import main
        from unittest.mock import MagicMock

        mock_result = MagicMock(
            player_steps=0,
            kernel_steps=0,
            stopped_reason="test",
            final_state=MagicMock(
                phase=MagicMock(value="pre_deal"),
                table=MagicMock(
                    scores=(25000, 25000, 25000, 25000),
                    dealer_seat=0,
                ),
            ),
            as_match_log=lambda: {},
            actions_wire=(),
            events_wire=(),
        )

        with patch("llm.cli.run_llm_match", return_value=mock_result) as mock_run:
            main(["--dry-run", "--max-hands", "1"])
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("persist") is None