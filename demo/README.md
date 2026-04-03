# AIma Demo 牌谱

本文件夹包含用于演示和调试的预设牌谱。

## 文件说明

- `complex_game.json` - 复杂对局牌谱（4局）
  - 第1局：碰、吃、大明杠、荣和
  - 第2局：暗杠、加杠、自摸
  - 第3局：九连宝灯役满
  - 第4局：流局（荒牌）

- `run_demo.py` - 一键运行演示脚本

## 运行方式

### 方式1：使用脚本
```bash
python demo/run_demo.py
```

### 方式2：直接使用 CLI
```bash
# 回放牌谱
python -m llm --replay demo/complex_game.json --watch

# 调整速度
python -m llm --replay demo/complex_game.json --watch --watch-delay 0.5
```

## 自定义牌谱

可以编辑 `complex_game.json` 中的 `actions_wire` 来修改对局流程。

牌谱格式参考 `src/kernel/replay_json.py` 中的 `match_log_document`。
