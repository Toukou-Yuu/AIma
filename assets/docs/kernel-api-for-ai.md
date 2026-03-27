# AIma 麻将内核：对外接口说明（供 AI / 编排层使用）

本文面向**内核之外的编排程序**（例如多 LLM 牌手、终端、测试脚本），说明如何**观测局面**、**枚举合法动作**、**构造 `Action` 并调用 `apply`**。包名以可编辑安装为准：`pip install -e ".[dev]"` 后，导入前缀一般为 `kernel.*`（`PYTHONPATH=src` 或 `pyproject.toml` 中 `pythonpath` 已配置）。

---

## 1. 推荐集成方式（最小闭环）

1. **初始化**：`from kernel.engine.state import initial_game_state` → `state = initial_game_state()`。
2. **开局**：构造 136 张标准牌山（`kernel.tiles.deck.build_deck` + `shuffle_deck(..., seed=...)`），调用
  `apply(state, Action(kind=ActionKind.BEGIN_ROUND, wall=tuple(wall)))`。
3. **循环**：
  - 对每个需要决策的 seat：`legal_actions(state, seat)`；
  - 将选中的意图转为 `Action`（字段与 `ActionKind` 一致）；
  - `outcome = apply(state, action)`，`state = outcome.new_state`；
  - 可选：收集 `outcome.events` 写入日志。
4. **局末**：
  - `state.phase == HAND_OVER` 或 `FLOWN` 时，用 `NOOP` + 下一局 `wall` 推进（见 §5）；
  - `state.phase == MATCH_END` 时**停止调用 `apply`**。

---

## 2. 观测：`observation(state, seat, mode)`

**模块**：`kernel.api.observation`  

```python
def observation(
    state: GameState,
    seat: int,
    mode: Literal["human", "debug"] = "human",
) -> Observation
```

- `seat`：必须为 `0..3`，否则 `ValueError`。
- `mode`：
  - `human`（正式对局推荐）：返回**该 seat 可见**的信息。当前实现中自家手牌完整；河、宝牌指示、场况、立直状态等公共信息一致。**注意**：若未来加入「他家手牌隐藏」的细化，仍以本函数实现为准。
  - `debug`：除人类信息外，还提供 `wall_remaining`、`dead_wall`（王牌相关拼接）等调试字段；**禁止**作为公平对局的选手通道。

### 2.1 `Observation` 字段说明


| 字段                                   | 类型                          | 含义                                                              |
| ------------------------------------ | --------------------------- | --------------------------------------------------------------- |
| `seat`                               | `int`                       | 观测者座位                                                           |
| `hand`                               | `Counter[Tile] | None`      | 该席手牌（`board` 为 `None` 时可能为空）                                    |
| `melds`                              | `tuple[Meld, ...]`          | 该席副露                                                            |
| `river`                              | `tuple[RiverEntry, ...]`    | 全场河牌时间序；`RiverEntry` 含 `tile`、`seat`、`is_tsumogiri`、`is_riichi` |
| `dora_indicators`                    | `tuple[Tile, ...]`          | 已翻开的表宝指示牌序列                                                     |
| `ura_indicators`                     | `tuple[Tile, ...] | None`   | 里宝：在 `debug` 下可见；在 `human` 下若该席已立直，当前实现会暴露里宝基底（实现细节以源码为准）       |
| `riichi_state`                       | `tuple[bool, ...]`          | 四家是否已立直                                                         |
| `scores`                             | `tuple[int, int, int, int]` | 点棒                                                              |
| `honba`                              | `int`                       | 本场数                                                             |
| `kyoutaku`                           | `int`                       | 供托（累计点数，非根数）                                                    |
| `turn_seat`                          | `int`                       | 当前行动席（无 `board` 时回退为观测席）                                        |
| `last_discard` / `last_discard_seat` | 可选                          | 河尾舍牌与打牌者                                                        |
| `wall_remaining`                     | `int | None`                | 仅 `debug`：本墙剩余张数                                                |
| `dead_wall`                          | `tuple[Tile, ...] | None`   | 仅 `debug`：王牌相关拼接视图                                              |


---

## 3. 合法动作：`legal_actions(state, seat)`

**模块**：`kernel.api.legal_actions`  

```python
def legal_actions(state: GameState, seat: int) -> tuple[LegalAction, ...]
```

- `seat`：`0..3`，否则 `ValueError`。
- **返回值**：当前该席在规则下可执行的 `LegalAction` 列表；可能为空元组。

### 3.1 `LegalAction` 与 `Action` 的对应关系

`LegalAction` 是**便于枚举**的视图；提交引擎时必须转为 `Action`（见 `llm.action_build` 或自写映射）：


| `LegalAction.kind` | 构造 `Action` 时的要点 |
| ------------------ | ------------------- |
| `DRAW` | `Action(kind=DRAW, seat=seat)`（`seat` 须为 `current_seat`） |
| `DISCARD` | 必须带 `tile`；若 `declare_riichi=True`，同步设置 `Action.declare_riichi=True` |
| `TSUMO` | `Action(kind=TSUMO, seat=seat)`；可附带 `tile`（与盘面一致） |
| `PASS_CALL` | `Action(kind=PASS_CALL, seat=seat)` |
| `RON` | `Action(kind=RON, seat=seat)`（荣和牌以 `CallResolution` 上下文为准） |
| `OPEN_MELD` | 必须带 `meld: Meld`（吃 / 碰 / 大明杠 之一；由 `legal_actions` 枚举，与 `kernel.api.meld_candidates.enumerate_call_response_open_melds` 一致） |
| `ANKAN` | 必须带 `meld`（暗杠；见 `enumerate_ankan_melds`） |
| `SHANKUMINKAN` | 必须带 `meld`（加杠；见 `enumerate_shankuminkan_melds`） |
| `NOOP` | `Action(kind=NOOP, seat=seat)`；局间推进时常需同时传 `wall`（见 §5） |


