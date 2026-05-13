"""kernel.config 配置测试。"""

from __future__ import annotations

from kernel.config import MahjongConfig, get_config_for_preset


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


class TestGetConfigForPreset:
    def test_tonpuusen(self) -> None:
        cfg = get_config_for_preset("tonpuusen")
        assert cfg.is_tonpuusen() is True

    def test_default(self) -> None:
        cfg = get_config_for_preset("default")
        assert cfg.is_hanchan() is True

    def test_unknown(self) -> None:
        cfg = get_config_for_preset("unknown")
        assert cfg.is_hanchan() is True
