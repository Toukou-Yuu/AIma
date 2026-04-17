"""从 YAML 配置文件读取 LLM / 对局配置。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml


_REPO_TEMPLATE_PATH = Path("configs/template.yaml")
_KERNEL_TEMPLATE_PATH = Path("configs/aima_kernel_template.yaml")
_BASE_KERNEL_PATH = Path("configs/aima_kernel.yaml")


@dataclass(frozen=True, slots=True)
class LLMRuntimeConfig:
    """LLM 运行时配置。"""

    prompt_format: Literal["natural", "json"]
    context_scope: Literal["stateless", "per_hand", "per_match"]
    compression_level: Literal["none", "snip", "micro", "collapse", "autocompact"]
    history_budget: int
    context_budget_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int
    request_delay: float
    conversation_logging_enabled: bool


@dataclass(frozen=True, slots=True)
class LLMClientConfig:
    """LLM 单连接配置。"""

    provider: Literal["openai", "anthropic"]
    base_url: str
    api_key: str
    model: str
    timeout_sec: float
    max_tokens: int
    system_prompt: str
    prompt_format: Literal["natural", "json"]
    context_scope: Literal["stateless", "per_hand", "per_match"]
    compression_level: Literal["none", "snip", "micro", "collapse", "autocompact"]
    history_budget: int
    context_budget_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int


@dataclass(frozen=True, slots=True)
class MatchEndCondition:
    """对局结束条件。"""

    type: Literal["hands"]
    value: int
    allow_negative: bool

    def is_match_end(self, hands_played: int, scores: tuple[int, ...]) -> tuple[bool, str]:
        """判断是否满足结束条件。"""
        if hands_played >= self.value:
            return True, f"hands_completed:{hands_played}"

        if not self.allow_negative:
            for seat, score in enumerate(scores):
                if score < 0:
                    return True, f"negative_score:seat{seat}"

        return False, ""


@dataclass(frozen=True, slots=True)
class MatchConfig:
    """对局配置。"""

    seed: int
    match_end: MatchEndCondition
    max_player_steps: int | None
    players: list[dict[str, Any]] | None


def _read_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        msg = f"配置文件顶层必须是对象: {path}"
        raise ValueError(msg)
    return data


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _get_required(config: dict[str, Any], path: str) -> Any:
    current: Any = config
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            msg = f"缺少必需配置项: {path}"
            raise ValueError(msg)
        current = current[part]
    return current


def _validate_choice(name: str, value: str, choices: tuple[str, ...]) -> str:
    if value not in choices:
        msg = f"{name} must be one of {choices}, got {value!r}"
        raise ValueError(msg)
    return value


def _should_merge_base_kernel(requested_path: Path) -> bool:
    return requested_path.parent == _BASE_KERNEL_PATH.parent and requested_path.name != _BASE_KERNEL_PATH.name


def load_kernel_config(config_path: Path | str = _BASE_KERNEL_PATH) -> dict[str, Any]:
    """加载配置，并按文件级优先级合并默认模板。"""
    requested_path = Path(config_path)
    merged: dict[str, Any] = {}

    for template_path in (_REPO_TEMPLATE_PATH, _KERNEL_TEMPLATE_PATH):
        merged = _deep_merge(merged, _read_yaml_file(template_path))

    if _should_merge_base_kernel(requested_path) and _BASE_KERNEL_PATH.exists():
        merged = _deep_merge(merged, _read_yaml_file(_BASE_KERNEL_PATH))

    if requested_path.exists():
        merged = _deep_merge(merged, _read_yaml_file(requested_path))
        return merged

    if requested_path == _BASE_KERNEL_PATH:
        if _KERNEL_TEMPLATE_PATH.exists():
            print(
                "警告: aima_kernel.yaml 不存在，使用模板文件。\n"
                "请复制 configs/aima_kernel_template.yaml 为 configs/aima_kernel.yaml 并填入你的 API Key。",
                file=__import__("sys").stderr,
            )
            return merged
        msg = (
            f"配置文件不存在: {config_path}\n"
            "请创建 configs/aima_kernel.yaml（可参考 configs/aima_kernel_template.yaml）"
        )
        raise FileNotFoundError(msg)

    msg = f"配置文件不存在: {requested_path}"
    raise FileNotFoundError(msg)


def _effective_llm_config(
    *,
    config_path: Path | str,
    seat: int | None = None,
    override_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = load_kernel_config(config_path)
    llm_cfg = cfg.get("llm")
    if not isinstance(llm_cfg, dict):
        raise ValueError("缺少 llm 配置段")

    effective = dict(llm_cfg)
    effective.pop("seats", None)

    if seat is not None:
        seat_cfg = llm_cfg.get("seats", {}).get(f"seat{seat}", {})
        if seat_cfg and not isinstance(seat_cfg, dict):
            raise ValueError(f"llm.seats.seat{seat} 必须是对象")
        effective = _deep_merge(effective, seat_cfg)

    if override_cfg:
        if not isinstance(override_cfg, dict):
            raise ValueError("override_cfg 必须是对象")
        effective = _deep_merge(effective, override_cfg)

    return effective


def load_llm_runtime_config(
    *,
    config_path: Path | str = _BASE_KERNEL_PATH,
    seat: int | None = None,
    override_cfg: dict[str, Any] | None = None,
) -> LLMRuntimeConfig:
    """读取 LLM 运行时配置。"""
    llm_cfg = _effective_llm_config(config_path=config_path, seat=seat, override_cfg=override_cfg)

    prompt_format = _validate_choice(
        "prompt_format",
        str(_get_required(llm_cfg, "prompt_format")),
        ("natural", "json"),
    )
    context_scope = _validate_choice(
        "context_scope",
        str(_get_required(llm_cfg, "context_scope")),
        ("stateless", "per_hand", "per_match"),
    )
    compression_level = _validate_choice(
        "compression_level",
        str(_get_required(llm_cfg, "compression_level")),
        ("none", "snip", "micro", "collapse", "autocompact"),
    )

    return LLMRuntimeConfig(
        prompt_format=prompt_format,
        context_scope=context_scope,
        compression_level=compression_level,
        history_budget=int(_get_required(llm_cfg, "history_budget")),
        context_budget_tokens=int(_get_required(llm_cfg, "context_budget_tokens")),
        reserved_output_tokens=int(_get_required(llm_cfg, "reserved_output_tokens")),
        safety_margin_tokens=int(_get_required(llm_cfg, "safety_margin_tokens")),
        request_delay=float(_get_required(llm_cfg, "request_delay")),
        conversation_logging_enabled=bool(_get_required(llm_cfg, "conversation_logging.enabled")),
    )


def load_llm_config(
    *,
    config_path: Path | str = _BASE_KERNEL_PATH,
    seat: int | None = None,
    override_cfg: dict[str, Any] | None = None,
) -> LLMClientConfig | None:
    """读取 LLM 客户端配置。"""
    llm_cfg = _effective_llm_config(config_path=config_path, seat=seat, override_cfg=override_cfg)
    runtime_cfg = load_llm_runtime_config(config_path=config_path, seat=seat, override_cfg=override_cfg)

    provider = _validate_choice(
        "provider",
        str(_get_required(llm_cfg, "provider")),
        ("openai", "anthropic"),
    )
    api_key = str(_get_required(llm_cfg, "api_key"))
    if not api_key or api_key in ("your-api-key-here", "your-api-key"):
        return None

    system_prompt = str(_get_required(llm_cfg, "system_prompt"))
    if not system_prompt.strip():
        raise ValueError(
            "未配置 system_prompt。请在 llm.system_prompt 中提供完整提示词。"
        )

    return LLMClientConfig(
        provider=provider,
        base_url=str(_get_required(llm_cfg, "base_url")),
        api_key=api_key,
        model=str(_get_required(llm_cfg, "model")),
        timeout_sec=float(_get_required(llm_cfg, "timeout_sec")),
        max_tokens=int(_get_required(llm_cfg, "max_tokens")),
        system_prompt=system_prompt,
        prompt_format=runtime_cfg.prompt_format,
        context_scope=runtime_cfg.context_scope,
        compression_level=runtime_cfg.compression_level,
        history_budget=runtime_cfg.history_budget,
        context_budget_tokens=runtime_cfg.context_budget_tokens,
        reserved_output_tokens=runtime_cfg.reserved_output_tokens,
        safety_margin_tokens=runtime_cfg.safety_margin_tokens,
    )


def _parse_match_end(match_data: dict[str, Any]) -> MatchEndCondition:
    end_cfg = _get_required(match_data, "match_end")
    if not isinstance(end_cfg, dict):
        raise ValueError("match.match_end 必须是对象")
    return MatchEndCondition(
        type=str(_get_required(end_cfg, "type")),
        value=int(_get_required(end_cfg, "value")),
        allow_negative=bool(_get_required(end_cfg, "allow_negative")),
    )


def load_match_config(
    config_path: Path | str = _BASE_KERNEL_PATH,
    match_config_path: Path | str | None = None,
) -> MatchConfig:
    """加载对局配置。"""
    cfg = load_kernel_config(config_path)

    if match_config_path is not None:
        cfg = load_kernel_config(match_config_path)

    match_data = _get_required(cfg, "match")
    if not isinstance(match_data, dict):
        raise ValueError("match 配置段必须是对象")

    players = match_data.get("players")
    if players is not None and not isinstance(players, list):
        raise ValueError("match.players 必须是列表")

    max_player_steps = match_data.get("max_player_steps")
    if max_player_steps is not None:
        max_player_steps = int(max_player_steps)

    return MatchConfig(
        seed=int(_get_required(match_data, "seed")),
        match_end=_parse_match_end(match_data),
        max_player_steps=max_player_steps,
        players=players,
    )


def get_logging_config(config_path: Path | str = _BASE_KERNEL_PATH) -> dict[str, Any]:
    """获取日志配置。"""
    cfg = load_kernel_config(config_path)
    logging_cfg = cfg.get("logging")
    if not isinstance(logging_cfg, dict):
        raise ValueError("缺少 logging 配置段")
    return logging_cfg
