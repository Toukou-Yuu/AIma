"""Agent 包 - LLM 玩家代理封装."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel.api.legal_actions import LegalAction
    from kernel.engine.state import GameState
    from llm.protocol import ChatMessage, CompletionClient

log = logging.getLogger(__name__)


@dataclass
class Decision:
    """Agent 决策结果."""

    action: "LegalAction"
    why: str | None
    history: list["ChatMessage"]


class PlayerAgent:
    """玩家代理 - 封装 LLM 调用和状态管理.

    Phase 2: 支持从 profile.json 加载个性化配置.
    """

    def __init__(
        self,
        player_id: str | None = None,
        profile: "PlayerProfile | None" = None,
        max_history_rounds: int = 10,
    ):
        """初始化 Agent.

        Args:
            player_id: 玩家 ID（用于从 configs/players/{id}/profile.json 加载配置）
            profile: 直接传入的 profile（优先级高于 player_id）
            max_history_rounds: 最大历史对话轮数
        """
        self.player_id = player_id
        self.max_history_rounds = max_history_rounds
        self._history: list[ChatMessage] = []

        # 加载 profile
        if profile is not None:
            self.profile = profile
        elif player_id is not None:
            from llm.agent.profile import load_profile
            loaded = load_profile(player_id)
            self.profile = loaded if loaded is not None else self._default_profile()
        else:
            self.profile = self._default_profile()

    def _default_profile(self) -> "PlayerProfile":
        """返回默认 profile."""
        from llm.agent.profile import PlayerProfile
        return PlayerProfile(
            id="default",
            name="DefaultBot",
            model="gpt-4o-mini",
            provider="openai",
            temperature=0.7,
            max_tokens=1024,
            timeout_sec=120.0,
            persona_prompt="",
            strategy_prompt="",
        )

    def decide(
        self,
        state: GameState,
        seat: int,
        *,
        client: CompletionClient | None,
        dry_run: bool = False,
        session_audit: bool = False,
        request_delay_seconds: float = 0.0,
    ) -> Decision:
        """根据当前局面做出决策.

        Args:
            state: 当前游戏状态
            seat: 玩家座位
            client: LLM 客户端（dry_run 时可为 None）
            dry_run: 是否跳过 LLM 调用，直接选第一个合法动作
            session_audit: 是否记录审计日志
            request_delay_seconds: LLM 调用前延迟

        Returns:
            Decision: 包含选择的动作、原因说明和更新后的历史
        """
        # 延迟导入避免循环依赖
        from kernel.api.legal_actions import legal_actions
        from kernel.api.observation import observation
        from kernel.engine.actions import ActionKind
        from llm.agent.prompt_builder import build_decision_prompt, build_system_prompt
        from llm.parse import extract_json_object
        from llm.protocol import ChatMessage
        from llm.validate import explain_text_from_choice, find_matching_legal_action
        from llm.wire import legal_action_to_wire

        # 1. 获取合法动作
        acts = legal_actions(state, seat)
        if not acts:
            msg = f"no legal_actions for seat {seat}"
            raise RuntimeError(msg)

        # 2. 唯一合法动作为「过」时跳过 LLM
        if len(acts) == 1 and acts[0].kind == ActionKind.PASS_CALL:
            if session_audit:
                log.info("llm_skipped singleton pass_call seat=%s", seat)
            return Decision(acts[0], None, self._history)

        # 3. dry_run 模式
        if dry_run or client is None:
            return Decision(acts[0], None, self._history)

        # 4. 构建 observation 和 prompt
        obs = observation(state, seat, mode="human")
        user_content = build_decision_prompt(obs, acts)
        current_user_msg = ChatMessage(role="user", content=user_content)

        # 5. 拼装消息（使用 profile 的 persona/strategy）
        messages = [ChatMessage(role="system", content=build_system_prompt(self.profile))]
        if self._history:
            messages.extend(self._history)
        messages.append(current_user_msg)

        # 6. 调用 LLM
        if request_delay_seconds > 0:
            time.sleep(request_delay_seconds)
        raw = client.complete(messages)
        if session_audit:
            head = raw if len(raw) <= 600 else raw[:600] + "…"
            log.debug("llm raw_head seat=%s %r", seat, head)
            # 记录历史消息数量
            hist_len = len(self._history)
            log.debug("llm_history seat=%s history_msgs=%s", seat, hist_len)

        # 7. 解析和校验
        try:
            choice = extract_json_object(raw)
        except (ValueError, TypeError) as e:
            log.warning("parse failed, fallback first legal: %s", e)
            return Decision(acts[0], None, self._history)

        why = explain_text_from_choice(choice)
        la = find_matching_legal_action(acts, choice)

        # 8. 构建 assistant 消息内容
        assistant_content = json.dumps(choice, ensure_ascii=False)

        # 9. 处理匹配失败的情况（仍记录历史）
        if la is None:
            log.warning("choice not in legal_actions, fallback first: %s", choice)
            self._history.append(current_user_msg)
            self._history.append(ChatMessage(role="assistant", content=assistant_content))
            # 截断历史
            max_history_msgs = self.max_history_rounds * 2
            if len(self._history) > max_history_msgs:
                self._history = self._history[-max_history_msgs:]
            return Decision(acts[0], None, self._history)

        # 10. 记录审计日志
        if session_audit:
            log.info(
                "llm_choice seat=%s %s",
                seat,
                json.dumps(legal_action_to_wire(la), ensure_ascii=False),
            )

        # 11. 更新历史：追加 user + assistant
        self._history.append(current_user_msg)
        self._history.append(ChatMessage(role="assistant", content=assistant_content))

        # 12. 截断历史
        max_history_msgs = self.max_history_rounds * 2
        if len(self._history) > max_history_msgs:
            self._history = self._history[-max_history_msgs:]

        return Decision(la, why, self._history)

    def clear_history(self) -> None:
        """清空对话历史（用于新一局开始）."""
        self._history = []
