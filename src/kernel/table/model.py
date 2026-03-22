"""牌桌场况：场风、局序、亲席、本场、供托、点棒。行为对照 mahjong_rules/Mahjong_Soul.md §3、§11。

供托 ``kyoutaku`` 为**累计点数**（立直棒常见为每根 1000 点）。
根数与点数换算由上层或常量 ``RIICHI_STICK_POINTS`` 约定。
不涉及摸打、局流推进或点数结算。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# 四麻默认起配（§11）；三麻等变体由上层传入 ``starting_points``。
DEFAULT_STARTING_POINTS = 25_000
# 立直棒单根点数（§7）；供托增减可与根数相乘后写入 ``kyoutaku``。
RIICHI_STICK_POINTS = 1000


class PrevailingWind(Enum):
    """场风圈：半庄为東場 → 南場；西入等业务未在 v1 实现，此处不增加枚举成员。"""

    EAST = "east"
    SOUTH = "south"


class RoundNumber(Enum):
    """局序：一至四（東一局 … 東四局 / 南一局 …）。"""

    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4


class MatchPreset(Enum):
    """对局长度意向：东风战仅东四局；半庄为东南各四局。具体终局逻辑由后续模块处理。"""

    HANCHAN = "hanchan"
    TONPUSEN = "tonpuu"


def seat_wind_rank(dealer_seat: int, seat: int) -> int:
    """
    自风在字牌中的 rank（与 ``Tile`` 字牌一致：1 东、2 南、3 西、4 北）。

    座位 ``0..3`` 顺时针递增；``dealer_seat`` 为亲家时，亲为东，下家南、对家西、上家北。
    """
    if not 0 <= dealer_seat <= 3:
        msg = "dealer_seat must be 0..3"
        raise ValueError(msg)
    if not 0 <= seat <= 3:
        msg = "seat must be 0..3"
        raise ValueError(msg)
    offset = (seat - dealer_seat) % 4
    return offset + 1


@dataclass(frozen=True, slots=True)
class TableSnapshot:
    """
    某一时刻的场况快照（不含手牌与牌山）。

    ``scores`` 下标与座位 ``0..3`` 一致。
    """

    prevailing_wind: PrevailingWind
    round_number: RoundNumber
    dealer_seat: int
    honba: int
    kyoutaku: int
    scores: tuple[int, int, int, int]
    match_preset: MatchPreset = MatchPreset.HANCHAN

    def __post_init__(self) -> None:
        validate_table_snapshot(self)


def validate_table_snapshot(snapshot: TableSnapshot) -> None:
    """校验场况不变量；失败时抛出 ``ValueError``。"""
    if not 0 <= snapshot.dealer_seat <= 3:
        msg = "dealer_seat must be 0..3"
        raise ValueError(msg)
    if snapshot.honba < 0:
        msg = "honba must be non-negative"
        raise ValueError(msg)
    if snapshot.kyoutaku < 0:
        msg = "kyoutaku must be non-negative"
        raise ValueError(msg)
    if len(snapshot.scores) != 4:
        msg = "scores must have length 4"
        raise ValueError(msg)
    for i, s in enumerate(snapshot.scores):
        if s < 0:
            msg = f"scores[{i}] must be non-negative"
            raise ValueError(msg)


def initial_table_snapshot(
    *,
    dealer_seat: int = 0,
    starting_points: int = DEFAULT_STARTING_POINTS,
    prevailing_wind: PrevailingWind = PrevailingWind.EAST,
    round_number: RoundNumber = RoundNumber.ONE,
    honba: int = 0,
    kyoutaku: int = 0,
    match_preset: MatchPreset = MatchPreset.HANCHAN,
) -> TableSnapshot:
    """生成半庄（或东风战预设）开局默认场况：四家同分、本场与供托为零。"""
    if starting_points < 0:
        msg = "starting_points must be non-negative"
        raise ValueError(msg)
    scores = (starting_points, starting_points, starting_points, starting_points)
    return TableSnapshot(
        prevailing_wind=prevailing_wind,
        round_number=round_number,
        dealer_seat=dealer_seat,
        honba=honba,
        kyoutaku=kyoutaku,
        scores=scores,
        match_preset=match_preset,
    )
