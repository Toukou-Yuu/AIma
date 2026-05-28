# v4.0 测试分层文档

## 测试分层

```bash
# 快速离线测试（默认）
PYTHONPATH=src pytest -q

# v4 核心测试
PYTHONPATH=src pytest -q tests/v4 tests/arena tests/agents tests/experiments tests/metrics tests/context tests/memory tests/prompts tests/models

# 端到端 contract 测试
PYTHONPATH=src pytest -q tests/v4/test_experiment_contract_e2e.py

# Live API 测试
RUN_LIVE_LLM_TESTS=1 DEEPSEEK_API_KEY=xxx PYTHONPATH=src pytest -q tests/test_llm_core_deepseek.py
```

---

## pytest markers

| Marker | 用途 |
|--------|------|
| ui | 需要 textual/rich UI库的测试 |
| live | 需要真实 API 调用 |
| slow | 超过5秒的测试 |

### 配置（pyproject.toml）

```toml
[tool.pytest.ini_options]
markers = [
    "ui: tests requiring textual/questionary/rich UI libraries",
    "live: tests requiring real API calls (skipped by default)",
    "slow: tests that take >5 seconds to run",
]
```

---

## 测试分类

### 单元测试

- kernel 规则逻辑
- context builder
- memory lifecycle
- prompt rendering

### Contract 测试

- artifact 格式契约
- SQLite index 契约
- memory 写入契约

### E2E 测试

- 完整实验链路验证
- aggregate → index → UI

### Live 测试

- 真实 LLM API 调用
- 需显式启用

---

## Skipped 测试说明

当前 9 个 skipped 测试均为设计意图：

| 测试 | Skip 原因 |
|------|-----------|
| test_no_ron_claimants_via_direct_call | 由上层测试覆盖 |
| test_legal_actions_hand_over | 由其他测试覆盖 |
| test_decide_with_session_audit_and_delay | 需 DEEPSEEK_API_KEY |
| test_decide_with_conversation_logger | 需 DEEPSEEK_API_KEY |
| test_polish_returns_memory | 需 DEEPSEEK_API_KEY |
| test_reliability_summary_has_total_decisions | 需预先aggregate数据 |
| test_llm_decisions_have_diagnostics | 需外部 LLM API |
| SQLite 测试（2个） | 需预先运行的实验数据 |

### 运行 live 测试

```bash
RUN_LIVE_LLM_TESTS=1 DEEPSEEK_API_KEY="sk-xxx" \
  PYTHONPATH=src pytest -q tests/test_llm_core_deepseek.py tests/test_llm_summarizer.py::TestPolishWithDeepSeek
```

---

## 测试性能

### 当前状态

- 总测试数：2455
- 运行时间：约6分钟
- E2E测试：function-scope（每次新建实验）

### v4.1 优化计划

将 E2E fixture 改为 module-scope：

```python
@pytest.fixture(scope="module")
def smoke_run_dir(tmp_path_factory):
    ...
```

预期效果：E2E测试时间显著下降。

---

## Coverage

```bash
PYTHONPATH=src pytest --cov=src --cov-report=html
```

- 要求：≥90%
- UI 目录不计入 coverage