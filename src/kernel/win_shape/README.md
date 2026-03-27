# win_shape 包

- **标准形**：`can_win_standard_form(concealed, melds, win_tile)`，门内计数含和了牌；赤五与通常五映射到同一索引槽参与顺子/刻子分解。
- **门清分解**：`decompose.py` 提供 vec34 上「4 面子 + 1 雀头」枚举与 `menzen_peikou_level`（一杯口／二杯口）。
- **七对子**：仍在 `kernel.call.win.can_ron_seven_pairs`；统一荣和入口见 `kernel.call.win.can_ron_default`。

本目录说明仅描述职责，不写对局进度代号。
