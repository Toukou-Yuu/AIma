"""从 YAML 配置文件读取 LLM / 对局配置。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

_REPO_TEMPLATE_PATH = Path("configs/template.yaml")
_KERNEL_TEMPLATE_PATH = Path("configs/aima_kernel_template.yaml")
_BASE_KERNEL_PATH = Path("configs/aima_kernel.yaml")
_ENV_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_PLACEHOLDER_KEYS = {"", "your-api-key-here", "your-api-key"}


@dataclass(frozen=True, slots=True)
class LLMRuntimeConfig:
    """LLM 运行时配置。"""

    prompt_format: Literal["natural", "json"]
    context_scope: Literal["stateless", "per_hand", "per_match"]
    compression_level: Literal["none", "snip", "micro", "collapse", "autocompact"]
    history_budget: int
    context_compression_threshold: float
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
    max_context: int
    max_tokens: int
    system_prompt: str
    prompt_format: Literal["natural", "json"]
    context_scope: Literal["stateless", "per_hand", "per_match"]
    compression_level: Literal["none", "snip", "micro", "collapse", "autocompact"]
    history_budget: int
    context_compression_threshold: float

    @property
    def has_api_key(self) -> bool:
        """Whether this profile has a usable API key."""
        return not _is_missing_api_key(self.api_key)


@dataclass(frozen=True, slots=True)
class LLMProfileConfig:
    """LLM 连接 profile。"""

    name: str
    provider: Literal["openai", "anthropic"]
    base_url: str
    api_key: str
    model: str
    timeout_sec: float
    max_context: int
    max_tokens: int


@dataclass(frozen=True, slots=True)
class SeatLLMBinding:
    """座位到 LLM profile 的绑定。"""

    seat: int
    profile_name: str
    profile: LLMProfileConfig


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
    return (
        requested_path.parent == _BASE_KERNEL_PATH.parent
        and requested_path.name != _BASE_KERNEL_PATH.name
    )


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
                "请复制 configs/aima_kernel_template.yaml 为 configs/aima_kernel.yaml "
                "并填入你的 API Key。",
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
    override_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = load_kernel_config(config_path)
    llm_cfg = cfg.get("llm")
    if not isinstance(llm_cfg, dict):
        raise ValueError("缺少 llm 配置段")

    effective = dict(llm_cfg)

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
    del seat
    llm_cfg = _effective_llm_config(config_path=config_path, override_cfg=override_cfg)

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

    threshold = float(_get_required(llm_cfg, "context_compression_threshold"))
    if not 0 < threshold <= 1:
        raise ValueError("context_compression_threshold must be in (0, 1]")

    return LLMRuntimeConfig(
        prompt_format=prompt_format,
        context_scope=context_scope,
        compression_level=compression_level,
        history_budget=int(_get_required(llm_cfg, "history_budget")),
        context_compression_threshold=threshold,
        request_delay=float(_get_required(llm_cfg, "request_delay")),
        conversation_logging_enabled=bool(_get_required(llm_cfg, "conversation_logging.enabled")),
    )


def _resolve_env_value(value: str) -> str:
    match = _ENV_PATTERN.match(value.strip())
    if not match:
        return value
    return os.environ.get(match.group(1), "")


def _is_missing_api_key(api_key: str) -> bool:
    return api_key.strip() in _PLACEHOLDER_KEYS


def _parse_profile(name: str, data: Any) -> LLMProfileConfig:
    if not isinstance(data, dict):
        raise ValueError(f"llm.profiles.{name} 必须是对象")

    provider = _validate_choice(
        f"llm.profiles.{name}.provider",
        str(_get_required(data, "provider")),
        ("openai", "anthropic"),
    )
    max_context = int(_get_required(data, "max_context"))
    max_tokens = int(_get_required(data, "max_tokens"))
    if max_context <= 0:
        raise ValueError(f"llm.profiles.{name}.max_context must be positive")
    if max_tokens <= 0:
        raise ValueError(f"llm.profiles.{name}.max_tokens must be positive")
    if max_tokens >= max_context:
        raise ValueError(
            f"llm.profiles.{name}.max_tokens must be smaller than max_context"
        )

    return LLMProfileConfig(
        name=name,
        provider=provider,
        base_url=str(_get_required(data, "base_url")),
        api_key=_resolve_env_value(str(_get_required(data, "api_key"))),
        model=str(_get_required(data, "model")),
        timeout_sec=float(_get_required(data, "timeout_sec")),
        max_context=max_context,
        max_tokens=max_tokens,
    )


def load_llm_profiles(
    *,
    config_path: Path | str = _BASE_KERNEL_PATH,
    override_cfg: dict[str, Any] | None = None,
) -> dict[str, LLMProfileConfig]:
    """读取所有 LLM 连接 profile。"""
    llm_cfg = _effective_llm_config(config_path=config_path, override_cfg=override_cfg)
    profiles_cfg = _get_required(llm_cfg, "profiles")
    if not isinstance(profiles_cfg, dict) or not profiles_cfg:
        raise ValueError("llm.profiles 必须是非空对象")
    return {name: _parse_profile(name, data) for name, data in profiles_cfg.items()}


def load_seat_llm_bindings(
    *,
    config_path: Path | str = _BASE_KERNEL_PATH,
    override_cfg: dict[str, Any] | None = None,
) -> dict[int, SeatLLMBinding]:
    """读取 seat0-seat3 到 LLM profile 的绑定。"""
    llm_cfg = _effective_llm_config(config_path=config_path, override_cfg=override_cfg)
    seats_cfg = _get_required(llm_cfg, "seats")
    if not isinstance(seats_cfg, dict):
        raise ValueError("llm.seats 必须是对象")

    profiles = load_llm_profiles(config_path=config_path, override_cfg=override_cfg)
    bindings: dict[int, SeatLLMBinding] = {}
    for seat in range(4):
        key = f"seat{seat}"
        seat_cfg = _get_required(seats_cfg, key)
        if not isinstance(seat_cfg, dict):
            raise ValueError(f"llm.seats.{key} 必须是对象")
        profile_name = str(_get_required(seat_cfg, "profile"))
        if profile_name not in profiles:
            raise ValueError(f"llm.seats.{key}.profile 引用了不存在的 profile: {profile_name}")
        bindings[seat] = SeatLLMBinding(
            seat=seat,
            profile_name=profile_name,
            profile=profiles[profile_name],
        )
    return bindings


def _client_config_from_profile(
    profile: LLMProfileConfig,
    runtime_cfg: LLMRuntimeConfig,
    system_prompt: str,
) -> LLMClientConfig:
    prompt_budget = int(profile.max_context * runtime_cfg.context_compression_threshold)
    if profile.max_tokens >= prompt_budget:
        raise ValueError(
            f"llm.profiles.{profile.name}.max_tokens must be smaller than "
            "max_context * context_compression_threshold"
        )
    return LLMClientConfig(
        provider=profile.provider,
        base_url=profile.base_url,
        api_key=profile.api_key,
        model=profile.model,
        timeout_sec=profile.timeout_sec,
        max_context=profile.max_context,
        max_tokens=profile.max_tokens,
        system_prompt=system_prompt,
        prompt_format=runtime_cfg.prompt_format,
        context_scope=runtime_cfg.context_scope,
        compression_level=runtime_cfg.compression_level,
        history_budget=runtime_cfg.history_budget,
        context_compression_threshold=runtime_cfg.context_compression_threshold,
    )


def load_seat_llm_configs(
    *,
    config_path: Path | str = _BASE_KERNEL_PATH,
    override_cfg: dict[str, Any] | None = None,
) -> dict[int, LLMClientConfig]:
    """读取四个座位的 LLM 客户端配置。"""
    llm_cfg = _effective_llm_config(config_path=config_path, override_cfg=override_cfg)
    runtime_cfg = load_llm_runtime_config(config_path=config_path, override_cfg=override_cfg)

    system_prompt = str(_get_required(llm_cfg, "system_prompt"))
    if not system_prompt.strip():
        raise ValueError(
            "未配置 system_prompt。请在 llm.system_prompt 中提供完整提示词。"
        )

    bindings = load_seat_llm_bindings(config_path=config_path, override_cfg=override_cfg)
    return {
        seat: _client_config_from_profile(binding.profile, runtime_cfg, system_prompt)
        for seat, binding in bindings.items()
    }


def load_llm_config(
    *,
    config_path: Path | str = _BASE_KERNEL_PATH,
    seat: int | None = None,
    override_cfg: dict[str, Any] | None = None,
) -> LLMClientConfig:
    """读取指定座位的 LLM 客户端配置。"""
    if seat is None:
        raise ValueError("load_llm_config 需要显式传入 seat")
    if seat not in range(4):
        raise ValueError(f"seat 必须在 0-3 之间: {seat}")
    return load_seat_llm_configs(config_path=config_path, override_cfg=override_cfg)[seat]


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
