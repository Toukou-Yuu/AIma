"""EpisodeContext - 本局运行时上下文（Agent 无状态化的关键）."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from llm.agent.context_store import ContextEvent, ContextStore
from llm.agent.memory import EpisodeStats
from llm.agent.message_ledger import LedgerMessage, MessageLedger
from llm.agent.stats import MatchStats

if TYPE_CHECKING:
    from kernel.api.legal_actions import LegalAction
    from kernel.api.observation import Observation
    from llm.agent import Decision
    from llm.agent.context_store import CompressionLevel
    from llm.agent.conversation_logger import ConversationLogger
    from llm.agent.event_journal import MatchJournal


@dataclass
class EpisodeContext:
    """本局运行时上下文.

    用于将 Agent 从"状态容器"改为"纯函数".
    运行时状态（本局统计、本场统计、决策历史）存储在此，
    Agent 只保留长期状态（profile/memory/stats）.
    """

    seat: int
    match_id: str = ""
    hand_number: int = 1
    episode_stats: EpisodeStats = field(default_factory=lambda: EpisodeStats("", 0))
    match_stats: MatchStats = field(default_factory=MatchStats)
    match_history_archive: tuple[str, ...] = ()
    match_journal: MatchJournal | None = field(default=None, repr=False)
    decision_history: list[Decision] = field(default_factory=list)
    context_store: ContextStore = field(default_factory=ContextStore, repr=False)
    message_ledger: MessageLedger = field(default_factory=MessageLedger, repr=False)

    # 对话记录器（可选，用于调试）
    conversation_logger: ConversationLogger | None = field(default=None, repr=False)

    def __post_init__(self):
        """初始化后确保 episode_stats 的 seat 正确."""
        if self.episode_stats.seat != self.seat:
            self.episode_stats.seat = self.seat

    def append_user_message(self, content: str, *, turn_index: int) -> LedgerMessage:
        """Append one user turn-state message."""
        return self.message_ledger.append(
            role="user",
            content=content,
            turn_index=turn_index,
            hand_number=self.hand_number,
            kind="turn_state",
        )

    def append_assistant_message(self, content: str, *, turn_index: int) -> LedgerMessage:
        """Append one assistant decision-reply message."""
        return self.message_ledger.append(
            role="assistant",
            content=content,
            turn_index=turn_index,
            hand_number=self.hand_number,
            kind="decision_reply",
        )

    def project_message_history(
        self,
        *,
        history_budget: int,
        compression_level: CompressionLevel,
    ) -> list[LedgerMessage]:
        """Project prior user/assistant turns for the next request."""
        if history_budget <= 0 or not self.message_ledger.messages:
            return []

        turn_indexes = self.message_ledger.turn_indexes()
        if not turn_indexes:
            return []

        if compression_level == "none":
            keep_turns = set(turn_indexes)
            return self.message_ledger.messages_for_turns(keep_turns)

        if compression_level in {"snip", "micro"}:
            keep_turns = set(turn_indexes[-history_budget:])
            keep = self.message_ledger.messages_for_turns(keep_turns)
            if compression_level == "micro":
                return [self._clip_ledger_message(message) for message in keep]
            return keep

        if len(turn_indexes) <= history_budget:
            return self.message_ledger.messages_for_turns(set(turn_indexes))

        if compression_level == "collapse":
            tail_turns = max(1, history_budget // 2 or 1)
        else:
            tail_turns = 1 if history_budget <= 2 else 2

        recent_turns = set(turn_indexes[-tail_turns:])
        recent_messages = self.message_ledger.messages_for_turns(recent_turns)
        summary = self._build_history_summary_message(
            summary_kind="autocompact" if compression_level == "autocompact" else "collapse",
        )
        if summary is None:
            return recent_messages
        return [summary, *recent_messages]

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

    def record_decision(
        self,
        decision: Decision,
        *,
        observation: Observation | None = None,
        legal_actions: tuple[LegalAction, ...] | None = None,
        phase: str | None = None,
    ) -> None:
        """记录决策到历史与结构化事实仓库。"""
        self.decision_history.append(decision)
        action = decision.action
        obs_phase = phase or (observation.phase.value if observation is not None else "")
        riichi_players: tuple[int, ...] = ()
        scores: tuple[int, ...] = ()
        last_discard: str | None = None
        last_discard_seat: int | None = None
        if observation is not None:
            riichi_players = tuple(i for i, flag in enumerate(observation.riichi_state) if flag)
            scores = tuple(observation.scores)
            last_discard = observation.last_discard.to_code() if observation.last_discard else None
            last_discard_seat = observation.last_discard_seat
        self.context_store.append_event(
            ContextEvent(
                turn_index=len(self.decision_history),
                phase=obs_phase,
                action_kind=action.kind.value,
                action_text=self._describe_action(action),
                why=decision.why,
                legal_action_count=len(legal_actions) if legal_actions is not None else 0,
                riichi_players=riichi_players,
                scores=scores,
                last_discard=last_discard,
                last_discard_seat=last_discard_seat,
            )
        )

    def project_history(
        self,
        *,
        detailed: bool,
        history_budget: int,
        compression_level: CompressionLevel,
    ) -> str:
        """根据预算和压缩策略构建历史文本。"""
        projection = self.context_store.project_history(
            detailed=detailed,
            history_budget=history_budget,
            compression_level=compression_level,
        )
        return projection.text

    def project_public_history(
        self,
        *,
        detailed: bool,
        history_budget: int,
        compression_level: CompressionLevel,
    ) -> str:
        """返回本局公共事件历史。"""
        if self.match_journal is None:
            return ""
        return self.match_journal.project_current_hand(
            viewer_seat=self.seat,
            detailed=detailed,
            history_budget=history_budget,
            compression_level=compression_level,
        )

    def project_match_history(
        self,
        *,
        archive_budget: int,
        compression_level: CompressionLevel,
    ) -> str:
        """返回跨局摘要文本（公共前情 + 自家归档）。"""
        if archive_budget <= 0:
            return ""
        lines: list[str] = []
        if self.match_journal is not None:
            public_archive = self.match_journal.project_archived_hands(
                archive_budget=archive_budget,
                compression_level=compression_level,
            )
            if public_archive:
                lines.append("公共前情:")
                lines.append(public_archive)
        if self.match_history_archive:
            archived = self.match_history_archive[-archive_budget:]
            lines.append(f"自家归档（最近 {len(archived)} 局）:")
            lines.extend(archived)
        return "\n".join(lines)

    def build_recent_public_summary(
        self,
        *,
        history_budget: int,
        compression_level: CompressionLevel,
    ) -> str:
        """Return recent public events as prompt material."""
        if self.match_journal is None:
            return ""
        return self.match_journal.project_current_hand(
            viewer_seat=self.seat,
            detailed=False,
            history_budget=history_budget,
            compression_level=compression_level,
        )

    def build_hand_summary(self) -> str:
        """生成本局归档摘要，供后续对局注入。"""
        summary_parts = [f"第{self.hand_number}局（自家）"]
        if self.episode_stats.total_points:
            sign = "+" if self.episode_stats.total_points > 0 else ""
            summary_parts.append(f"得点{sign}{self.episode_stats.total_points}")
        if self.episode_stats.wins:
            summary_parts.append(f"和了{self.episode_stats.wins}次")
        if self.episode_stats.deal_ins:
            summary_parts.append(f"放铳{self.episode_stats.deal_ins}次")
        if self.episode_stats.riichi_count:
            summary_parts.append(f"立直{self.episode_stats.riichi_count}次")

        history_text = self.context_store.project_history(
            detailed=False,
            history_budget=4,
            compression_level="collapse",
        ).text
        if history_text:
            return " | ".join(summary_parts) + "\n关键决策:\n" + history_text
        return " | ".join(summary_parts)

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
            kind_map = {"chi": "吃", "pon": "碰", "daiminkan": "杠"}
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
            kind_map = {"chi": "吃", "pon": "碰", "daiminkan": "杠"}
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

    def _build_history_summary_message(
        self,
        *,
        summary_kind: str,
    ) -> LedgerMessage | None:
        public_summary = self.build_recent_public_summary(
            history_budget=4,
            compression_level="autocompact" if summary_kind == "autocompact" else "collapse",
        )
        self_summary = self.context_store.project_history(
            detailed=False,
            history_budget=4,
            compression_level="autocompact" if summary_kind == "autocompact" else "collapse",
        ).text

        lines: list[str] = []
        if public_summary:
            lines.append("较早公开事件摘要:")
            lines.append(public_summary)
        if self_summary:
            lines.append("较早自家决策摘要:")
            lines.append(self_summary)
        if not lines:
            return None

        return LedgerMessage(
            message_id=f"history_{summary_kind}_summary",
            role="user",
            content="\n".join(lines),
            turn_index=0,
            hand_number=self.hand_number,
            kind="summary",
            compression_state="autocompact" if summary_kind == "autocompact" else "collapse",
        )

    def _clip_ledger_message(self, message: LedgerMessage) -> LedgerMessage:
        limit = 320 if message.role == "user" else 160
        content = message.content
        if len(content) <= limit:
            return message
        return LedgerMessage(
            message_id=message.message_id,
            role=message.role,
            content=content[: max(0, limit - 1)] + "…",
            turn_index=message.turn_index,
            hand_number=message.hand_number,
            kind=message.kind,
            compression_state="micro",
        )

    def end_episode(self, points: int) -> None:
        """结束本局，更新统计."""
        self.episode_stats.total_points = points
        self.episode_stats.hands_played = 1
        self.match_stats.points += points
        self.match_stats.hands += 1
