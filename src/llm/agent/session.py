"""SessionManager - 会话管理组件.

职责：
- 为每个 Agent 实例生成唯一 session_token
- 构建 session_id（确保不同实例的会话隔离）
- 保持同一实例的对话历史连续性
"""

from __future__ import annotations

from uuid import uuid4


class SessionManager:
    """会话管理组件.

    用于确保：
    - 不同 Agent 实例有独立的 LLM 会话上下文
    - 同一 Agent 实例保持对话历史连续

    Example:
        >>> session = SessionManager("player_001")
        >>> session.build_session_id(0)
        'majiang_player_player_001_a1b2c3d4'
    """

    def __init__(self, player_id: str | None = None) -> None:
        """初始化会话管理器.

        Args:
            player_id: 玩家 ID（可选）
        """
        self.player_id = player_id
        # 为每个实例生成唯一令牌（UUID 前 8 位）
        self._session_token = str(uuid4())[:8]

    def build_session_id(self, seat: int) -> str:
        """构建会话 ID.

        会话 ID 格式：majiang_player_{player_id or seat}_{session_token}
        - player_id 存在时使用 player_id
        - player_id 不存在时使用 seat_{seat}
        - session_token 确保不同实例的唯一性

        Args:
            seat: 当前座位（0-3）

        Returns:
            会话 ID 字符串
        """
        session_key = self.player_id or f"seat_{seat}"
        return f"majiang_player_{session_key}_{self._session_token}"

    def get_token(self) -> str:
        """获取当前实例的 session_token.

        Returns:
            session_token 字符串
        """
        return self._session_token