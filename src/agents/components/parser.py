"""OutputParser - LLM 输出解析组件.

职责：
- 包装 DecisionParser.parse_llm_response_detail
- 返回 ParseResult 供 pipeline 使用
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agents.pipeline_result import ParseResult
from llm.agent.decision_parser import DecisionParser

if TYPE_CHECKING:
    from kernel.api.legal_actions import LegalAction


class OutputParser:
    """LLM 输出解析器.

    包装 DecisionParser，将解析结果转换为 ParseResult。
    """

    @staticmethod
    def parse(
        raw_response: str,
        legal_actions: tuple["LegalAction", ...],
    ) -> ParseResult:
        """解析 LLM 响应.

        Args:
            raw_response: LLM 返回的原始文本
            legal_actions: 合法动作列表

        Returns:
            ParseResult 包含 choice、why、status、error
        """
        detail = DecisionParser.parse_llm_response_detail(raw_response, legal_actions)
        return ParseResult(
            choice=detail.choice,
            why=detail.why,
            status=detail.status,
            error=detail.error,
        )