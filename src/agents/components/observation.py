"""ObservationBuilder - 观测信息构建组件.

职责：
- 从 DecisionContext 构建真实观测描述字符串
- 给 AgentPipeline diagnostics 和可选 prompt observation section 使用
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arena.policy import DecisionContext


class ObservationBuilder:
    """观测信息构建器.

    从 DecisionContext 提取信息，构建供 LLM 理解的观测描述。
    """

    def build(self, ctx: "DecisionContext") -> str:
        """构建观测描述.

        Args:
            ctx: 决策上下文

        Returns:
            观测描述字符串
        """
        obs = ctx.observation
        lines: list[str] = []
        lines.append(f"Seat: {ctx.seat}")
        lines.append(f"Phase: {ctx.phase}")
        lines.append(f"Dealer seat: {obs.dealer_seat}")
        lines.append(f"Turn seat: {obs.turn_seat}")
        lines.append(
            "Scores: "
            + ", ".join(f"seat{i}={score}" for i, score in enumerate(obs.scores))
        )
        lines.append(f"Honba: {obs.honba}")
        lines.append(f"Kyoutaku: {obs.kyoutaku}")

        if obs.hand is None:
            lines.append("Hand: (hidden)")
        else:
            tiles: list[str] = []
            for tile, count in sorted(
                obs.hand.items(),
                key=lambda kv: (kv[0].suit.value, kv[0].rank, kv[0].is_red),
            ):
                tiles.extend([tile.to_code()] * count)
            lines.append("Hand: " + (" ".join(tiles) if tiles else "(empty)"))

        if obs.dora_indicators:
            dora = " ".join(tile.to_code() for tile in obs.dora_indicators)
            lines.append(f"Dora indicators: {dora}")
        else:
            lines.append("Dora indicators: (none)")

        if obs.last_discard is not None and obs.last_discard_seat is not None:
            lines.append(
                f"Last discard: seat{obs.last_discard_seat} {obs.last_discard.to_code()}"
            )

        lines.append(f"Legal actions: {len(ctx.legal_actions)}")
        for index, action in enumerate(ctx.legal_actions[:12], start=1):
            lines.append(f"  {index}. {self._format_action(action)}")
        if len(ctx.legal_actions) > 12:
            lines.append(f"  ... and {len(ctx.legal_actions) - 12} more")

        return "\n".join(lines)

    @staticmethod
    def _format_action(action: object) -> str:
        """Format a LegalAction without importing prompt internals."""
        kind = getattr(getattr(action, "kind", None), "value", str(getattr(action, "kind", "")))
        tile = getattr(action, "tile", None)
        if tile is not None:
            return f"{kind} {tile.to_code()}"
        meld = getattr(action, "meld", None)
        if meld is not None:
            tiles = " ".join(tile.to_code() for tile in meld.tiles)
            return f"{kind} {tiles}"
        return str(kind)
