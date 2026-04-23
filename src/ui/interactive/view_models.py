"""View-model builders for Textual screens."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from rich.text import Text

from ui.interactive.data import SEAT_LABELS, ModelSummary

PlayerOption = tuple[str, str]


@dataclass(frozen=True, slots=True)
class MatchSetupDraft:
    """Current MatchSetupScreen form state."""

    selected_player_ids: tuple[str, str, str, str]
    seed: str
    max_hands: str
    watch: bool
    delay: str


def selected_players_from_ids(player_ids: Sequence[str]) -> list[dict[str, Any]]:
    """Build runner player payloads from selected profile ids."""
    return [{"id": player_id, "seat": seat} for seat, player_id in enumerate(player_ids)]


def player_display_name(player_id: str, player_options: Sequence[PlayerOption]) -> str:
    """Resolve a player id to the label shown in setup UI."""
    if player_id == "default":
        return "默认 AI (dry-run)"
    for label, value in player_options:
        if value == player_id:
            return label
    return player_id


def build_match_setup_rows(
    draft: MatchSetupDraft,
    *,
    player_options: Sequence[PlayerOption],
    model_summary: ModelSummary,
) -> list[tuple[str, str | Text]]:
    """Build the match setup summary rows from form state and model bindings."""
    rows: list[tuple[str, str | Text]] = [
        ("随机种子", "随机" if draft.seed == "0" else draft.seed),
        ("目标局数", draft.max_hands),
        ("观战模式", "实时观战" if draft.watch else "后台运行"),
    ]
    if draft.watch:
        rows.append(("观战延迟", f"{draft.delay} 秒"))

    rows.extend(
        _build_seat_model_rows(
            selected_players_from_ids(draft.selected_player_ids),
            player_options=player_options,
            model_summary=model_summary,
        )
    )
    return rows


def _build_seat_model_rows(
    players: list[dict[str, Any]],
    *,
    player_options: Sequence[PlayerOption],
    model_summary: ModelSummary,
) -> list[tuple[str, Text]]:
    bindings = {binding.seat: binding for binding in model_summary.seat_bindings}
    rows: list[tuple[str, Text]] = []
    for player in players:
        seat = int(player["seat"])
        player_id = str(player["id"])
        name = player_display_name(player_id, player_options)
        if player_id == "default":
            rows.append((SEAT_LABELS[seat], Text(f"{name} -> dry-run", style="dim")))
            continue

        binding = bindings.get(seat)
        if binding is None:
            rows.append((SEAT_LABELS[seat], Text(f"{name} -> 未绑定 LLM", style="red")))
            continue

        rows.append(
            (
                SEAT_LABELS[seat],
                Text(
                    (
                        f"{name} -> {binding.profile_name} · "
                        f"{binding.model} · {binding.connection_label}"
                    ),
                    style=binding.connection_style,
                ),
            )
        )
    return rows
