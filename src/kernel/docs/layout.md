# kernel 目录结构说明

| 路径 | 职责 |
|------|------|
| `tiles/` | 牌种、单张牌数据模型；136 张牌组生成与洗牌（可复现种子）。 |
| `wall/` | 牌山切分：本墙与王牌（6 张岭上 + 4 槽里/表指示叠；见该包 ``README``）。 |
| `deal/` | 开局配牌、剩余本墙与首张表宝指示牌（与 ``wall`` 王牌顺序约定一致）。 |
| `play/` | 局内本墙自摸、打牌与河牌记录（与 ``BoardState`` 的轮次字段配合）。 |
| `call/` | 舍牌应答：荣和、吃碰大明杠与 pass 优先级（与 ``CALL_RESPONSE`` 配合）。 |
| `kan/` | 开杠后的岭上摸、翻表宝指示牌，以及暗杠/加杠的纯函数转移（与 ``BoardState.rinshan_draw_index`` 等字段配合）。 |
| `hand/` | 门内手牌多重集合、副露数据结构、张数守恒与副露形状校验（不含鸣牌可否与听牌）。 |
| `table/` | 场风、局序、亲席、本场、供托、四家点棒等场况快照（不含局流与状态机）。 |
| `engine/` | 对局阶段、`GameState`、统一 `apply` 入口。 |
| `riichi/` | 立直相关听牌等纯函数；宣言、供托与摸切约束由 `apply` + `play` / `kan` 接线。 |
| `win_shape/` | 标准四面子一雀头等和了形纯判定（与荣和/自摸共用）。 |
| `scoring/` | 役、宝牌计数、符/番→点、荣和与自摸支付、`HAND_OVER` 场况更新。 |
| `flow/` | 流局种类判定、听牌结算、与 `apply` 的 `FLOWN` 衔接。 |
| `match/` | 比赛终局、名次与最终点棒（与 `table.transitions` 协同）。 |
| `api/` | `legal_actions`、`observation`；`meld_candidates`（鸣牌/暗杠/加杠候选）。 |
| `event_log.py` | 结构化对局事件类型（每步 `apply` 可产出）。 |
| `replay.py` / `replay_json.py` | 动作序列回放；JSON wire 编解码。 |

非 Python 文件（如本说明）用于**索引与约定**，不写对局进度或内部里程碑代号。
