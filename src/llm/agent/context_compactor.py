"""LLM-assisted semantic compaction for older chat history."""

from __future__ import annotations

import logging

from llm.agent.message_ledger import LedgerMessage
from llm.protocol import ChatMessage, CompletionClient

log = logging.getLogger(__name__)


class ContextCompactor:
    """Produce a semantic summary for older user/assistant decision history."""

    def compact(
        self,
        *,
        client: CompletionClient,
        messages: list[LedgerMessage],
        hand_number: int,
        target_tokens: int,
    ) -> LedgerMessage | None:
        """Summarize older messages into one replacement history message."""
        if not messages:
            return None
        prompt = self._build_compaction_prompt(messages, target_tokens=target_tokens)
        try:
            summary = client.complete(
                [
                    ChatMessage(
                        role="system",
                        content=(
                            "你是AIma麻将代理的上下文压缩器。"
                            "只总结历史对话，不做出麻将行动选择。"
                        ),
                    ),
                    ChatMessage(role="user", content=prompt),
                ]
            ).strip()
        except Exception:
            log.exception("semantic context compaction failed")
            return None
        if not summary:
            return None
        return LedgerMessage(
            message_id="history_semantic_summary",
            role="user",
            content=f"以下是较早对局历史的语义压缩摘要：\n{summary}",
            turn_index=messages[-1].turn_index,
            hand_number=hand_number,
            kind="summary",
            compression_state="autocompact",
        )

    def _build_compaction_prompt(
        self,
        messages: list[LedgerMessage],
        *,
        target_tokens: int,
    ) -> str:
        parts = [
            "请把下面较早的麻将决策对话压缩成一段可继续用于后续决策的上下文摘要。",
            "要求：",
            "- 保留影响后续决策的牌桌事实、已经暴露的信息、关键读牌线索和本家策略倾向。",
            "- 保留模型已经承诺或反复采用的打法理由。",
            "- 不添加原文没有出现的信息，不猜测他家暗手。",
            "- 不输出动作 JSON，只输出摘要正文。",
            f"- 目标长度约 {max(64, target_tokens)} token。",
            "",
            "历史消息：",
        ]
        for message in messages:
            role = "user" if message.role == "user" else "assistant"
            parts.append(f"[{role} turn={message.turn_index}]")
            parts.append(message.content)
            parts.append("")
        return "\n".join(parts)
