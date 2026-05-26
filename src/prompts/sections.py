"""Section renderer helpers for prompt DSL.

每个 section renderer 是一个函数，接收渲染上下文和配置，返回渲染后的字符串。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from arena.policy import DecisionContext
    from kernel.api import LegalAction
    from prompts.schema import PromptSectionSpec


# Type alias for section renderer functions
SectionRenderer = Callable[
    ["DecisionContext", "PromptSectionSpec"],
    str,
]


def render_system_prompt(ctx: "DecisionContext", spec: "PromptSectionSpec") -> str:
    """Render system prompt section.

    Args:
        ctx: Decision context
        spec: Section specification with variant and options

    Returns:
        System prompt text
    """
    variant = spec.variant or "default"
    options = spec.options

    if variant == "riichi":
        return _render_riichi_system_prompt(options)
    if variant == "default":
        return _render_default_system_prompt(options)
    # Fallback for unknown variants
    return _render_default_system_prompt(options)


def _render_default_system_prompt(options: dict[str, Any]) -> str:
    """Render default system prompt."""
    role = options.get("role", "Mahjong player")
    return f"You are a {role}."


def _render_riichi_system_prompt(options: dict[str, Any]) -> str:
    """Render riichi mahjong system prompt."""
    role = options.get("role", "Japanese Riichi Mahjong player")
    return f"""You are an expert {role}.

CRITICAL: You MUST respond with ONLY a valid JSON object. No explanations before or after. No markdown code blocks. No extra text.

Your response must be parseable by JSON.parse() directly.

Example valid response:
{{"action": "DISCARD 1m", "why": "Isolated tile, improves hand efficiency"}}

Example INVALID responses (DO NOT DO THIS):
- "Let me think..." (explanation before JSON)
- ```json{{"action":...}}``` (markdown code block)
- {{'action': 'DISCARD 1m'}} (single quotes, not valid JSON)

Your task: Analyze the game state and choose the best action from legal_actions."""


def render_game_state(ctx: "DecisionContext", spec: "PromptSectionSpec") -> str:
    """Render game state section.

    Args:
        ctx: Decision context
        spec: Section specification

    Returns:
        Game state description
    """
    lines = ["## Game State"]
    lines.append(f"- Phase: {ctx.phase}")
    lines.append(f"- Your seat: {ctx.seat}")
    lines.append(f"- Dealer seat: {ctx.state.table.dealer_seat}")
    lines.append(f"- Hand index: {ctx.hand_index}")
    lines.append(f"- Step index: {ctx.step_index}")

    # Scores
    scores = ctx.state.table.scores
    lines.append("- Scores:")
    for i, score in enumerate(scores):
        dealer_marker = " (dealer)" if i == ctx.state.table.dealer_seat else ""
        lines.append(f"  - Seat {i}{dealer_marker}: {score}")

    # Honba and kyoutaku
    lines.append(f"- Honba: {ctx.state.table.honba}")
    lines.append(f"- Kyoutaku (riichi sticks): {ctx.state.table.kyoutaku}")

    return "\n".join(lines)


def render_hand(ctx: "DecisionContext", spec: "PromptSectionSpec") -> str:
    """Render player's hand section.

    Args:
        ctx: Decision context
        spec: Section specification

    Returns:
        Hand description
    """
    obs = ctx.observation
    if obs.hand is None:
        return "## Your Hand\n(no tiles)"

    lines = ["## Your Hand"]

    # Sort and group tiles
    from collections import Counter

    from kernel.tiles.model import Tile

    hand: Counter[Tile] = obs.hand
    tile_strs = []
    for tile in sorted(hand.elements(), key=lambda t: (t.suit.value, t.rank)):
        tile_str = tile.to_code()
        tile_strs.append(tile_str)

    if tile_strs:
        lines.append(" ".join(tile_strs))
    else:
        lines.append("(empty)")

    # Melds
    if obs.melds:
        lines.append("\nMelds:")
        for i, meld in enumerate(obs.melds):
            lines.append(f"  {i + 1}. {meld.kind.value}: {' '.join(t.to_code() for t in meld.tiles)}")

    return "\n".join(lines)


def render_river(ctx: "DecisionContext", spec: "PromptSectionSpec") -> str:
    """Render river (discards) section.

    Args:
        ctx: Decision context
        spec: Section specification with max_items

    Returns:
        River description
    """
    obs = ctx.observation
    river = obs.river

    max_items = spec.max_items
    if max_items is not None and len(river) > max_items:
        river = river[-max_items:]

    lines = ["## River (Discards)"]

    if not river:
        lines.append("(empty)")
        return "\n".join(lines)

    # Group by seat
    from collections import defaultdict

    by_seat: dict[int, list[str]] = defaultdict(list)
    for entry in river:
        tile_str = entry.tile.to_code()
        if entry.is_riichi:
            tile_str += "*"
        if entry.is_tsumogiri:
            tile_str += "'"
        by_seat[entry.seat].append(tile_str)

    for seat in sorted(by_seat.keys()):
        lines.append(f"Seat {seat}: {' '.join(by_seat[seat])}")

    return "\n".join(lines)


def render_dora(ctx: "DecisionContext", spec: "PromptSectionSpec") -> str:
    """Render dora indicators section.

    Args:
        ctx: Decision context
        spec: Section specification

    Returns:
        Dora indicators description
    """
    obs = ctx.observation

    lines = ["## Dora Indicators"]
    if obs.dora_indicators:
        dora_strs = [t.to_code() for t in obs.dora_indicators]
        lines.append(" ".join(dora_strs))
    else:
        lines.append("(none revealed)")

    if obs.ura_indicators:
        lines.append("\nUra-dora (if you win with riichi):")
        ura_strs = [t.to_code() for t in obs.ura_indicators]
        lines.append(" ".join(ura_strs))

    return "\n".join(lines)


def render_riichi_state(ctx: "DecisionContext", spec: "PromptSectionSpec") -> str:
    """Render riichi state section.

    Args:
        ctx: Decision context
        spec: Section specification

    Returns:
        Riichi state description
    """
    obs = ctx.observation
    riichi = obs.riichi_state

    lines = ["## Riichi State"]
    for seat, is_riichi in enumerate(riichi):
        status = "RIICHI" if is_riichi else "not riichi"
        lines.append(f"- Seat {seat}: {status}")

    return "\n".join(lines)


def render_legal_actions(ctx: "DecisionContext", spec: "PromptSectionSpec") -> str:
    """Render legal actions section.

    Args:
        ctx: Decision context
        spec: Section specification with max_items

    Returns:
        Legal actions description
    """
    actions = ctx.legal_actions

    max_items = spec.max_items
    if max_items is not None and len(actions) > max_items:
        actions = actions[:max_items]

    lines = ["## Legal Actions"]
    lines.append(f"Total: {len(ctx.legal_actions)} available")

    for i, action in enumerate(actions):
        action_str = _format_action(action)
        lines.append(f"{i + 1}. {action_str}")

    if max_items is not None and len(ctx.legal_actions) > max_items:
        lines.append(f"... and {len(ctx.legal_actions) - max_items} more")

    return "\n".join(lines)


def _format_action(action: "LegalAction") -> str:
    """Format a legal action for display.

    Args:
        action: The legal action to format

    Returns:
        Formatted action string
    """
    kind = action.kind.value.upper()

    if action.tile is not None:
        return f"{kind} {action.tile.to_code()}"
    if action.meld is not None:
        tiles_str = " ".join(t.to_code() for t in action.meld.tiles)
        return f"{kind} {tiles_str}"
    return kind


def render_memory(ctx: "DecisionContext", spec: "PromptSectionSpec") -> str:
    """Render memory section.

    Args:
        ctx: Decision context
        spec: Section specification with source for memory content

    Returns:
        Memory description (stub for now)
    """
    # Memory integration will be implemented in Phase 4
    # For now, return empty if no source data
    source = spec.source
    if source is None:
        return ""

    options = spec.options
    content = options.get("content", "")

    if not content:
        return ""

    lines = ["## Memory"]
    lines.append(content)
    return "\n".join(lines)


def render_output_format(ctx: "DecisionContext", spec: "PromptSectionSpec") -> str:
    """Render output format instructions section.

    Args:
        ctx: Decision context
        spec: Section specification with variant

    Returns:
        Output format instructions
    """
    variant = spec.variant or "json_action"

    if variant == "json_action":
        return _render_json_action_format()
    if variant == "natural_action":
        return _render_natural_action_format()
    return _render_json_action_format()


def _render_json_action_format() -> str:
    """Render JSON action output format instructions."""
    return """## Output Format

