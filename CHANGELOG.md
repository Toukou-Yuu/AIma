# AIma CHANGELOG

## v4.0-freeze (2026-05-27)

### 新增功能
- 实验平台完整链路：`experiments.run` → artifact → aggregate → index → UI
- Prompt DSL与ContextBuilder统一上下文构建
- Memory passive injection生命周期闭环
- SQLite runtime index实时更新
- Debug artifact配置实现（save_prompts, save_debug_snapshots）
- EventSink protocol扩展（on_hand_end回调）

### 修复问题
- MatchRunner自然终局语义修正（completed vs truncated）
- 中途流局连庄不计入hand_count（九九种/四风连打/四杠/四立直）
- Artifact contract测试自包含（不依赖仓库runs目录）
- YAML布尔陷阱修复（mode: off → "off"）
- ContextEvent import路径清理
- autocompact实验性warning

### 文档更新
- docs/v4文档体系建立
- EXPERIMENTS.md配置示例修正

### 测试状态
- 2389 passed, 9 skipped
- Live DeepSeek API测试验证通过

---

## v3.1.3 (2026-05-23)

### 修复问题
- Kernel规则边界hardening
- Flow semantics澄清
- MatchRunner截断逻辑修正

---

## v3.1.2 (2026-05-24)

### 修复问题
- 立直判断时机修正
- 和牌判定边界修复
- Score计算准确性修正

---

## v3.1.1 (2026-05-21)

### 新增功能
- 规则审计机制
- GameState边界检查

---

## v3.1.0 (2026-05-14)

### 新增功能
- Kernel规则引擎重构
- MatchRunner统一对局流程
- Policy协议标准化

---

## v3.0.0 (2026-04-12)

### 新增功能
- Textual全屏TUI
- 动态观战界面
- 牌谱回放系统
- 角色管理模块