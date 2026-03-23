# riichi 包

- **听牌**：`is_tenpai_default` 在门清下为七对听牌 **或** 存在某张和了牌使 `can_ron_default` 成立（与荣和形判对齐）；`is_tenpai_seven_pairs` 仍保留供子集测试。
- **一发**：`BoardState.ippatsu_eligible` 在立直宣言打牌后加入该席；任意吃 / 碰 / 大明杠鸣牌成功后清空全体候选（与常见友人桌「鸣牌后一发失效」一致）；荣和结算路径亦清空。
- **双立直**：`BoardState.double_riichi` 在该席本局河中此前无自家舍牌且宣言立直时记入，供点数模块识别役种。

本目录说明仅描述职责与约定，不写对局进度代号。
