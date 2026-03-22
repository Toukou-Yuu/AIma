# wall 包约定

## 岭上摸取顺序

`split_wall` 将王牌区 `wall[122:136]` 切为：

- `DeadWall.rinshan`：前 10 张，下标 `0..9`。
- `DeadWall.indicators`：后 4 张，为表宝指示牌槽位。

开杠后的岭上摸牌顺序为：依次使用 `rinshan[0]`、`rinshan[1]`、…，由 `BoardState.rinshan_draw_index` 指向下一张待摸张。该游标与 `live_draw_index` 独立。
