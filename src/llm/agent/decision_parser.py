"""DecisionParser - 决策解析组件.

职责：
- 解析 LLM 返回的 JSON 响应
- 匹配解析结果与合法动作
- 处理解析失败和匹配失败的 fallback
- 提取决策原因（why）
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from kernel.api.legal_actions import LegalAction

log = logging.getLogger(__name__)

ParseStatus = Literal["matched", "parse_failed", "match_failed"]
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\{.*?\}\s*```", re.DOTALL)


@dataclass(frozen=True, slots=True)
class DecisionParseResult:
    """结构化的模型响应解析结果。"""

    action: "LegalAction | None"
    why: str | None
    choice: dict[str, Any] | None
    status: ParseStatus
    note: str | None = None
    error: str | None = None


class DecisionParser:
    """决策解析组件.

    负责将 LLM 的文本响应解析为合法动作。
    """

    @staticmethod
    def parse_llm_response(
        raw_response: str,
        legal_actions: tuple["LegalAction", ...],
    ) -> tuple["LegalAction | None", str | None]:
        """解析 LLM 响应并匹配合法动作.

        Args:
            raw_response: LLM 返回的原始文本
            legal_actions: 合法动作列表

        Returns:
            (匹配的合法动作, 决策原因) - 如果解析或匹配失败，返回 (None, None)
        """
        result = DecisionParser.parse_llm_response_detail(raw_response, legal_actions)
        if result.action is None:
            return None, None
        return result.action, result.why

    @staticmethod
    def parse_llm_response_detail(
        raw_response: str,
        legal_actions: tuple["LegalAction", ...],
    ) -> DecisionParseResult:
        """解析 LLM 响应并保留可写入 conversation 的诊断信息。"""
        from llm.parse import extract_json_object
        from llm.validate import explain_text_from_choice, find_matching_legal_action

        note = "fenced_json_accepted" if _JSON_FENCE_RE.search(raw_response.strip()) else None

        # 1. 解析 JSON
        try:
            choice = extract_json_object(raw_response)
        except (ValueError, TypeError) as e:
            log.warning("parse failed: %s", e)
            return DecisionParseResult(
                action=None,
                why=None,
                choice=None,
                status="parse_failed",
                note=note,
                error=str(e),
            )

        # 2. 提取原因
        why = explain_text_from_choice(choice)

        # 3. 匹合法动作
        la = find_matching_legal_action(legal_actions, choice)
        if la is None:
            return DecisionParseResult(
                action=None,
                why=why,
                choice=choice,
                status="match_failed",
                note=note,
                error="response did not match any legal action",
            )

        return DecisionParseResult(
            action=la,
            why=why,
            choice=choice,
            status="matched",
            note=note,
            error=None,
        )

    @staticmethod
    def validate_decision(
        action: "LegalAction",
        legal_actions: tuple["LegalAction", ...],
    ) -> bool:
        """验证决策是否合法.

        Args:
            action: 待验证的动作
            legal_actions: 合法动作列表

        Returns:
            True 如果动作在合法动作列表中
        """
        return action in legal_actions

    @staticmethod
    def fallback_action(
        legal_actions: tuple["LegalAction", ...],
    ) -> "LegalAction":
        """获取 fallback 动作（第一个合法动作）.

        Args:
            legal_actions: 合法动作列表

        Returns:
            第一个合法动作

        Raises:
            RuntimeError: 如果 legal_actions 为空
        """
        if not legal_actions:
            raise RuntimeError("no legal_actions for fallback")
        return legal_actions[0]

    @staticmethod
    def choice_to_wire(choice: dict) -> str:
        """将 choice 序列化为 JSON 字符串（用于 assistant 消息）.

        Args:
            choice: 解析后的 choice dict

        Returns:
            JSON 字符串
        """
        return json.dumps(choice, ensure_ascii=False)
