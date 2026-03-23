# wall 包约定

## 王牌 14 张切分

`split_wall` 将王牌区 `wall[122:136]` 切为：

- `DeadWall.rinshan`：前 **6** 张，岭上摸取顺序 `rinshan[0..5]`。
- 后 **8** 张：4 槽，每槽交错为 **（里宝指示牌、表宝指示牌）**，即  
  `ura_bases[0], indicators[0], ura_bases[1], indicators[1], …`  
  开局翻开 `indicators[0]` 为第一张表宝指示；开杠后依次翻开 `indicators[k]`。  
  **立直和了**结算时，与已翻开表指示同数目的里指示为 `ura_bases[0..k-1]`（见 `kernel.scoring.dora.ura_indicators_for_settlement`）。

## 岭上摸取顺序

由 `BoardState.rinshan_draw_index` 指向下一张待摸张，与 `live_draw_index` 独立。
