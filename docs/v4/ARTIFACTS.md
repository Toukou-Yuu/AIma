# v4.0 Artifact 格式文档

## Artifact 文件格式

### summary.json

```json
{
  "schema_version": 1,
  "match_id": "uuid",
  "job_id": "uuid",
  "seed": 42,
  "step_count": 150,
  "hand_count": 8,
  "completed_hands": 8,
  "stopped_reason": "MATCH_END",
  "outcome": "completed",
  "final_phase": "match_end",
  "truncated_after_completed_hand": false,
  "final_points": [35000, 28000, 22000, 15000],
  "point_delta": [10000, 3000, -3000, -10000],
  "starting_points": [25000, 25000, 25000, 25000],
  "started_at": "2026-05-27T00:00:00+00:00",
  "finished_at": "2026-05-27T00:00:12+00:00",
  "duration_ms": 12345
}
```

`max_hands` 是实验安全截断上限，表示完成 N 局后停止。runner 会在局结束后
执行一次 `NEXT_ROUND` 让 kernel 判断是否自然终局；如果未自然终局但达到
`max_hands`，则 `outcome="truncated"`、`stopped_reason="max_hands_reached"`、
`truncated_after_completed_hand=true`。此时 `final_phase` 可能是下一局的
`in_round` 初始状态，这是预期 artifact 语义。

### replay.json

```json
{
  "format_version": 2,
  "seed": 42,
  "stopped_reason": "MATCH_END",
  "steps": [
    {
      "step_index": 0,
      "phase": "DRAW",
      "events": [...]
    }
  ],
  "actions": [
    {
      "kind": "draw_tile",
      "seat": 0,
      "tile": "1m"
    }
  ],
  "final_phase": "MATCH_END"
}
```

### events.jsonl

每行一个事件记录：

```json
{"schema_version": 1, "match_id": "...", "job_id": "...", "step_index": 0, "hand_index": 0, "seed": 42, "event": {"kind": "draw_tile", "seat": 0, "tile": "1m"}}
{"schema_version": 1, "match_id": "...", "job_id": "...", "step_index": 1, "hand_index": 0, "seed": 42, "event": {"kind": "discard_tile", "seat": 0, "tile": "9m", "riichi": false}}
```

### decisions.jsonl

每行一个决策记录：

```json
{"schema_version": 1, "match_id": "...", "job_id": "...", "step_index": 0, "seat": 0, "action": {"kind": "discard", "tile": "9m"}, "parse_status": "ok", "fallback_used": false, "latency_ms": 150.0, "diagnostics": {"prompt_tokens": 2000, "completion_tokens": 100, "memory_injected_tokens": 0}}
```

---

## 事件类型

| Kind | 字段 |
|------|------|
| draw_tile | seat, tile |
| discard_tile | seat, tile, riichi, tsumogiri |
| call_tile | seat, meld_type, tiles |
| ron | seat, target_seat, tile, han, fu |
| tsumo | seat, tile, han, fu, rinshan |
| hand_over | winners, payments, tenpai_seats |
| match_end | final_points, ranking |
| riichi_called | seat |
| kan_called | seat, kan_type |

---

## Action 类型

| Kind | 字段 |
|------|------|
| discard | tile, riichi |
| call | meld_type |
| ron | target_tile |
| tsumo | - |
| riichi | tile |
| kan | kan_type, tile |

---

## Diagnostics 字段

```json
{
  "prompt_tokens": 2000,
  "completion_tokens": 100,
  "memory_injected_tokens": 150,
  "estimated_tokens": 2150,
  "raw_response": "...",
  "parse_errors": [],
  "fallback_reason": null
}
```

---

## Aggregate 输出

### match_metrics.csv

列：match_id, job_id, seed, outcome, step_count, hand_count, final_points_0-3, point_delta_0-3, ron_count_0-3, tsumo_count_0-3, riichi_count_0-3, total_prompt_tokens, total_completion_tokens, avg_latency_ms, p99_latency_ms, parse_success_count, parse_error_count

### decision_metrics.csv

列：match_id, job_id, seat, hand_index, step_index, parse_status, fallback_used, latency_ms, prompt_tokens, completion_tokens, memory_injected_tokens, action_kind

### player_metrics.csv

列：seat, match_count, avg_final_points, avg_point_delta, total_ron_count, total_tsumo_count, total_riichi_count, riichi_success_rate, avg_prompt_tokens, total_tokens, parse_success_rate, avg_latency_ms, p99_latency_ms

### reliability_summary.json

```json
{
  "total_decisions": 5032,
  "parse_success_rate": 1.0,
  "parse_fallback_rate": 0.0,
  "parse_error_rate": 0.0,
  "avg_latency_ms": 0.0,
  "p50_latency_ms": 0.0,
  "p95_latency_ms": 0.0,
  "p99_latency_ms": 0.0,
  "avg_prompt_tokens": 0.0,
  "avg_completion_tokens": 0.0,
  "avg_memory_injected_tokens": 0.0
}
```

---

## Debug Snapshots

v4.0 支持以下 debug artifacts（需在配置中启用 `save_prompts` 或 `save_debug_snapshots`）：

### prompt_messages.jsonl

每行记录发送给 LLM 的完整 prompt messages。

### model_raw_response.jsonl

每行记录 LLM 的原始响应。

### memory_snapshot.jsonl

每行记录 prompt 注入时的 memory 状态快照，包含读取的 layers、token 估算和
实际渲染进 prompt 的 memory 文本。

### observation.jsonl

每行记录发送给 policy 的 observation。

### 限制说明

v4.0 `save_debug_snapshots=true` 只保存 prompt/model/memory/observation 级别的
调试 traces。

**不包含** 完整的 GameState before/after snapshots（`state_before.jsonl` / `state_after.jsonl`）。

完整的 state snapshots 将在 v4.1 的 golden/debug 模式中实现。
