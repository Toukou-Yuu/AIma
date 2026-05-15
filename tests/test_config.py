"""kernel.config 配置测试。"""

from __future__ import annotations

from kernel.config import MahjongConfig, get_default_config
from kernel.config_manager import KernelConfigManager


class TestMahjongConfig:
    def test_tonpuusen(self) -> None:
        cfg = MahjongConfig.tonpuusen()
        assert cfg.match_length == "tonpuusen"
        assert cfg.round_wind_count == 1

    def test_is_hanchan(self) -> None:
        cfg = MahjongConfig.default()
        assert cfg.is_hanchan() is True
        assert cfg.is_tonpuusen() is False

    def test_is_tonpuusen(self) -> None:
        cfg = MahjongConfig.tonpuusen()
        assert cfg.is_tonpuusen() is True
        assert cfg.is_hanchan() is False


class TestGetDefaultConfig:
    """get_default_config 测试。"""

    def test_returns_mahjong_config(self) -> None:
        """返回 MahjongConfig 实例。"""
        cfg = get_default_config()
        assert isinstance(cfg, MahjongConfig)
        assert cfg.is_hanchan() is True

    def test_consistent_on_multiple_calls(self) -> None:
        """多次调用返回一致配置（缓存生效）。"""
        KernelConfigManager.reset_cache()
        cfg1 = get_default_config()
        cfg2 = get_default_config()
        assert cfg1 == cfg2

    def test_values_match_yaml(self) -> None:
        """配置值与 YAML 一致。"""
        cfg = get_default_config()
        assert cfg.starting_points == 25000
        assert cfg.riichi_stick_value == 1000
        assert cfg.honba_value == 300
        assert cfg.allow_open_tanyao is True
        assert cfg.allow_multiple_ron is True