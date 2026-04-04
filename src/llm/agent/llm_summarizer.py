"""LLM 摘要生成器 - 使用 LLM 润色 memory 摘要."""

from __future__ import annotations

from llm.agent.memory import EpisodeStats, PlayerMemory
from llm.protocol import ChatMessage, CompletionClient


class LLMSummarizer:
    """使用 LLM 润色 memory 摘要."""

    def __init__(self, client: CompletionClient | None = None):
        self.client = client

    def polish(
        self,
        rule_based_memory: PlayerMemory,
        episode_stats: EpisodeStats,
    ) -> PlayerMemory:
        """将规则摘要润色为自然语言."""
        if self.client is None:
            return rule_based_memory

        # 构建润色 prompt
        prompt = self._build_polish_prompt(rule_based_memory, episode_stats)

        messages = [
            ChatMessage(
                role="system",
                content="你是一个麻将分析助手。请将规则化的统计摘要转换为自然语言建议。",
            ),
            ChatMessage(role="user", content=prompt),
        ]

        try:
            response = self.client.complete(messages)
            # 解析响应，提取润色后的 patterns
            polished_patterns = self._parse_response(response)

            return PlayerMemory(
                play_bias=rule_based_memory.play_bias,
                recent_patterns=polished_patterns[:5],  # 保留最多5条
                total_games=rule_based_memory.total_games,
                last_updated=rule_based_memory.last_updated,
            )
        except Exception:
            # 失败时回退到规则摘要
            return rule_based_memory

    def _build_polish_prompt(
        self, memory: PlayerMemory, stats: EpisodeStats
    ) -> str:
        """构建润色 prompt."""
        lines = [
            "请根据以下统计信息，生成2-3条简洁的改进建议：",
            "",
            "本局统计：",
            f"- 和了: {stats.wins}次",
            f"- 放铳: {stats.deal_ins}次",
            f"- 立直: {stats.riichi_count}次",
            f"- 立直后和了: {stats.riichi_win}次",
            f"- 立直后放铳: {stats.riichi_deal_in}次",
            "",
            f"当前风格: {memory.play_bias}",
            "",
            "请生成自然语言建议（每条建议一行，不要编号）：",
        ]
        return "\n".join(lines)

    def _parse_response(self, response: str) -> list[str]:
        """解析 LLM 响应."""
        lines = [
            line.strip() for line in response.strip().split("\n") if line.strip()
        ]
        return lines[:5]  # 最多取5条


def create_summarizer(
    use_llm: bool = False,
    client: CompletionClient | None = None,
) -> "EpisodeSummarizer | LLMSummarizer":
    """创建摘要器工厂.

    Args:
        use_llm: 是否使用 LLM 润色
        client: LLM 客户端（use_llm=True 时必需）

    Returns:
        EpisodeSummarizer 或 LLMSummarizer 实例
    """
    if use_llm and client is not None:
        return LLMSummarizer(client)
    from llm.agent.memory import EpisodeSummarizer
    return EpisodeSummarizer()
