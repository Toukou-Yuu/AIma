"""对话记录器 - 实时记录完整的 LLM 对话历史.

职责：
- 管理对话日志文件的打开/写入/关闭
- 格式化消息为 Markdown
- 实时写入并刷新（支持 tail -f）

设计原则：
- 高内聚：只负责对话日志的记录
- 低耦合：通过构造函数注入依赖（player_id, conversation_id）
- 资源管理：文件在 __init__ 打开，在 close() 关闭
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm.protocol import ChatMessage

log = logging.getLogger(__name__)


class ConversationLogger:
    """对话记录器，有明确的生命周期.

    高内聚：只负责对话日志的记录
    低耦合：通过构造函数注入依赖（player_id, conversation_id）
    资源管理：文件在 __init__ 打开，在 close() 关闭

    改进：header 只在首次写入 Turn 时才写入，避免空文件和多次 header
    """

    def __init__(
        self,
        player_id: str,
        conversation_id: str,
        enabled: bool = True,
    ) -> None:
        """初始化对话记录器.

        Args:
            player_id: 玩家 ID（用于确定输出目录）
            conversation_id: 本地对话 ID（用于文件命名）
            enabled: 是否启用（支持配置开关）

        生命周期：
        - 创建时：打开文件（追加模式），但不立即写 header
        - 首次 log_turn：写入 header + Turn 内容
        - 结束时：关闭文件
        """
        self.player_id = player_id
        self.conversation_id = conversation_id
        self.enabled = enabled
        self._file = None
        self._header_written = False  # 标记 header 是否已写入

        if not enabled:
            return

        try:
            # 构建输出路径：configs/players/{player_id}/conversations/{YYYYMMDD}-{conversation_id}.md
            date_str = datetime.now().strftime("%Y%m%d")
            output_dir = Path(f"configs/players/{player_id}/conversations")
            output_dir.mkdir(parents=True, exist_ok=True)

            filename = f"{date_str}-{conversation_id}.md"
            filepath = output_dir / filename

            self._file = open(filepath, "a", encoding="utf-8")
            # 不立即写 header，等首次 log_turn 时再写
        except Exception as e:
            log.error("failed to initialize conversation logger: %s", e)
            self.enabled = False

    def log_turn(
        self,
        turn_number: int,
        seat: int,
        phase: str,
        messages: list["ChatMessage"],
        response: str,
    ) -> None:
        """记录一轮对话.

        Args:
            turn_number: 轮次编号（从 1 开始）
            seat: 座位号
            phase: 游戏阶段（如 "in_round"）
            messages: 发送给 LLM 的消息列表
            response: LLM 返回的响应
        """
        if not self.enabled or self._file is None:
            return

        try:
            # 首次写入时写 header（确保只有真实内容时才有 header）
            if not self._header_written:
                self._write_header(self.conversation_id)
                self._header_written = True

            self._write_turn(turn_number, seat, phase, messages, response)
            self._file.flush()  # 实时刷新，支持 tail -f
        except Exception as e:
            log.error("failed to log conversation turn: %s", e)

    def close(self) -> None:
        """结束记录，关闭文件.

        应在对局结束时调用（EpisodeContext 结束时）
        """
        if self._file:
            try:
                self._file.close()
            except Exception as e:
                log.error("failed to close conversation logger: %s", e)
            finally:
                self._file = None

    def _write_header(self, conversation_id: str) -> None:
        """写入文件头（会话信息）."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._file.write(f"## 对局 {timestamp} (conversation: {conversation_id})\n\n")

    def _write_turn(
        self,
        turn_number: int,
        seat: int,
        phase: str,
        messages: list["ChatMessage"],
        response: str,
    ) -> None:
        """写入一轮对话（Markdown 格式）."""
        self._file.write(f"### Turn {turn_number} (seat={seat}, phase={phase})\n\n")

        for msg in messages:
            role_cn = {
                "system": "System",
                "user": "User",
                "assistant": "Assistant",
            }.get(msg.role, msg.role.capitalize())
            self._file.write(f"**{role_cn}**:\n")
            self._file.write(f"{msg.content}\n\n")

        self._file.write("**Assistant**:\n")
        self._file.write(f"{response}\n\n")

        self._file.write("---\n\n")
