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
  "stopped_reason": "MATCH_END",
  "outcome": "completed",
  "final_points": [35000, 28000, 22000, 15000],
  "point_delta": [10000, 3000, -3000, -10000],
  "starting_points": [25000, 25000, 25000, 25000],
  "duration_ms": 12345
}
```

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