副露与杠的**候选枚举**实现于 `kernel.api.meld_candidates`，由 `legal_actions` 在 `CALL_RESPONSE` / `MUST_DISCARD` 中调用；若上层自造 `Meld`，仍须以 `apply` 是否抛出 `IllegalActionError` 为准。

### 3.2 各 `GamePhase` 下 `legal_actions` 行为摘要


| `state.phase`                       | 行为                                                            |
| ----------------------------------- | ------------------------------------------------------------- |
| `PRE_DEAL`                          | 返回 `()`；**不枚举** `BEGIN_ROUND`（由主机/裁判提供牌山并直接 `apply`）          |
| `IN_ROUND`                          | 依 `turn_phase` 返回 `DRAW` / `DISCARD`（含立直变种）/ 应答动作 / `TSUMO` 等 |
| `HAND_OVER` / `FLOWN` / `MATCH_END` | 对任意 seat 返回 `(LegalAction(kind=NOOP, seat=seat),)`            |


**注意**：

- `HAND_OVER` / `FLOWN` 的 `NOOP` 在 `apply` 里常需附带 `wall`（下一局牌山），见 §5；`legal_actions` **不会**携带 `wall`，需编排层自行拼接。
- `MATCH_END`：`legal_actions` 仍返回 `NOOP`，但当前 `apply` **未实现**终局阶段的转移，对 `MATCH_END` 调用 `apply` 会抛 `IllegalActionError`。编排层应在检测到 `state.phase == MATCH_END` 后**停止**再调用 `apply`（可将 `NOOP` 视为占位，勿当真提交）。

---

## 4. 推进局面：`apply` 与错误处理

**模块**：`kernel.engine.apply`  

```python
def apply(state: GameState, action: Action) -> ApplyOutcome
```

- **成功**：`ApplyOutcome.new_state` 为不可变新状态；`ApplyOutcome.events` 为本步事件元组。
- **失败**：抛出 `IllegalActionError`（`ValueError` 系）。编排层应记录日志、让模型重选或判负（策略由上层定）。

**不要**直接 `dataclasses.replace` 修改 `GameState` / `BoardState` 来「走棋」。

---

## 5. 局间 `NOOP` 与 `wall`（易错点）

当 `state.phase` 为 `HAND_OVER` 或 `FLOWN` 时，调用：

```python
apply(state, Action(kind=ActionKind.NOOP, wall=next_wall_tuple))
```

- `next_wall_tuple`：长度 136、且与 `build_deck()` 同多重集合的标准牌山。
- 若省略 `wall` 或非法牌山：`IllegalActionError`。

`MATCH_END` 之后：**不应再调用 `apply`**（当前实现会抛 `IllegalActionError`）。

---

## 6. 牌山与随机性

```python
from kernel.tiles.deck import build_deck, shuffle_deck

wall = tuple(shuffle_deck(build_deck(), seed=42))
```

- 相同 `seed` → 相同排列，便于复现与测试。

---

## 7. 辅助 API：回放与事件


| 符号 | 模块 | 用途 |
| ---- | ---- | ---- |
| `replay_from_actions` | `kernel.replay` | 给定 `list[Action]` 串行 `apply`，返回终态与每步 `ApplyOutcome` |
| `action_to_wire` / `wire_to_action` | `kernel.replay_json` | `Action` 与可 JSON 序列化的 wire 互转，供牌谱落盘与 `--replay` |
| `EventLog` / `GameEvent` 子类 | `kernel.event_log` | 事件类型定义；编排层可将 `outcome.events` 扁平化归档 |

`replay_from_event_log` 等函数侧重**日志与动作序列一致性**的验证，详见 `kernel.replay` 文档字符串。

---

## 8. 场况与配置

- **场况默认值**：`kernel.table.model.initial_table_snapshot()`（起点数、立直棒点数等可与 `kernel.config.DEFAULT_CONFIG` 对齐）。
- **规则条文**：`mahjong_rules/Mahjong_Soul.md`（版本以文件为准）；与实现不一致时以 **`apply` 行为**为准。
- **役种对照**：§12 与 `kernel.scoring.yaku.non_dora_yaku_han_and_labels`（及结算路径）对齐；§12.2 列为友人桌常见但**尚未实现**的番种。

---

## 9. AI 工程建议（简要）

1. **正式对局**只使用 `observation(..., mode="human")`；`debug` 仅用于开发/观战。
2. 模型输出先映射为结构化 `Action`，再 `apply`；**切勿**解析自然语言直接改状态。
3. 鸣牌与杠以 `legal_actions` 枚举为准；扩展新动作类型时仍应经 `apply` 校验。
4. 超时、重试、多 seat 并行**不属于**内核职责；在编排层实现并保证对 `apply` 的调用单线程顺序一致即可（同一 `state` 不并发 `apply`）。

---

## 10. 相关类型速查（import）

```python
from kernel.engine.state import GameState, initial_game_state
from kernel.engine.phase import GamePhase
from kernel.engine.actions import Action, ActionKind
from kernel.engine.apply import apply, ApplyOutcome, IllegalActionError
from kernel.api import legal_actions, observation, LegalAction, Observation
from kernel.tiles.deck import build_deck, shuffle_deck
```

更完整的内部类型（`BoardState`、`TableSnapshot`、`Meld`、`Tile` 等）按需在子模块中导入即可。