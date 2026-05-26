"""GameEngine 门面：为上层提供稳定的 kernel API。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from arena.result import EngineStepResult
from kernel.api.legal_actions import LegalAction
from kernel.api.observation import Observation
from kernel.engine.actions import Action
from kernel.engine.apply import apply, ApplyOutcome
from kernel.engine.phase import GamePhase
from kernel.engine.state import GameState, initial_game_state
from kernel.table.model import initial_table_snapshot, MatchPreset

if TYPE_CHECKING:
    from experiments.schema import MatchSpec


class GameEngine:
    """kernel API 稳定门面，供 arena/match_runner 使用。

    方法直接转发 kernel API，不引入额外抽象层。
    GameState、Observation、LegalAction 直接复用 kernel 类型。
    """

    def new_match(self, spec: "MatchSpec | None", seed: int) -> GameState:
        """创建新对局，返回 PRE_DEAL 状态。

        Args:
            spec: 对局配置（包含 preset, max_hands, allow_negative, step_limit）
                  如为 None，使用默认半庄配置
            seed: 随机种子

        Returns:
            PRE_DEAL 阶段的 GameState
        """
        # 根据preset设置起配点和局数
        if spec is None:
            # 默认使用半庄配置
            max_hands = 8
            starting_points = 25000
            match_preset = MatchPreset.HANCHAN
        elif spec.preset == "tonpuu":
            # 东风战：4局，起配25000
            max_hands = 4
            starting_points = 25000
            match_preset = MatchPreset.TONPUSEN
        elif spec.preset == "hanchan":
            # 半庄：8局，起配25000
            max_hands = spec.max_hands or 8
            starting_points = 25000
            match_preset = MatchPreset.HANCHAN
        else:
            # custom：使用spec中的值
            max_hands = spec.max_hands or 8
            starting_points = 25000
            match_preset = MatchPreset.HANCHAN

        # 存储配置供后续使用（通过state传递或单独存储）
        # 当前kernel不支持max_hands，需要在match_runner层面处理
        # 这里我们至少正确设置starting_points

        table = initial_table_snapshot(
            dealer_seat=0,
            starting_points=starting_points,
            match_preset=match_preset,
        )
        return initial_game_state(table)

    def legal_actions(
        self,
        state: GameState,
        seat: int
    ) -> tuple[LegalAction, ...]:
        """转发 kernel.api.legal_actions。

        Args:
            state: 当前局面
            seat: 执行者座位

        Returns:
            合法动作列表
        """
        from kernel.api.legal_actions import legal_actions
        return legal_actions(state, seat)

    def observe(
        self,
        state: GameState,
        seat: int,
        mode: Literal["human", "debug"] = "human"
    ) -> Observation:
        """转发 kernel.api.observation。

        Args:
            state: 当前局面
            seat: 观测者座位
            mode: 观测模式

        Returns:
            观测信息
        """
        from kernel.api.observation import observation
        return observation(state, seat, mode)

    def step(self, state: GameState, action: Action) -> EngineStepResult:
        """推进状态，包装 ApplyOutcome。

        Args:
            state: 当前局面
            action: 执行动作

        Returns:
            EngineStepResult（含 new_state、events）
        """
        outcome: ApplyOutcome = apply(state, action)
        return EngineStepResult(
            new_state=outcome.new_state,
            events=outcome.events,
            drained_pass_calls=outcome.drained_pass_calls,
        )

    def is_terminal(self, state: GameState) -> bool:
        """是否终局。

        Args:
            state: 当前局面

        Returns:
            True 如果 phase == MATCH_END
        """
        return state.phase == GamePhase.MATCH_END

    def phase(self, state: GameState) -> str:
        """当前阶段。

        Args:
            state: 当前局面

        Returns:
            phase.value 字符串
        """
        return state.phase.value