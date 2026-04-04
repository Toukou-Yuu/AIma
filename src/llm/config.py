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


@dataclass(frozen=True, slots=True)
class MatchConfig:
    """对局配置。"""

    seed: int = 42
    max_player_steps: int = 500
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
    timeout_sec: float | None = None,
    max_tokens: int | None = None,
) -> LLMClientConfig | None:
    """读取 LLM 配置。

    Args:
        config_path: 配置文件路径
        seat: 座位号（用于读取座位特定配置）
        timeout_sec: 覆盖超时时间
        max_tokens: 覆盖最大 token 数

    Returns:
        LLMClientConfig 或 None（如果未配置 API Key）
    """
    cfg = load_kernel_config(config_path)
    llm_cfg = cfg.get("llm", {})

    provider = llm_cfg.get("provider", "openai")
    if provider not in ("openai", "anthropic"):
        raise ValueError(f"provider must be 'openai' or 'anthropic', got {provider!r}")

    # 基础配置
    base_url = llm_cfg.get("base_url", "")
    api_key = llm_cfg.get("api_key", "")
    model = llm_cfg.get("model", "")

    # 座位特定配置覆盖
    if seat is not None:
        seat_key = f"seat{seat}"
        seat_cfg = llm_cfg.get("seats", {}).get(seat_key, {})
        if seat_cfg.get("api_key"):
            api_key = seat_cfg["api_key"]
        if seat_cfg.get("model"):
            model = seat_cfg["model"]

    # 检查 API Key
    if not api_key or api_key in ("your-api-key-here", "your-api-key"):
        return None

    # 设置默认值
    if not base_url:
        base_url = "https://api.openai.com/v1" if provider == "openai" else "https://api.anthropic.com"
    if not model:
        model = "gpt-4o-mini" if provider == "openai" else "claude-3-5-haiku-20241022"

    timeout_s = float(llm_cfg.get("timeout_sec", 120))
    max_tok = int(llm_cfg.get("max_tokens", 1024))

    # 参数覆盖
    if timeout_sec is not None:
        timeout_s = timeout_sec
    if max_tokens is not None:
        max_tok = max_tokens

    return LLMClientConfig(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_sec=timeout_s,
        max_tokens=max_tok,
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

    # 如果指定了对局配置，优先读取
    if match_config_path:
        try:
            with open(match_config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            match_data = data.get("match", {})
            return MatchConfig(
                seed=match_data.get("seed", 42),
                max_player_steps=match_data.get("max_player_steps", 500),
                players=match_data.get("players") or default_players,
            )
        except FileNotFoundError:
            pass

    # 使用内核配置
    match_data = cfg.get("match", {})
    return MatchConfig(
        seed=match_data.get("seed", 42),
        max_player_steps=match_data.get("max_player_steps", 500),
        players=default_players,
    )


def get_logging_config(config_path: Path | str = "configs/aima_kernel.yaml") -> dict[str, Any]:
    """获取日志配置。"""
    cfg = load_kernel_config(config_path)
    return cfg.get("logging", {})
