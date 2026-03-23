# `kernel.play`

本墙自摸、打牌与河牌记录；`model` 中含 `TurnPhase`、`RiverEntry`、`CallResolution`（舍牌应答窗口快照，由 `kernel.call` 在 `CALL_RESPONSE` 时读写）。与 `deal` 的 `BoardState` 配合。和了形判与点数在 `kernel.call` / `kernel.scoring`。
