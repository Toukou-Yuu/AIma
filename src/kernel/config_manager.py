"""内核规则配置管理器。

从 YAML 加载 MahjongConfig，支持延迟加载、缓存、保存和验证。
"""

from __future__ import annotations

import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from kernel.config import MahjongConfig


_KERNEL_CONFIG_PATH = Path("configs/aima_kernel.yaml")
_TEMPLATE_PATH = Path("configs/aima_kernel_template.yaml")

_REQUIRED_FIELDS = (
    "match_length",
    "starting_points",
    "round_wind_count",
    "allow_open_tanyao",
    "allow_multiple_ron",
    "red_dora_enabled",
    "ura_dora_enabled",
    "flow_mangan_enabled",
    "kiriage_mangan_enabled",
    "ippatsu_enabled",
    "west_round_enabled",
    "riichi_stick_value",
    "honba_value",
)


class KernelConfigManager:
    """内核规则配置管理器。"""

    _cached_config: MahjongConfig | None = None

    @classmethod
    def load(cls, path: Path | None = None) -> MahjongConfig:
        """从 YAML 加载 MahjongConfig。

        Args:
            path: 配置文件路径，默认 aima_kernel.yaml

        Returns:
            MahjongConfig 实例

        Raises:
            FileNotFoundError: 文件不存在且模板复制失败
            ValueError: kernel 块缺失或字段不完整
        """
        if path is None:
            path = _KERNEL_CONFIG_PATH

        # 文件不存在时从模板复制
        if not path.exists():
            if _TEMPLATE_PATH.exists():
                shutil.copy(_TEMPLATE_PATH, path)
            else:
                raise FileNotFoundError(f"配置文件 {path} 和模板均不存在")

        data = cls._read_yaml(path)

        if "kernel" not in data:
            raise ValueError("配置文件缺少 kernel 配置块")

        kernel_data = data["kernel"]
        missing = cls._validate_fields(kernel_data)
        if missing:
            raise ValueError(f"kernel 配置块缺少必需字段: {', '.join(missing)}")

        return MahjongConfig(
            match_length=kernel_data["match_length"],
            starting_points=kernel_data["starting_points"],
            round_wind_count=kernel_data["round_wind_count"],
            allow_open_tanyao=kernel_data["allow_open_tanyao"],
            allow_multiple_ron=kernel_data["allow_multiple_ron"],
            red_dora_enabled=kernel_data["red_dora_enabled"],
            ura_dora_enabled=kernel_data["ura_dora_enabled"],
            flow_mangan_enabled=kernel_data["flow_mangan_enabled"],
            kiriage_mangan_enabled=kernel_data["kiriage_mangan_enabled"],
            ippatsu_enabled=kernel_data["ippatsu_enabled"],
            west_round_enabled=kernel_data["west_round_enabled"],
            riichi_stick_value=kernel_data["riichi_stick_value"],
            honba_value=kernel_data["honba_value"],
        )

    @classmethod
    def save(cls, config: MahjongConfig, path: Path | None = None) -> None:
        """保存 MahjongConfig 到 YAML。

        保留 YAML 中其他配置段（llm, players 等），只更新 kernel 块。

        Args:
            config: MahjongConfig 实例
            path: 配置文件路径，默认 aima_kernel.yaml
        """
        if path is None:
            path = _KERNEL_CONFIG_PATH

        # 读取现有内容
        if path.exists():
            data = cls._read_yaml(path)
        else:
            data = {}

        # 更新 kernel 块
        data["kernel"] = asdict(config)

        # 写入文件
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    @classmethod
    def get_default(cls) -> MahjongConfig:
        """获取默认配置（延迟加载 + 缓存）。"""
        if cls._cached_config is None:
            cls._cached_config = cls.load()
        return cls._cached_config

    @classmethod
    def reset_cache(cls) -> None:
        """重置缓存（测试用）。"""
        cls._cached_config = None

    @classmethod
    def validate(cls, data: dict[str, Any]) -> list[str]:
        """验证配置数据，返回缺失字段列表。

        Args:
            data: YAML 解析后的字典

        Returns:
            缺失的必需字段列表，空列表表示验证通过
        """
        if "kernel" not in data:
            return ["kernel"]
        return cls._validate_fields(data["kernel"])

    @classmethod
    def _validate_fields(cls, kernel_data: dict[str, Any]) -> list[str]:
        """检查 kernel 块中的必需字段。"""
        return [f for f in _REQUIRED_FIELDS if f not in kernel_data]

    @classmethod
    def _read_yaml(cls, path: Path) -> dict[str, Any]:
        """读取 YAML 文件。"""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}