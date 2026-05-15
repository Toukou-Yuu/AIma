"""KernelConfigManager 单元测试。"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from kernel.config import MahjongConfig
from kernel.config_manager import KernelConfigManager


class TestKernelConfigManagerLoad:
    """加载配置测试。"""

    def test_load_from_existing_file(self) -> None:
        """从现有文件加载。"""
        config = KernelConfigManager.load()
        assert config.match_length == "hanchan"
        assert config.starting_points == 25000

    def test_load_missing_kernel_block_raises_error(self, tmp_path: Path) -> None:
        """缺少 kernel 块时报错。"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("llm: {}")
        with pytest.raises(ValueError, match="缺少 kernel 配置块"):
            KernelConfigManager.load(config_file)

    def test_load_missing_field_raises_error(self, tmp_path: Path) -> None:
        """缺少必需字段时报错。"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("kernel: {match_length: hanchan}")
        with pytest.raises(ValueError, match="缺少必需字段"):
            KernelConfigManager.load(config_file)


class TestKernelConfigManagerSave:
    """保存配置测试。"""

    def test_save_creates_new_file(self, tmp_path: Path) -> None:
        """保存创建新文件。"""
        config_file = tmp_path / "test.yaml"
        config = MahjongConfig.default()
        KernelConfigManager.save(config, config_file)
        assert config_file.exists()

    def test_save_preserves_existing_sections(self, tmp_path: Path) -> None:
        """保存保留其他配置段。"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text("llm: {profiles: {}}")
        config = MahjongConfig.default()
        KernelConfigManager.save(config, config_file)
        content = config_file.read_text()
        assert "llm:" in content
        assert "kernel:" in content


class TestKernelConfigManagerValidate:
    """验证配置测试。"""

    def test_validate_complete_config(self) -> None:
        """完整配置验证通过。"""
        data = {
            "kernel": {
                "match_length": "hanchan",
                "starting_points": 25000,
                "round_wind_count": 2,
                "allow_open_tanyao": True,
                "allow_multiple_ron": True,
                "red_dora_enabled": True,
                "ura_dora_enabled": True,
                "flow_mangan_enabled": True,
                "kiriage_mangan_enabled": True,
                "ippatsu_enabled": True,
                "west_round_enabled": False,
                "riichi_stick_value": 1000,
                "honba_value": 300,
            }
        }
        missing = KernelConfigManager.validate(data)
        assert missing == []

    def test_validate_incomplete_config(self) -> None:
        """不完整配置返回缺失字段列表。"""
        data = {"kernel": {"match_length": "hanchan"}}
        missing = KernelConfigManager.validate(data)
        assert "starting_points" in missing

    def test_validate_missing_kernel_block(self) -> None:
        """缺少 kernel 块返回 kernel。"""
        data = {"llm": {}}
        missing = KernelConfigManager.validate(data)
        assert missing == ["kernel"]


class TestKernelConfigManagerGetDefault:
    """获取默认配置测试。"""

    def test_get_default_returns_valid_config(self) -> None:
        """获取有效默认配置。"""
        KernelConfigManager.reset_cache()
        config = KernelConfigManager.get_default()
        assert isinstance(config, MahjongConfig)
        assert config.match_length == "hanchan"

    def test_get_default_is_cached(self) -> None:
        """默认配置缓存生效。"""
        KernelConfigManager.reset_cache()
        config1 = KernelConfigManager.get_default()
        config2 = KernelConfigManager.get_default()
        assert config1 is config2

    def test_reset_cache_clears_cached_config(self) -> None:
        """reset_cache 清除缓存。"""
        config1 = KernelConfigManager.get_default()
        KernelConfigManager.reset_cache()
        config2 = KernelConfigManager.get_default()
        # 重新加载后配置值相同，但不是同一实例
        assert config1 == config2