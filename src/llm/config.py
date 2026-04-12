"""从 YAML 配置文件读取 LLM 配置（取代环境变量）。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml


@dataclass(frozen=True, slots=True)
class LLMClientConfig:
    """单连接配置。"""

    provider: Literal["openai", "anthropic"]
    base_url: str
    api_key: str
    model: str
    timeout_sec: float = 120.0
    max_tokens: int = 1024
    system_prompt: str = ""  # 系统提示词
    prompt_format: Literal["natural", "json"] = "natural"  # Prompt 格式


@dataclass(frozen=True, slots=True)
class MatchEndCondition:
    """对局结束条件。"""

    type: Literal["hands"] = "hands"  # 目前只支持局数制
    value: int = 8  # 默认半庄（8局）
    allow_negative: bool = True  # 是否允许负分继续（False则有人负分时提前结束）

    def is_match_end(self, hands_played: int, scores: tuple[int, ...]) -> tuple[bool, str]:
        """判断是否满足结束条件。

        Returns:
            (是否结束, 结束原因)
        """
        # 检查局数
        if hands_played >= self.value:
            return True, f"hands_completed:{hands_played}"

        # 检查负分（如果启用）
        if not self.allow_negative:
            for seat, score in enumerate(scores):
                if score < 0:
                    return True, f"negative_score:seat{seat}"

        return False, ""


@dataclass(frozen=True, slots=True)
class MatchConfig:
    """对局配置。"""

    seed: int = 42
    match_end: MatchEndCondition | None = None  # 对局结束条件
    max_player_steps: int = 500  # 兼容旧配置，优先级低于 match_end
    players: list[dict[str, Any]] | None = None


def load_kernel_config(config_path: Path | str = "configs/aima_kernel.yaml") -> dict[str, Any]:
    """从 YAML 加载内核配置。

    Args:
        config_path: 配置文件路径，默认 configs/aima_kernel.yaml

    Returns:
        配置字典
    """
    path = Path(config_path)

    # 如果默认路径不存在，尝试使用模板
    if not path.exists() and config_path == "configs/aima_kernel.yaml":
        template_path = Path("configs/aima_kernel_template.yaml")
        if template_path.exists():
            print(
                "警告: aima_kernel.yaml 不存在，使用模板文件。\n"
                "请复制 configs/aima_kernel_template.yaml 为 configs/aima_kernel.yaml 并填入你的 API Key。",
                file=__import__('sys').stderr
            )
            path = template_path
        else:
            raise FileNotFoundError(
                f"配置文件不存在: {config_path}\n"
                "请创建 configs/aima_kernel.yaml（可参考 configs/aima_kernel_template.yaml）"
            )

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_llm_config(
    *,
    config_path: Path | str = "configs/aima_kernel.yaml",
    seat: int | None = None,
    override_cfg: dict[str, Any] | None = None,
) -> LLMClientConfig | None:
    """读取 LLM 配置。

    配置优先级（高到低）：
    1. 函数参数直接覆盖（如 seat 特定配置）
    2. 对局配置 override_cfg
    3. 座位特定配置（seats.seatN）
    4. 内核全局配置（aima_kernel.yaml）

    **重要**：system_prompt 是必需配置项，必须在 YAML 配置中提供。
    参考 configs/aima_kernel_template.yaml 中的示例。

    Args:
        config_path: 内核配置文件路径
        seat: 座位号（用于读取座位特定配置）
        override_cfg: 对局配置中的 llm 部分，用于覆盖内核配置

    Returns:
        LLMClientConfig 或 None（如果未配置 API Key）

    Raises:
        ValueError: 未配置 system_prompt 时抛出，提供配置指引
    """
    cfg = load_kernel_config(config_path)
    llm_cfg = cfg.get("llm", {})

    provider = llm_cfg.get("provider", "openai")
    if provider not in ("openai", "anthropic"):
        raise ValueError(f"provider must be 'openai' or 'anthropic', got {provider!r}")

    # 基础配置（内核全局）
    base_url = llm_cfg.get("base_url", "")
    api_key = llm_cfg.get("api_key", "")
    model = llm_cfg.get("model", "")
    timeout_sec = float(llm_cfg.get("timeout_sec", 120))
    max_tokens = int(llm_cfg.get("max_tokens", 1024))
    system_prompt = llm_cfg.get("system_prompt", "")
    prompt_format = llm_cfg.get("prompt_format", "natural")
    if prompt_format not in ("natural", "json"):
        raise ValueError(f"prompt_format must be 'natural' or 'json', got {prompt_format!r}")

    # 座位特定配置覆盖（优先级：座位 > 全局）
    if seat is not None:
        seat_key = f"seat{seat}"
        seat_cfg = llm_cfg.get("seats", {}).get(seat_key, {})
        if seat_cfg.get("api_key"):
            api_key = seat_cfg["api_key"]
        if seat_cfg.get("model"):
            model = seat_cfg["model"]
        if seat_cfg.get("base_url"):
            base_url = seat_cfg["base_url"]
        if "timeout_sec" in seat_cfg:
            timeout_sec = float(seat_cfg["timeout_sec"])
        if "max_tokens" in seat_cfg:
            max_tokens = int(seat_cfg["max_tokens"])
        if seat_cfg.get("prompt_format"):
            prompt_format = seat_cfg["prompt_format"]

    # 对局配置覆盖（优先级：对局 > 座位 > 全局）
    if override_cfg:
        if override_cfg.get("provider"):
            provider = override_cfg["provider"]
        if override_cfg.get("api_key"):
            api_key = override_cfg["api_key"]
        if override_cfg.get("base_url"):
            base_url = override_cfg["base_url"]
        if override_cfg.get("model"):
            model = override_cfg["model"]
        if "timeout_sec" in override_cfg:
            timeout_sec = float(override_cfg["timeout_sec"])
        if "max_tokens" in override_cfg:
            max_tokens = int(override_cfg["max_tokens"])
        if override_cfg.get("system_prompt"):
            system_prompt = override_cfg["system_prompt"]
        if override_cfg.get("prompt_format"):
            prompt_format = override_cfg["prompt_format"]

    # 检查 API Key
    if not api_key or api_key in ("your-api-key-here", "your-api-key"):
        return None

    # 检查 system_prompt（必需配置项）
    if not system_prompt:
        raise ValueError(
            "未配置 system_prompt。system_prompt 是必需的配置项。\n\n"
            "请在 configs/aima_kernel.yaml 的 llm 部分添加 system_prompt 配置。\n"
            "参考模板文件：configs/aima_kernel_template.yaml\n\n"
            "示例配置：\n"
            "llm:\n"
            "  system_prompt: |\n"
            "    你是日式麻将（立直麻将）的牌手代理...\n\n"
            "提示词应包含：牌面编码说明、输出格式要求、决策约束等。"
        )

    # 设置默认值
    if not base_url:
        base_url = "https://api.openai.com/v1" if provider == "openai" else "https://api.anthropic.com"
    if not model:
        model = "gpt-4o-mini" if provider == "openai" else "claude-3-5-haiku-20241022"

    return LLMClientConfig(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_sec=timeout_sec,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
        prompt_format=prompt_format,
    )


def load_match_config(
    config_path: Path | str = "configs/aima_kernel.yaml",
    match_config_path: Path | str | None = None,
) -> MatchConfig:
    """加载对局配置。

    Args:
        config_path: 内核配置文件路径
        match_config_path: 对局特定配置文件路径（如 player_battle.yaml）

    Returns:
        MatchConfig
    """
    # 从内核配置读取默认值
    cfg = load_kernel_config(config_path)
    default_players = cfg.get("players")

    def _parse_match_end(match_data: dict) -> MatchEndCondition | None:
        """解析对局结束条件配置。"""
        end_cfg = match_data.get("match_end")
        if end_cfg:
            return MatchEndCondition(
                type=end_cfg.get("type", "hands"),
                value=end_cfg.get("value", 8),
                allow_negative=end_cfg.get("allow_negative", True),
            )
        # 兼容旧配置
        return None

    # 如果指定了对局配置，优先读取
    if match_config_path:
        try:
            with open(match_config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            match_data = data.get("match", {})
            return MatchConfig(
                seed=match_data.get("seed", 42),
                match_end=_parse_match_end(match_data),
                max_player_steps=match_data.get("max_player_steps", 500),
                players=match_data.get("players") or default_players,
            )
        except FileNotFoundError:
            pass

    # 使用内核配置
    match_data = cfg.get("match", {})
    return MatchConfig(
        seed=match_data.get("seed", 42),
        match_end=_parse_match_end(match_data),
        max_player_steps=match_data.get("max_player_steps", 500),
        players=default_players,
    )


def get_logging_config(config_path: Path | str = "configs/aima_kernel.yaml") -> dict[str, Any]:
    """获取日志配置。"""
    cfg = load_kernel_config(config_path)
    return cfg.get("logging", {})
