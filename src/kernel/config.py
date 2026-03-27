"""麻将规则配置：对局长度、食断、一炮多响、赤牌、满贯规则等。

本模块提供统一的配置数据类，用于自定义麻将规则变体。
默认值遵循雀魂友人桌标准规则（v1.1）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MahjongConfig:
    """
    麻将规则配置。

    默认值遵循雀魂友人桌标准规则（v1.1）：
    - 半庄战（东 + 南各 4 局）
    - 起配点 25000 点
    - 食断あり（副露后断幺可役）
    - 一炮多响あり（多家同时荣和）
    - 三赤（5m/5p/5s 各 1 张赤牌）
    - 流局满贯あり
    - 切上满贯あり（3 番 110 符/4 番 70 符）
    """

    # ========== 对局形式 ==========
    #: 对局长度：半庄 (hanchan) 或东风战 (tonpuusen)
    match_length: str = "hanchan"  # "hanchan" | "tonpuusen"

    #: 起配点（默认 25000）
    starting_points: int = 25_000

    #: 场风圈风（东：1，南：2）- 用于判定是否 All Last
    round_wind_count: int = 2  # 东场 + 南场

    # ========== 鸣牌与役 ==========
    #: 食断あり：副露后断幺九可算役
    allow_open_tanyao: bool = True

    #: 一炮多响あり：多家同时荣和
    allow_multiple_ron: bool = True

    # ========== 宝牌 ==========
    #: 赤牌あり：三赤（5m/5p/5s 各 1 张）
    red_dora_enabled: bool = True

    #: 里宝牌あり：立直和了时翻开里宝指示牌
    ura_dora_enabled: bool = True

    # ========== 满贯规则 ==========
    #: 流し満貫（流局满贯）あり：荒牌流局时听牌且「全舍牌幺九、未被吃碰大明杠鸣走」则按满贯结算
    flow_mangan_enabled: bool = True

    #: 切上满贯あり：3 番 110 符或 4 番 70 符按满贯计算
    kiriage_mangan_enabled: bool = True

    # ========== 其他 ==========
    #: 立直棒点数（默认 1000 点）
    riichi_stick_value: int = 1_000

    #: 本场费（默认 300 点/场）
    honba_value: int = 300

    @classmethod
    def default(cls) -> "MahjongConfig":
        """返回雀魂友人桌标准配置（v1.1）。"""
        return cls()

    @classmethod
    def tonpuusen(cls) -> "MahjongConfig":
        """返回东风战配置。"""
        return cls(match_length="tonpuusen", round_wind_count=1)

    def is_hanchan(self) -> bool:
        """是否为半庄战。"""
        return self.match_length == "hanchan"

    def is_tonpuusen(self) -> bool:
        """是否为东风战。"""
        return self.match_length == "tonpuusen"


# 默认配置实例（雀魂友人桌标准规则）
DEFAULT_CONFIG = MahjongConfig.default()


def get_config_for_preset(preset_name: str) -> MahjongConfig:
    """
    根据预设名称获取配置。

    Args:
        preset_name: 预设名称 ("hanchan", "tonpuusen", "default")

    Returns:
        对应的 MahjongConfig 实例
    """
    if preset_name == "tonpuusen":
        return MahjongConfig.tonpuusen()
    return MahjongConfig.default()
