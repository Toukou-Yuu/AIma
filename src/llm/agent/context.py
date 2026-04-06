"""EpisodeContext - 本局运行时上下文（Agent 无状态化的关键）."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from llm.agent.memory import EpisodeStats
from llm.agent.stats import MatchStats

if TYPE_CHECKING:
    from collections import Counter

    from kernel.api.observation import Observation
    from kernel.tiles.model import Tile
    from llm.agent import Decision


@dataclass
class EpisodeContext:
    """本局运行时上下文.

    用于将 Agent 从"状态容器"改为"纯函数".
    运行时状态（本局统计、本场统计、决策历史）存储在此，
    Agent 只保留长期状态（profile/memory/stats）.
    """

    seat: int
    episode_stats: EpisodeStats = field(default_factory=lambda: EpisodeStats("", 0))
    match_stats: MatchStats = field(default_factory=MatchStats)
    decision_history: list[Decision] = field(default_factory=list)

    # Phase 2: 状态差异法 - 保存上一帧信息
    last_observation: Observation | None = field(default=None, repr=False)
    last_hand: Counter[Tile] | None = field(default=None, repr=False)
    frame_count: int = field(default=0)
    new_riichi_triggered: bool = field(default=False)  # 有人立直后发送关键帧

    def __post_init__(self):
        """初始化后确保 episode_stats 的 seat 正确."""
        if self.episode_stats.seat != self.seat:
            self.episode_stats.seat = self.seat

    def should_send_keyframe(self) -> bool:
        """判断是否应发送关键帧（完整状态）.

        关键帧触发条件：
        1. 局开始时（frame_count == 0）
        2. 每10回合定期同步
        3. 有人立直后（new_riichi_triggered）

        Returns:
            True: 应发送关键帧（完整状态）
            False: 可发送变化帧（增量更新）
        """
        # 局开始时必须关键帧
        if self.frame_count == 0:
            return True

        # 有人立直后发送关键帧
        if self.new_riichi_triggered:
            self.new_riichi_triggered = False  # 重置标记
            return True

        # 每10回合定期同步
        if self.frame_count % 10 == 0:
            return True

        return False

    def record_riichi_trigger(self) -> None:
        """记录有人立直，触发下一帧为关键帧."""
        self.new_riichi_triggered = True

    def update_frame(self, observation: Observation) -> None:
        """更新帧信息.

        Args:
            observation: 当前观测
        """
        self.last_observation = observation
        self.last_hand = observation.hand.copy() if observation.hand else None
        self.frame_count += 1
        """初始化后确保 episode_stats 的 seat 正确."""
        if self.episode_stats.seat != self.seat:
            self.episode_stats.seat = self.seat

    def record_win(self, win_tile: str) -> None:
        """记录和了."""
        self.episode_stats.wins += 1
        self.episode_stats.win_tiles.append(win_tile)
        if self.episode_stats.riichi_count > 0:
            self.episode_stats.riichi_win += 1

        self.match_stats.wins += 1
        if self.match_stats.riichi_count > 0:
            self.match_stats.riichi_wins += 1

    def record_deal_in(self, deal_in_tile: str) -> None:
        """记录放铳."""
        self.episode_stats.deal_ins += 1
        self.episode_stats.deal_in_tiles.append(deal_in_tile)
        if self.episode_stats.riichi_count > 0:
            self.episode_stats.riichi_deal_in += 1

        self.match_stats.deal_ins += 1
        if self.match_stats.riichi_count > 0:
            self.match_stats.riichi_deal_ins += 1

    def record_riichi(self) -> None:
        """记录立直宣言."""
        self.episode_stats.riichi_count += 1
        self.match_stats.riichi_count += 1

    def record_decision(self, decision: Decision) -> None:
        """记录决策到历史."""
        self.decision_history.append(decision)

    def format_history_summary(self) -> str:
        """生成关键事件摘要（替代逐条记录）.

        只保留关键事件：立直、和牌、放铳、副露（吃碰杠）
        丢弃普通打牌、摸牌、过牌等冗余信息

        Returns:
            纯文本格式的关键事件摘要，每行一条记录
        """
        if not self.decision_history:
            return ""

        lines = []
        for i, d in enumerate(self.decision_history, 1):
            action_desc = self._describe_action_summary(d.action)
            if action_desc:  # 只记录关键事件
                lines.append(f"第{i}巡: {action_desc}")

        return "\n".join(lines)

    def _describe_action_summary(self, action) -> str | None:
        """将 action 描述为摘要文本，只返回关键事件."""
        from kernel.engine.actions import ActionKind

        kind = action.kind

        # 关键事件1: 和牌
        if kind == ActionKind.RON:
            return "荣和"

        if kind == ActionKind.TSUMO:
            return "自摸"

        # 关键事件2: 立直（通过 discard + declare_riichi 判断）
        if kind == ActionKind.DISCARD and action.declare_riichi:
            tile_code = action.tile.to_code() if action.tile else "?"
            return f"打{tile_code}立直宣言"

        # 关键事件3: 副露（吃碰杠）
        if kind == ActionKind.OPEN_MELD and action.meld:
            m = action.meld
            tiles = "/".join(t.to_code() for t in m.tiles) if m.tiles else "?"
            called = m.called_tile.to_code() if m.called_tile else "?"
            kind_map = {"chii": "吃", "pon": "碰", "daiminkan": "杠"}
            cn = kind_map.get(m.kind.value, m.kind.value)
            return f"{cn}{tiles}"

        if kind == ActionKind.ANKAN and action.meld:
            m = action.meld
            tiles = "/".join(t.to_code() for t in m.tiles) if m.tiles else "?"
            return f"暗杠{tiles}"

        if kind == ActionKind.SHANKUMINKAN and action.meld:
            m = action.meld
            tiles = "/".join(t.to_code() for t in m.tiles) if m.tiles else "?"
            return f"加杠{tiles}"

        # 非关键事件：返回 None（不记录）
        return None

    def format_history_for_prompt(self) -> str:
        """将决策历史格式化为纯文本（完整版，用于对比调试）.

        Returns:
            纯文本格式的决策历史，每行一条记录
        """
        if not self.decision_history:
            return ""

        lines = []
        for i, d in enumerate(self.decision_history, 1):
            action_desc = self._describe_action(d.action)
            reason = d.why if d.why else "未说明"
            lines.append(f"第{i}巡: {action_desc} (理由: {reason})")

        return "\n".join(lines)

    def _describe_action(self, action) -> str:
        """将 action 描述为可读文本."""
        from kernel.engine.actions import ActionKind

        kind = action.kind

        if kind == ActionKind.DISCARD:
            tile_code = action.tile.to_code() if action.tile else "?"
            riichi_str = "并立直" if action.declare_riichi else ""
            return f"打{tile_code}{riichi_str}"

        if kind == ActionKind.OPEN_MELD and action.meld:
            m = action.meld
            tiles = "/".join(t.to_code() for t in m.tiles) if m.tiles else "?"
            called = m.called_tile.to_code() if m.called_tile else "?"
            kind_map = {"chii": "吃", "pon": "碰", "daiminkan": "杠"}
            cn = kind_map.get(m.kind.value, m.kind.value)
            return f"{cn} {tiles} (叫{called})"

        if kind == ActionKind.ANKAN and action.meld:
            m = action.meld
            tiles = "/".join(t.to_code() for t in m.tiles) if m.tiles else "?"
            return f"暗杠 {tiles}"

        if kind == ActionKind.SHANKUMINKAN and action.meld:
            m = action.meld
            tiles = "/".join(t.to_code() for t in m.tiles) if m.tiles else "?"
            called = m.called_tile.to_code() if m.called_tile else "?"
            return f"加杠 {tiles} (叫{called})"

        if kind == ActionKind.RON:
            return "荣和"

        if kind == ActionKind.TSUMO:
            return "自摸"

        if kind == ActionKind.PASS_CALL:
            return "跳过"

        if kind == ActionKind.DRAW:
            return "摸牌"

        return kind.value

    def end_episode(self, points: int) -> None:
        """结束本局，更新统计."""
        self.episode_stats.total_points = points
        self.episode_stats.hands_played = 1
        self.match_stats.points += points
        self.match_stats.hands += 1
