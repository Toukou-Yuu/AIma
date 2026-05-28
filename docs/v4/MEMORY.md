# v4.0 Memory 机制文档

## 概述

v4.0 Memory 实现了 **被动注入** 模式：系统在构建 prompt 时自动注入记忆内容，LLM 不主动调用 memory 工具。

---

## Memory 层次

| Layer | 范围 | 生命周期 | 用途 |
|-------|------|----------|------|
| hand | 当前局 | 局结束时清空 | 记录本局关键事件 |
| match | 当前对局 | 对局结束时清空 | 记录跨局摘要 |
| persistent | 长期 | 跨session持久化 | 记录长期模式（v4.2完善） |
| opponent | 对手特定 | 跨session持久化 | 记录对手行为模式（v4.2完善） |

---

## Memory 模式

### off（关闭）

不注入任何 memory 内容。

```yaml
memory:
  mode: "off"
```

### passive（被动注入）

在 prompt 构建时自动注入 memory 内容。

```yaml
memory:
  mode: "passive"
  layers: ["match"]
```

注入的 memory section 格式：

```
【历史记忆】
[match] Hand 3: seat1和牌(ron), seat0放铳, 12000点
[match] Hand 5: seat2立直成功, tsumo和牌, 8000点
```

---

## Memory 生命周期

### 写入时机

| 时机 | 写入Layer | 内容 |
|------|-----------|------|
| on_hand_end | match | 本局摘要（胜负、得分、立直情况） |
| on_match_end | persistent | 对局摘要（v4.2实现） |

### 清空时机

| 时机 | 清空Layer |
|------|-----------|
| on_hand_end | hand |
| on_match_end | match |

---

## v4.0 限制

### 当前支持

- ✅ passive 注入模式
- ✅ match layer 摘要写入
- ✅ in_memory 存储
- ✅ memory_snapshot.jsonl debug 输出

### 不支持（v4.1/v4.2计划）

- ❌ 检索式 memory reader（v4.2）
- ❌ LLM summary 生成（v4.2）
- ❌ opponent layer 行为建模（v4.2）
- ❌ persistent layer 跨实验持久化（v4.2）

---

## YAML 配置陷阱

**重要**：YAML 1.1 会把 `off` 解析为布尔 `False`。

```yaml
# 错误写法
memory:
  mode: off       # 解析为 False，触发ValidationError

# 正确写法
memory:
  mode: "off"     # 字符串 "off"
```

---

## Memory Ablation 实验

v4.2 推荐实验变量：

```yaml
# baseline: memory off
memory:
  mode: "off"

# treatment: memory passive
memory:
  mode: "passive"
  layers: ["match"]
```

观察指标：
- token usage 增加
- fallback rate 变化
- parse error rate
- 长期稳定性（跨局决策质量）