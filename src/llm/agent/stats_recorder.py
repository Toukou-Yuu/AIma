"""StatsRecorder - 统计记录."""

from __future__ import annotations

from typing import TYPE_CHECKING

from llm.agent.context_store import ContextEvent
from llm.agent.services.action_descriptor import describe_action

if TYPE_CHECKING:
    from kernel.api.legal_actions import LegalAction
    from kernel.api.observation import Observation
    from llm.agent import Decision
    from llm.agent.context_store import ContextStore
    from llm.agent.episode_state import EpisodeState
    from llm.agent.stats import MatchStats


class StatsRecorder:
    """统计记录器.

    管理本局和本场统计数据的更新。
    """

    def __init__(
        self,
        state: EpisodeState,
        context_store: ContextStore,
    ):
        self._state = state
        self._context_store = context_store

    def record_win(self, win_tile: str) -> None:
        """记录和了."""
        self._state.episode_stats.wins += 1
        self._state.episode_stats.win_tiles.append(win_tile)
        if self._state.episode_stats.riichi_count > 0:
            self._state.episode_stats.riichi_win += 1

        self._state.match_stats.wins += 1
        if self._state.match_stats.riichi_count > 0:
            self._state.match_stats.riichi_wins += 1

    def record_deal_in(self, deal_in_tile: str) -> None:
        """记录放铳."""
        self._state.episode_stats.deal_ins += 1
        self._state.episode_stats.deal_in_tiles.append(deal_in_tile)
        if self._state.episode_stats.riichi_count > 0:
            self._state.episode_stats.riichi_deal_in += 1

        self._state.match_stats.deal_ins += 1
        if self._state.match_stats.riichi_count > 0:
            self._state.match_stats.riichi_deal_ins += 1

    def record_riichi(self) -> None:
        """记录立直宣言."""
        self._state.episode_stats.riichi_count += 1
        self._state.match_stats.riichi_count += 1

    def end_episode(self, points: int) -> None:
        """结束本局，更新统计."""
        self._state.episode_stats.total_points = points
        self._state.episode_stats.hands_played = 1
        self._state.match_stats.points += points
        self._state.match_stats.hands += 1

    def record_decision(
        self,
        decision: Decision,
        *,
        observation: Observation | None = None,
        legal_actions: tuple[LegalAction, ...] | None = None,
        phase: str | None = None,
    ) -> None:
        """记录决策到历史与结构化事实仓库。"""
        self._state.decision_history.append(decision)
        action = decision.action
        obs_phase = phase or (observation.phase.value if observation is not None else "")
        riichi_players: tuple[int, ...] = ()
        scores: tuple[int, ...] = ()
        last_discard: str | None = None
        last_discard_seat: int | None = None
        if observation is not None:
            riichi_players = tuple(i for i, flag in enumerate(observation.riichi_state) if flag)
            scores = tuple(observation.scores)
            last_discard = observation.last_discard.to_code() if observation.last_discard else None
            last_discard_seat = observation.last_discard_seat
        self._context_store.append_event(
            ContextEvent(
                turn_index=len(self._state.decision_history),
                phase=obs_phase,
                action_kind=action.kind.value,
                action_text=describe_action(action),
                why=decision.why,
                legal_action_count=len(legal_actions) if legal_actions is not None else 0,
                riichi_players=riichi_players,
                scores=scores,
                last_discard=last_discard,
                last_discard_seat=last_discard_seat,
            )
        )