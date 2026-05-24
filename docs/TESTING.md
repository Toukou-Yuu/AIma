# AIma 测试指南

## 概述

AIma 使用 pytest 作为测试框架，测试目录为 `tests/`。

## 运行测试

```bash
# 运行全量测试
pytest -q

# 运行特定测试
pytest tests/test_yakuman.py -v

# 跳过慢速测试
pytest -m "not slow"

# 运行 live API 测试（需要设置环境变量）
RUN_LIVE_LLM_TESTS=1 DEEPSEEK_API_KEY=xxx pytest -m live -v
```

## pytest markers

| Marker | 说明 | 用法 |
|--------|------|------|
| `ui` | 需要 textual/rich 库 | 缺库时自动跳过 |
| `live` | 需要 true API 调用 | 默认跳过，需 `RUN_LIVE_LLM_TESTS=1` |
| `slow` | 运行时间 >5s | CI 可跳过 |

## API Key 管理

**禁止硬编码 API Key**：

- ❌ 错误：`api_key="sk-xxx"` 直接写在代码中
- ✅ 正确：使用 `os.environ.get("DEEPSEEK_API_KEY")`

live API 测试模板：

```python
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_LLM_TESTS") != "1",
    reason="需要真实 API，设置 RUN_LIVE_LLM_TESTS=1",
)

def test_xxx():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("需设置 DEEPSEEK_API_KEY")
```

## 测试工具函数

`tests/llm_test_utils.py` 提供：

| 函数 | 用途 |
|------|------|
| `load_test_runtime_config()` | 加载运行时配置 |
| `load_test_seat_llm_configs()` | 加载座位配置 |
| `build_test_agent()` | 构造 PlayerAgent |

`tests/engine_helpers.py` 提供状态构造函数：

| 函数 | 用途 |
|------|------|
| `make_board()` | 构造指定手牌 |
| `make_meld()` | 构造副露对象 |
| `make_ron_board()` | 构造荣和状态 |

## UI 测试

UI 测试依赖 `rich` optional dependencies：

```bash
pip install .[rich]
pytest -m ui
```

未安装时自动跳过（`pytest.importorskip`）。

## PYTHONPATH

子进程测试需要显式设置：

```python
import os
import subprocess

env = os.environ.copy()
env["PYTHONPATH"] = "src"
subprocess.run(["python", "-m", "llm", ...], env=env)
```

## 测试风格

- 类名：`Test{FeatureName}`
- 方法名：`test_{scenario}_{expected}`
- 回归测试：文件头部注释说明 BUG 根因
- 使用 `Counter[Tile]` 构造牌形
- 异常测试使用 `pytest.raises(Exception, match="pattern")`

## 稳定性 Gate

dry-run 稳定性测试分两档：

|档位 | Seeds | 用途 | 命令 |
|------|-------|------|------|
| Fast | 10 | 日常开发、快速回归 | `AIMA_STABILITY_SEEDS=10 pytest -q tests/test_runner_dry_run_stability.py` |
| Full | 100 | 版本冻结、论文实验前验收 | `AIMA_STABILITY_SEEDS=100 pytest -q tests/test_runner_dry_run_stability.py -m slow` |

默认为 10 seeds（约 2-3 分钟）。正式验收前必须跑一次 100 seeds full gate。

失败时输出：seed、phase、reason、kernel_steps、player_steps、replay path。