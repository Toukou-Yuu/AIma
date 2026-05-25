"""Replay 后端实现，根据历史 decisions 回放输出。"""

# backend type: "replay"

from __future__ import annotations

import time
from pathlib import Path

from models.backend import ChatMessage, ModelRequest, ModelResponse
from models.schema import ModelSpec


class ReplayBackend:
    """根据历史 decisions.jsonl 回放输出的后端。

    用于复现实验结果，不调用任何外部服务。
    同时实现 CompletionClient 和 ModelBackend 协议。
    """

    def __init__(self, spec: ModelSpec, replay_path: Path | None = None) -> None:
        """初始化 Replay 后端。

        Args:
            spec: 模型配置规格
            replay_path: decisions.jsonl 文件路径（可选）
        """
        if spec.backend != "replay":
            msg = f"ReplayBackend requires backend=replay, got {spec.backend}"
            raise ValueError(msg)

        self._spec = spec
        self._replay_path = replay_path or Path(spec.extra.get("replay_path", ""))
        self._decisions: list[dict] = []
        self._decision_index = 0
        self._last_messages: list[ChatMessage] | None = None

        # 加载 decisions
        self._load_decisions()

    @property
    def spec(self) -> ModelSpec:
        """当前模型配置。"""
        return self._spec

    @property
    def backend_name(self) -> str:
        """后端名称。"""
        return "replay"

    @property
    def model_name(self) -> str:
        """模型名称。"""
        return self._spec.model_name

    @property
    def last_messages(self) -> list[ChatMessage] | None:
        """最近一次调用时传入的消息列表，用于调试。"""
        return self._last_messages

    def _load_decisions(self) -> None:
        """从 decisions.jsonl 加载决策记录。"""
        import json

        if not self._replay_path.exists():
            return

        with open(self._replay_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    decision = json.loads(line)
                    self._decisions.append(decision)
                except json.JSONDecodeError:
                    continue

    def _get_next_response(self) -> str:
        """获取下一个回放响应。"""
        if self._decision_index < len(self._decisions):
            decision = self._decisions[self._decision_index]
            self._decision_index += 1
            # 返回 raw_output 字段，如果不存在则返回空字符串
            return decision.get("raw_output", "")
        return ""

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,  # noqa: ARG002
    ) -> str:
        """返回回放响应（CompletionClient 协议）。

        Args:
            messages: 消息列表（忽略）
            model: 模型名称（忽略）

        Returns:
            回放响应字符串
        """
        self._last_messages = list(messages)
        return self._get_next_response()

    def generate(self, request: ModelRequest) -> ModelResponse:
        """生成回放响应（ModelBackend 协议）。

        Args:
            request: 模型请求

        Returns:
            ModelResponse 包含回放响应
        """
        start_time = time.perf_counter()
        self._last_messages = list(request.messages)

        text = self._get_next_response()
        latency_ms = (time.perf_counter() - start_time) * 1000

        # 从 decision 记录中获取 token 信息（如果有）
        decision_idx = self._decision_index - 1
        prompt_tokens = None
        completion_tokens = None
        if decision_idx >= 0 and decision_idx < len(self._decisions):
            diagnostics = self._decisions[decision_idx].get("diagnostics", {})
            prompt_tokens = diagnostics.get("prompt_tokens")
            completion_tokens = diagnostics.get("completion_tokens")

        return ModelResponse(
            text=text,
            finish_reason="stop",
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            backend_name=self.backend_name,
            model_name=self.model_name,
        )

    def reset(self) -> None:
        """重置回放索引，从头开始回放。"""
        self._decision_index = 0