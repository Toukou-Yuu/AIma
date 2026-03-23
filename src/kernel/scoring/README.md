# scoring

役、宝牌、符/番→点、荣和与自摸支付，以及 `HAND_OVER` 时 `TableSnapshot` 更新。里宝指示牌由 `DeadWall.ura_bases` 与已翻开表指示数目对齐，经 `ura_indicators_for_settlement` 在 `apply` 中传入结算。子集内 **平和**：门清四顺子 + 非役牌雀头、荣和须两面待；符为门清荣和 30 / 门清自摸 20（`win_shape.pinfu` + `compute_fu`）。具体规则以代码为准；与 `mahjong_rules/` 对照表可在实现时查阅。
