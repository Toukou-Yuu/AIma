"""EpisodeContext - 本局运行时上下文（Agent 无状态化的关键）."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from llm.agent.context_store import ContextStore
from llm.agent.episode_state import EpisodeState
from llm.agent.history_projector import HistoryProjector
from llm.agent.message_ledger import LedgerMessage, MessageLedger
from llm.agent.message_manager import MessageManager
from llm.agent.stats_recorder import StatsRecorder

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

    重构为协调类，组合子组件：
    - EpisodeState: 纯状态容器
    - MessageManager: 消息管理
    - StatsRecorder: 统计记录
    - HistoryProjector: 历史投影
    """

    # 子组件（延迟初始化）
    _state: EpisodeState = field(init=False)
    _messages: MessageManager = field(init=False)
    _stats: StatsRecorder = field(init=False)
    _history: HistoryProjector = field(init=False)

    # 其他依赖组件
    context_store: ContextStore = field(default_factory=ContextStore)
    match_journal: MatchJournal | None = field(default=None)
    conversation_logger: ConversationLogger | None = field(default=None)

    def __init__(
        self,
        seat: int,
        match_id: str = "",
        hand_number: int = 1,
        episode_stats=None,
        match_stats=None,
        match_history_archive: tuple[str, ...] = (),
        decision_history=None,
        context_store=None,
        match_journal=None,
        conversation_logger=None,
    ):
        """初始化 EpisodeContext.

        Args:
            seat: 座位号（必传）
            match_id: 对局 ID
            hand_number: 局号
            episode_stats: 本局统计（可选，默认自动创建）
            match_stats: 本场统计（可选，默认自动创建）
            match_history_archive: 归档历史
            decision_history: 决策历史（可选，默认空列表）
            context_store: 上下文仓库（可选，默认自动创建）
            match_journal: 公共事件日志（可选）
            conversation_logger: 对话记录器（可选）
        """
        from llm.agent.memory import EpisodeStats
        from llm.agent.stats import MatchStats

        # 初始化状态容器
        self._state = EpisodeState(
            seat=seat,
            match_id=match_id,
            hand_number=hand_number,
            episode_stats=episode_stats or EpisodeStats("", seat),
            match_stats=match_stats or MatchStats(),
            match_history_archive=match_history_archive,
            decision_history=decision_history or [],
        )

        # 初始化其他依赖组件
        self.context_store = context_store or ContextStore()
        self.match_journal = match_journal
        self.conversation_logger = conversation_logger

        # 初始化消息管理器
        message_ledger = MessageLedger()
        self._messages = MessageManager(_ledger=message_ledger)

        # 初始化统计记录器
        self._stats = StatsRecorder(
            state=self._state,
            context_store=self.context_store,
        )

        # 初始化历史投影器
        self._history = HistoryProjector(
            state=self._state,
            message_ledger=message_ledger,
            context_store=self.context_store,
            match_journal=self.match_journal,
        )

    # ==================== 状态属性（委托到 _state） ====================

    @property
    def seat(self) -> int:
        return self._state.seat

    @seat.setter
    def seat(self, value: int):
        self._state.seat = value

    @property
    def match_id(self) -> str:
        return self._state.match_id

    @match_id.setter
    def match_id(self, value: str):
        self._state.match_id = value

    @property
    def hand_number(self) -> int:
        return self._state.hand_number

    @hand_number.setter
    def hand_number(self, value: int):
        self._state.hand_number = value

    @property
    def episode_stats(self):
        return self._state.episode_stats

    @episode_stats.setter
    def episode_stats(self, value):
        self._state.episode_stats = value

    @property
    def match_stats(self):
        return self._state.match_stats

    @match_stats.setter
    def match_stats(self, value):
        self._state.match_stats = value

    @property
    def match_history_archive(self) -> tuple[str, ...]:
        return self._state.match_history_archive

    @match_history_archive.setter
    def match_history_archive(self, value: tuple[str, ...]):
        self._state.match_history_archive = value

    @property
    def decision_history(self):
        return self._state.decision_history

    @decision_history.setter
    def decision_history(self, value):
        self._state.decision_history = value

    # ==================== 消息管理（委托到 _messages） ====================

    def append_user_message(self, content: str, *, turn_index: int) -> LedgerMessage:
        """Append one user turn-state message."""
        return self._messages.append_user_message(
            content=content,
            turn_index=turn_index,
            hand_number=self._state.hand_number,
        )

    def append_assistant_message(self, content: str, *, turn_index: int) -> LedgerMessage:
        """Append one assistant decision-reply message."""
        return self._messages.append_assistant_message(
            content=content,
            turn_index=turn_index,
            hand_number=self._state.hand_number,
        )

    @property
    def message_ledger(self) -> MessageLedger:
        """消息账本（过渡接口，保持兼容性）。"""
        return self._messages._ledger

    def _clip_ledger_message(self, message: LedgerMessage) -> LedgerMessage:
        """裁剪消息（过渡接口，保持测试兼容性）。"""
        return self._history._clip_ledger_message(message)

    # match_journal setter（同步更新 _history）
    def _set_match_journal(self, value):
        self.match_journal = value
        if hasattr(self, '_history'):
            self._history._match_journal = value

    # ==================== 历史投影（委托到 _history） ====================

    def project_message_history(
        self,
        *,
        history_budget: int,
        compression_level: CompressionLevel,
    ) -> list[LedgerMessage]:
        """Project prior user/assistant turns for the next request."""
        return self._history.project_message_history(
            history_budget=history_budget,
            compression_level=compression_level,
        )

    def project_history(
        self,
        *,
        detailed: bool,
        history_budget: int,
        compression_level: CompressionLevel,
    ) -> str:
        """根据预算和压缩策略构建历史文本。"""
        return self._history.project_history(
            detailed=detailed,
            history_budget=history_budget,
            compression_level=compression_level,
        )

    def project_public_history(
        self,
        *,
        detailed: bool,
        history_budget: int,
        compression_level: CompressionLevel,
    ) -> str:
        """返回本局公共事件历史。"""
        return self._history.project_public_history(
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
        return self._history.project_match_history(
            archive_budget=archive_budget,
            compression_level=compression_level,
        )

    def build_recent_public_summary(
        self,
        *,
        history_budget: int,
        compression_level: CompressionLevel,
    ) -> str:
        """Return recent public events as prompt material."""
        return self._history.build_recent_public_summary(
            history_budget=history_budget,
            compression_level=compression_level,
        )

    def build_hand_summary(self) -> str:
        """生成本局归档摘要，供后续对局注入。"""
        return self._history.build_hand_summary()

    def format_history_summary(self) -> str:
        """生成关键事件摘要（替代逐条记录）.

        只保留关键事件：立直、和牌、放铳、副露（吃碰杠）
        丢弃普通打牌、摸牌、过牌等冗余信息

        Returns:
            纯文本格式的关键事件摘要，每行一条记录
        """
        return self._history.format_history_summary()

    def format_history_for_prompt(self) -> str:
        """将决策历史格式化为纯文本（完整版，用于对比调试）.

        Returns:
            纯文本格式的决策历史，每行一条记录
        """
        return self._history.format_history_for_prompt()

    # ==================== 统计记录（委托到 _stats） ====================

    def record_win(self, win_tile: str) -> None:
        """记录和了."""
        self._stats.record_win(win_tile)

    def record_deal_in(self, deal_in_tile: str) -> None:
        """记录放铳."""
        self._stats.record_deal_in(deal_in_tile)

    def record_riichi(self) -> None:
        """记录立直宣言."""
        self._stats.record_riichi()

    def record_decision(
        self,
        decision: Decision,
        *,
        observation: Observation | None = None,
        legal_actions: tuple[LegalAction, ...] | None = None,
        phase: str | None = None,
    ) -> None:
        """记录决策到历史与结构化事实仓库。"""
        self._stats.record_decision(
            decision,
            observation=observation,
            legal_actions=legal_actions,
            phase=phase,
        )

    def end_episode(self, points: int) -> None:
        """结束本局，更新统计."""
        self._stats.end_episode(points)