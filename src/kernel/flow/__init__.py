"""流局相关：类型导出与判定函数。"""

from kernel.flow.model import FlowKind, FlowResult, TenpaiResult
from kernel.flow.settle import (
    settle_flow,
    settle_tenpai,
    compute_tenpai_result,
    should_continue_dealer,
    update_honba,
)
from kernel.flow.transitions import (
    check_flow_kind,
    check_nine_nine_declaration,
    is_exhausted_flow,
    is_four_kans_flow,
    is_four_riichi_flow,
    is_four_winds_flow,
    is_nine_nine_flow,
    is_three_ron_flow,
)

__all__ = [
    "FlowKind",
    "FlowResult",
    "TenpaiResult",
    "check_flow_kind",
    "check_nine_nine_declaration",
    "is_exhausted_flow",
    "is_four_kans_flow",
    "is_four_riichi_flow",
    "is_four_winds_flow",
    "is_nine_nine_flow",
    "is_three_ron_flow",
    "settle_flow",
    "settle_tenpai",
    "compute_tenpai_result",
    "should_continue_dealer",
    "update_honba",
]