CRITICAL: Respond with ONLY a JSON object. No markdown. No explanations.

Valid response example:
{"action": "DISCARD 1m", "why": "Isolated tile"}

INVALID responses (will cause parse failure):
- ```json{"action":...}```
- "I think..." before the JSON
- Any text after the JSON

Action formats:
- DISCARD <tile>: Discard a tile (e.g., DISCARD 1m, DISCARD 5p, DISCARD 9s)
- DRAW: Draw from wall
- PASS_CALL: Pass on chi/pon/kan/ron opportunity
- OPEN_MELD <tiles>: Call chi/pon/kan (e.g., OPEN_MELD 1m2m3m)
- ANKAN <tiles>: Concealed kan (e.g., ANKAN 1m1m1m1m)
- TSUMO: Self-draw win
- RON: Call win on discard

Copy an action EXACTLY from legal_actions list above. Do not invent actions."""


def _render_natural_action_format() -> str:
    """Render natural action output format instructions."""
    return """## Output Format

Respond with a natural language description of your action:
- State the action you want to take
- Briefly explain your reasoning"""


# Registry of section renderers
SECTION_RENDERERS: dict[str, SectionRenderer] = {
    "system_prompt": render_system_prompt,
    "game_state": render_game_state,
    "hand": render_hand,
    "river": render_river,
    "dora": render_dora,
    "riichi_state": render_riichi_state,
    "legal_actions": render_legal_actions,
    "memory": render_memory,
    "output_format": render_output_format,
}


def get_renderer(name: str) -> SectionRenderer | None:
    """Get a section renderer by name.

    Args:
        name: Renderer name

    Returns:
        Section renderer function, or None if not found
    """
    return SECTION_RENDERERS.get(name)


def estimate_tokens(text: str) -> int:
    """Estimate token count for text.

    Uses a simple heuristic: ~4 characters per token on average for mixed text.

    Args:
        text: Text to estimate

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    # Simple heuristic: ~4 characters per token
    return len(text) // 4 + 1