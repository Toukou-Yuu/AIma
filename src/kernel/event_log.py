"""事件日志与回放：结构化事件记录、确定性回放。

K13 核心模块：记录对局中所有关键事件，支持确定性回放。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel.deal.model import Meld
    from kernel.flow.model import FlowKind
    from kernel.tiles.model import Tile


@dataclass(frozen=True, slots=True)
class GameEvent:
    """事件基类。

    Attributes:
        seat: 执行者座位（系统事件可为 None）
        sequence: 事件序列号（从 0 开始）
    """

    seat: int | None
    sequence: int


@dataclass(frozen=True, slots=True)
class RoundBeginEvent(GameEvent):
    """局开始：配牌完成。

    Attributes:
        dealer_seat: 亲家座位
        dora_indicator: 表宝指示牌
        seeds: 各家初始手牌种子索引（用于回放验证）
    """

    dealer_seat: int
    dora_indicator: "Tile"
    seeds: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class DrawTileEvent(GameEvent):
    """摸牌。

    Attributes:
        tile: 摸到的牌
        is_rinshan: 是否岭上摸牌
        wall_remaining: 剩余牌数
    """

    tile: "Tile"
    is_rinshan: bool
    wall_remaining: int


@dataclass(frozen=True, slots=True)
class DiscardTileEvent(GameEvent):
    """打牌。

    Attributes:
        tile: 打出的牌
        is_tsumogiri: 是否摸切
        declare_riichi: 是否立直宣言
    """

    tile: "Tile"
    is_tsumogiri: bool
    declare_riichi: bool


@dataclass(frozen=True, slots=True)
class CallEvent(GameEvent):
    """鸣牌（吃/碰/杠）。

    Attributes:
        meld: 副露
        call_kind: 鸣牌类型 ("chi", "pon", "daiminkan", "ankan", "shankuminkan")
    """

    meld: "Meld"
    call_kind: str


@dataclass(frozen=True, slots=True)
class RonEvent(GameEvent):
    """荣和。

    Attributes:
        win_tile: 和了牌
        discard_seat: 放铳者座位
    """

    win_tile: "Tile"
    discard_seat: int


@dataclass(frozen=True, slots=True)
class TsumoEvent(GameEvent):
    """自摸。

    Attributes:
        win_tile: 和了牌
        is_rinshan: 是否岭上自摸
    """

    win_tile: "Tile"
    is_rinshan: bool


@dataclass(frozen=True, slots=True)
class FlowEvent(GameEvent):
    """流局。

    Attributes:
        flow_kind: 流局类型
        tenpai_seats: 听牌者集合
    """

    flow_kind: "FlowKind"
    tenpai_seats: frozenset[int]


@dataclass(frozen=True, slots=True)
class HandOverEvent(GameEvent):
    """局结束。

    Attributes:
        winners: 和了者集合（流局时为空）
        payments: 各家点棒变化（相对局开始前）
    """

    winners: tuple[int, ...]
    payments: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class EventLog:
    """事件日志容器。

    Attributes:
        events: 事件列表（按时间序）
        seed: 随机种子（用于回放验证）
        match_id: 对局 ID（可选）
    """

    events: tuple[GameEvent, ...]
    seed: int | None = None
    match_id: str | None = None

    def append(self, event: GameEvent) -> EventLog:
        """追加事件（返回新实例）。"""
        return EventLog(
            events=self.events + (event,),
            seed=self.seed,
            match_id=self.match_id,
        )
