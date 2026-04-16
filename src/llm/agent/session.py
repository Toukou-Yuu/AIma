"""会话策略与日志命名。"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

SessionScope = Literal["stateless", "per_hand", "per_match"]


class ModelSessionPolicy:
    """模型侧会话策略。"""

    def __init__(
        self,
        player_id: str | None = None,
        *,
        scope: SessionScope = "per_hand",
    ) -> None:
        """初始化会话策略。"""
        self.player_id = player_id
        self.scope = scope
        self._session_token = str(uuid4())[:8]

    def build_session_id(
        self,
        seat: int,
        *,
        hand_number: int = 1,
        match_id: str | None = None,
    ) -> str | None:
        """按策略构建 session_id。"""
        if self.scope == "stateless":
            return None

        session_key = self.player_id or f"seat_{seat}"
        base = f"majiang_player_{session_key}_{self._session_token}"
        if self.scope == "per_match":
            if match_id:
                return f"{base}_m{match_id}"
            return base
        return f"{base}_h{hand_number}"

    def get_token(self) -> str:
        """获取当前实例的唯一令牌。"""
        return self._session_token


class ConversationLogNamer:
    """对话日志命名器。"""

    def __init__(self, player_id: str | None = None) -> None:
        self.player_id = player_id
        self._session_token = str(uuid4())[:8]

    def build_log_session_id(self, seat: int, hand_number: int = 1) -> str:
        """为日志文件构建稳定的局级会话名。"""
        session_key = self.player_id or f"seat_{seat}"
        return f"majiang_player_{session_key}_{self._session_token}_h{hand_number}"
