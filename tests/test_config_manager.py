"""KernelConfigManager 单元测试。"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from kernel.config import MahjongConfig, RonPolicy
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
                "ron_policy": "multi_ron",
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


class TestKernelConfigManagerEmptyFile:
    """空文件加载测试。"""

    def test_load_empty_file_raises_error(self, tmp_path: Path) -> None:
        """空 YAML 文件加载时应报错缺少 kernel 块。"""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        with pytest.raises(ValueError, match="缺少 kernel 配置块"):
            KernelConfigManager.load(config_file)

    def test_load_empty_dict_raises_error(self, tmp_path: Path) -> None:
        """空字典 YAML 加载时应报错缺少 kernel 块。"""
        config_file = tmp_path / "empty_dict.yaml"
        config_file.write_text("{}")
        with pytest.raises(ValueError, match="缺少 kernel 配置块"):
            KernelConfigManager.load(config_file)

    def test_read_yaml_returns_empty_dict_for_empty_file(self, tmp_path: Path) -> None:
        """_read_yaml 对空文件返回空字典。"""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        result = KernelConfigManager._read_yaml(config_file)
        assert result == {}

    def test_read_yaml_returns_empty_dict_for_null_content(self, tmp_path: Path) -> None:
        """_read_yaml 对只有 null 的文件返回空字典。"""
        config_file = tmp_path / "null.yaml"
        config_file.write_text("null")
        result = KernelConfigManager._read_yaml(config_file)
        assert result == {}


class TestKernelConfigManagerYamlError:
    """YAML 格式错误测试。"""

    def test_load_invalid_yaml_raises_error(self, tmp_path: Path) -> None:
        """YAML 格式错误时应抛出 yaml.YAMLError。"""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text(":invalid: yaml: [unbalanced")
        with pytest.raises(yaml.YAMLError):
            KernelConfigManager.load(config_file)

    def test_load_malformed_yaml_raises_error(self, tmp_path: Path) -> None:
        """格式错误的 YAML 应抛出 yaml.YAMLError。"""
        config_file = tmp_path / "malformed.yaml"
        config_file.write_text("kernel: {unclosed_bracket")
        with pytest.raises(yaml.YAMLError):
            KernelConfigManager.load(config_file)

    def test_read_yaml_invalid_syntax_raises_error(self, tmp_path: Path) -> None:
        """_read_yaml 对无效 YAML 语法抛出 yaml.YAMLError。"""
        config_file = tmp_path / "bad_syntax.yaml"
        config_file.write_text("  bad:\n    - indentation\n  wrong")
        with pytest.raises(yaml.YAMLError):
            KernelConfigManager._read_yaml(config_file)


class TestKernelConfigManagerTypeMismatch:
    """字段类型不匹配测试。

    注意：当前 MahjongConfig 是 frozen dataclass，不进行运行时类型验证。
    类型不匹配的值会被静默接受。以下是记录当前行为的测试。
    """

    def test_load_string_starting_points_accepted(self, tmp_path: Path) -> None:
        """starting_points 为字符串时当前行为是静默接受（无运行时类型验证）。"""
        config_file = tmp_path / "type_mismatch.yaml"
        config_file.write_text("""
kernel:
  match_length: hanchan
  starting_points: "not_a_number"
  round_wind_count: 2
  allow_open_tanyao: true
  allow_multiple_ron: true
  red_dora_enabled: true
  ura_dora_enabled: true
  flow_mangan_enabled: true
  kiriage_mangan_enabled: true
  ippatsu_enabled: true
  west_round_enabled: false
  riichi_stick_value: 1000
  honba_value: 300
""")
        # 当前行为：dataclass 不验证类型，字符串被赋值给 int 字段
        config = KernelConfigManager.load(config_file)
        assert config.starting_points == "not_a_number"

    def test_load_string_boolean_field_accepted(self, tmp_path: Path) -> None:
        """布尔字段为字符串时当前行为是静默接受（无运行时类型验证）。"""
        config_file = tmp_path / "bool_mismatch.yaml"
        config_file.write_text("""
kernel:
  match_length: hanchan
  starting_points: 25000
  round_wind_count: 2
  allow_open_tanyao: "yes"
  allow_multiple_ron: true
  red_dora_enabled: true
  ura_dora_enabled: true
  flow_mangan_enabled: true
  kiriage_mangan_enabled: true
  ippatsu_enabled: true
  west_round_enabled: false
  riichi_stick_value: 1000
  honba_value: 300
""")
        # 当前行为：dataclass 不验证类型，字符串被赋值给 bool 字段
        config = KernelConfigManager.load(config_file)
        assert config.allow_open_tanyao == "yes"

    def test_load_list_instead_of_value_accepted(self, tmp_path: Path) -> None:
        """字段为列表而非标量时当前行为是静默接受（无运行时类型验证）。"""
        config_file = tmp_path / "list_mismatch.yaml"
        config_file.write_text("""
kernel:
  match_length: hanchan
  starting_points: [25000, 30000]
  round_wind_count: 2
  allow_open_tanyao: true
  allow_multiple_ron: true
  red_dora_enabled: true
  ura_dora_enabled: true
  flow_mangan_enabled: true
  kiriage_mangan_enabled: true
  ippatsu_enabled: true
  west_round_enabled: false
  riichi_stick_value: 1000
  honba_value: 300
""")
        # 当前行为：dataclass 不验证类型，列表被赋值给 int 字段
        config = KernelConfigManager.load(config_file)
        assert config.starting_points == [25000, 30000]

    def test_load_float_instead_of_int_succeeds(self, tmp_path: Path) -> None:
        """整数字段为浮点数时应能转换（YAML 会自动处理）。"""
        config_file = tmp_path / "float_value.yaml"
        config_file.write_text("""
kernel:
  match_length: hanchan
  starting_points: 25000.0
  round_wind_count: 2
  allow_open_tanyao: true
  allow_multiple_ron: true
  red_dora_enabled: true
  ura_dora_enabled: true
  flow_mangan_enabled: true
  kiriage_mangan_enabled: true
  ippatsu_enabled: true
  west_round_enabled: false
  riichi_stick_value: 1000
  honba_value: 300
""")
        # 浮点数转整数是可接受的
        config = KernelConfigManager.load(config_file)
        assert config.starting_points == 25000