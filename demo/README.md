# AIma Demo 演示

本文件夹包含用于演示的预设牌谱。

## 文件说明

- `complex_game.json` - 完整对局牌谱（约 1200 个动作）
- `run_demo.py` - 一键运行回放脚本

## 运行方式

### 方式1：使用脚本（推荐）
```bash
python demo/run_demo.py
```

### 方式2：直接使用 CLI
```bash
python -m llm --replay demo/complex_game.json --watch

# 调整播放速度
python -m llm --replay demo/complex_game.json --watch --watch-delay 0.5
```

## 牌谱说明

`complex_game.json` 是一个完整的半庄对局，包含：
- 东场 + 南场（多局）
- 包含多种鸣牌（碰、吃、杠）
- 包含立直、荣和、自摸等场景
- 包含宝牌、赤宝牌显示

## 生成新牌谱

如需生成新的牌谱：
```bash
python -c "
import json, sys
sys.path.insert(0, 'src')
from llm.runner import run_llm_match

rr = run_llm_match(seed=42, max_player_steps=1000, dry_run=True)
doc = rr.as_match_log()

with open('demo/complex_game.json', 'w') as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)
print(f'Saved with {len(doc[\"actions\"])} actions')
"
```
