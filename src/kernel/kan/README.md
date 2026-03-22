# kan 包

杠相关的纯函数转移：**岭上摸**、**杠后翻表宝指示牌**、**暗杠**、**加杠（升杠）**。

## 岭上与指示牌

- 岭上顺序见 `wall/README.md`：`dead_wall.rinshan[rinshan_draw_index]`。
- 开局已翻开 `revealed_indicators[0]`（与 `deal` 中首张表宝一致）。第 *k* 次开杠（本实现中每杠一次）在岭摸的同时追加 `dead_wall.indicators[k]` 到 `revealed_indicators`（*k* 为追加前已揭示枚数，与 `len(revealed_indicators)` 对齐）。

## 手数与阶段

杠并岭摸之后，当前家为 **门内+副露共 15 张**、`last_draw_was_rinshan=True`，须再打出一张后才会进入他家应答等后续流程。打出后舍牌者若含 **四张面子（杠）**，在 ``CALL_RESPONSE`` 下合计可为 **14**（门内+副露），与吃碰后 **13** 并列校验；详见 ``deal.model.validate_board_state``。

## 与 `engine.apply` 的对应

- `ActionKind.ANKAN` / `SHANKUMINKAN`：在 `MUST_DISCARD` 且非「岭上待打」时提交对应 `Meld`。
- 大明杠仍通过 `OPEN_MELD` + `MeldKind.DAIMINKAN`，由 `call` 层接岭摸链。

## 累计杠 / 岭摸次数

- `completed_kan_rinshan_count(board)` 与 `board.rinshan_draw_index` 相同，可作 **四杠流局**（K11）等判定的输入。
- 当前实现里每杠翻一枚表宝指示牌，与 `INDICATOR_COUNT` 耦合；在指示牌用尽后无法继续完成「杠+岭摸」链，与实体桌「仅四枚表宝」一致。

## 分期功能

- **抢杠荣和**：须在加杠/大明杠与岭摸之间插入应答窗，当前未接（见 `call` 与引擎分期）。
