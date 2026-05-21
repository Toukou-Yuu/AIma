"""麻将规则配置：对局长度、食断、一炮多响、赤牌、满贯规则等。

本模块提供统一的配置数据类，用于自定义麻将规则变体。
默认值遵循雀魂友人桌标准规则（v1.1）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RonPolicy(Enum):
    """多家荣和策略。"""

    MULTI_RON = "multi_ron"
    """一炮多响：所有荣和者同时和牌（雀魂默认）。"""

    ATAMAHANE = "atamahane"
    """头跳：仅最早一家荣和有效（下家 > 对家 > 上家）。"""

    TRIPLE_ABORTIVE_ONLY = "triple_abortive_only"
    """三家和流局：3家荣和时流局，双响允许。"""


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

    #: 多家荣和策略：multi_ron（一炮多响）、atamahane（头跳）、triple_abortive_only（三家和流局）
    ron_policy: RonPolicy = RonPolicy.MULTI_RON

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
    #: 一发あり：立直后下一巡内和了可计一发
    ippatsu_enabled: bool = True

    #: 西入あり：半庄战南场结束后若亲家听牌则进入西场（本项目中暂不实现）
    west_round_enabled: bool = False

    #: 立直棒点数（默认 1000 点）
    riichi_stick_value: int = 1_000

    #: 本场费（默认 300 点/场）
    honba_value: int = 300

    #: 国士无双抢暗杠：允许国士无双十三面听牌抢暗杠的幺九牌
    allow_kokushi_rob_ankan: bool = True

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


def get_default_config() -> MahjongConfig:
    """获取默认内核配置（从 YAML 加载，带缓存）。"""
    from kernel.config_manager import KernelConfigManager
    return KernelConfigManager.get_default()
