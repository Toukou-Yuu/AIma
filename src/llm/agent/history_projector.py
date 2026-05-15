"""HistoryProjector - 历史投影."""

from __future__ import annotations

from typing import TYPE_CHECKING

from llm.agent.context_store import CompressionLevel
from llm.agent.message_ledger import LedgerMessage
from llm.agent.services.action_descriptor import describe_action, describe_action_summary

if TYPE_CHECKING:
    from llm.agent.context_store import ContextStore
    from llm.agent.episode_state import EpisodeState
    from llm.agent.event_journal import MatchJournal
    from llm.agent.message_ledger import MessageLedger


class HistoryProjector:
    """历史投影器.

    管理历史消息的投影和格式化。
    """

    def __init__(
        self,
        state: EpisodeState,
        message_ledger: MessageLedger,
        context_store: ContextStore,
        match_journal: MatchJournal | None,
    ):
        self._state = state
        self._message_ledger = message_ledger
        self._context_store = context_store
        self._match_journal = match_journal

    def project_message_history(
        self,
        *,
        history_budget: int,
        compression_level: CompressionLevel,
    ) -> list[LedgerMessage]:
        """Project prior user/assistant turns for the next request."""
        if history_budget <= 0 or not self._message_ledger.messages:
            return []

        turn_indexes = self._message_ledger.turn_indexes()
        if not turn_indexes:
            return []

        if compression_level == "none":
            keep_turns = set(turn_indexes)
            return self._message_ledger.messages_for_turns(keep_turns)

        if compression_level in {"snip", "micro"}:
            keep_turns = set(turn_indexes[-history_budget:])
            keep = self._message_ledger.messages_for_turns(keep_turns)
            if compression_level == "micro":
                return [self._clip_ledger_message(message) for message in keep]
            return keep

        if len(turn_indexes) <= history_budget:
            return self._message_ledger.messages_for_turns(set(turn_indexes))

        if compression_level == "collapse":
            tail_turns = max(1, history_budget // 2 or 1)
        else:
            tail_turns = 1 if history_budget <= 2 else 2

        recent_turns = set(turn_indexes[-tail_turns:])
        recent_messages = self._message_ledger.messages_for_turns(recent_turns)
        summary = self._build_history_summary_message(
            summary_kind="autocompact" if compression_level == "autocompact" else "collapse",
        )
        if summary is None:
            return recent_messages
        return [summary, *recent_messages]

    def project_history(
        self,
        *,
        detailed: bool,
        history_budget: int,
        compression_level: CompressionLevel,
    ) -> str:
        """根据预算和压缩策略构建历史文本。"""
        projection = self._context_store.project_history(
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
        if self._match_journal is None:
            return ""
        return self._match_journal.project_current_hand(
            viewer_seat=self._state.seat,
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
        if self._match_journal is not None:
            public_archive = self._match_journal.project_archived_hands(
                archive_budget=archive_budget,
                compression_level=compression_level,
            )
            if public_archive:
                lines.append("公共前情:")
                lines.append(public_archive)
        if self._state.match_history_archive:
            archived = self._state.match_history_archive[-archive_budget:]
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
        if self._match_journal is None:
            return ""
        return self._match_journal.project_current_hand(
            viewer_seat=self._state.seat,
            detailed=False,
            history_budget=history_budget,
            compression_level=compression_level,
        )

    def build_hand_summary(self) -> str:
        """生成本局归档摘要，供后续对局注入。"""
        summary_parts = [f"第{self._state.hand_number}局（自家）"]
        if self._state.episode_stats.total_points:
            sign = "+" if self._state.episode_stats.total_points > 0 else ""
            summary_parts.append(f"得点{sign}{self._state.episode_stats.total_points}")
        if self._state.episode_stats.wins:
            summary_parts.append(f"和了{self._state.episode_stats.wins}次")
        if self._state.episode_stats.deal_ins:
            summary_parts.append(f"放铳{self._state.episode_stats.deal_ins}次")
        if self._state.episode_stats.riichi_count:
            summary_parts.append(f"立直{self._state.episode_stats.riichi_count}次")

        history_text = self._context_store.project_history(
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
        if not self._state.decision_history:
            return ""

        lines = []
        for i, d in enumerate(self._state.decision_history, 1):
            action_desc = describe_action_summary(d.action)
            if action_desc:  # 只记录关键事件
                lines.append(f"第{i}巡: {action_desc}")

        return "\n".join(lines)

    def format_history_for_prompt(self) -> str:
        """将决策历史格式化为纯文本（完整版，用于对比调试）.

        Returns:
            纯文本格式的决策历史，每行一条记录
        """
        if not self._state.decision_history:
            return ""

        lines = []
        for i, d in enumerate(self._state.decision_history, 1):
            action_desc = describe_action(d.action)
            reason = d.why if d.why else "未说明"
            lines.append(f"第{i}巡: {action_desc} (理由: {reason})")

        return "\n".join(lines)

    def _build_history_summary_message(
        self,
        *,
        summary_kind: str,
    ) -> LedgerMessage | None:
        public_summary = self.build_recent_public_summary(
            history_budget=4,
            compression_level="autocompact" if summary_kind == "autocompact" else "collapse",
        )
        self_summary = self._context_store.project_history(
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
            hand_number=self._state.hand_number,
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