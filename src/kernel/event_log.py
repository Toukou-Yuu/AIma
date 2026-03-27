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
class WinSettlementLine:
    """单席和了结算摘要（荣和 / 自摸）。"""

    seat: int
    win_kind: str
    """``"ron"`` 或 ``"tsumo"``。"""
    han: int
    fu: int
    hand_pattern: str
    """和了形分类（如 ``一般形``、``七对子``）。"""
    yakus: tuple[str, ...]
    """役名列表（简体，含表/里宝牌番数标注）。"""
    discard_seat: int | None = None
    payment_from_discarder: int | None = None
    """荣和时该和了者从放铳家收取的点（本场已计入）。"""
    tsumo_deltas: tuple[int, int, int, int] | None = None
    """自摸时各家点棒增减（含本场、未计供托前）。"""
    kyoutaku_share: int = 0
    """本局该席分得的供托。"""
    points: int = 0
    """该席本局净得点（荣和=从铳家收入+供托份；自摸=三家支付净额+供托）。"""


@dataclass(frozen=True, slots=True)
class HandOverEvent(GameEvent):
    """局结束。

    Attributes:
        winners: 和了者集合（流局时为空）
        payments: 各家点棒变化（本局相对结算前）
        win_lines: 各和了席的符番役摘要
    """

    winners: tuple[int, ...]
    payments: tuple[int, int, int, int]
    win_lines: tuple[WinSettlementLine, ...] = ()


@dataclass(frozen=True, slots=True)
class MatchEndEvent(GameEvent):
    """比赛结束（半庄/东风战终局）。"""

    ranking: tuple[int, int, int, int]
    """各 seat 顺位（1 起算；同分同顺）。"""
    final_scores: tuple[int, int, int, int]
    """精算后（含终局供托分配）最终点棒。"""


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
