"""交互层的数据装配器。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from llm.config import load_kernel_config
from ui.interactive.utils import KERNEL_CONFIG_PATH, PLAYERS_DIR, load_profile_data
from ui.services import llm_connection

SEAT_LABELS = ("东家", "南家", "西家", "北家")
_PLACEHOLDER_KEYS = {"", "your-api-key", "your-api-key-here"}
_NORMAL_STOP_PREFIXES = ("hands_completed:", "negative_score:")
_ERROR_STOP_PREFIXES = (
    "begin_round_failed:",
    "illegal_action:",
    "noop_wall_failed:",
    "parse_error",
    "step_failed:",
)
_TRUNCATED_STOP_PREFIXES = ("max_player_steps",)


def _starts_with_any(value: str, prefixes: tuple[str, ...]) -> bool:
    """判断结束原因是否匹配任一已知前缀。"""
    return any(value.startswith(prefix) for prefix in prefixes)


def _is_normal_stop_reason(reason: str) -> bool:
    """配置驱动的正常停止原因。"""
    return reason == "match_end" or _starts_with_any(reason, _NORMAL_STOP_PREFIXES)


def _is_error_stop_reason(reason: str) -> bool:
    """异常停止原因。"""
    return _starts_with_any(reason, _ERROR_STOP_PREFIXES)


def _is_truncated_stop_reason(reason: str) -> bool:
    """截断停止原因。"""
    return _starts_with_any(reason, _TRUNCATED_STOP_PREFIXES)


def _label_with_reason_detail(label: str, reason: str, prefix: str) -> str:
    """生成带原始细节的原因文案。"""
    detail = reason.removeprefix(prefix).strip()
    return f"{label}: {detail}" if detail else label


@dataclass(frozen=True, slots=True)
class LLMProfileStatus:
    """单个 LLM profile 的 UI 状态。"""

    name: str
    provider_label: str
    model: str
    configured: bool
    connection_label: str
    connection_style: str
    connection_note: str


@dataclass(frozen=True, slots=True)
class SeatModelBinding:
    """座位到 LLM profile 的 UI 绑定。"""

    seat: int
    seat_label: str
    profile_name: str
    model: str
    connection_label: str
    connection_style: str


@dataclass(frozen=True, slots=True)
class ModelSummary:
    """首页和配置页使用的模型摘要。"""

    provider_label: str
    model: str
    configured: bool
    prompt_format: str
    conversation_logging: bool
    note: str
    connection_label: str
    connection_style: str
    connection_note: str
    profiles: tuple[LLMProfileStatus, ...] = ()
    seat_bindings: tuple[SeatModelBinding, ...] = ()

    @property
    def headline(self) -> str:
        """面向 UI 的主标题。"""
        if not self.configured:
            return "未完成模型配置"
        if self.profiles:
            return f"4席 / {len(self.profiles)} profiles"
        return f"{self.provider_label} / {self.model}"


@dataclass(frozen=True, slots=True)
class RosterEntry:
    """默认阵容中的一席。"""

    seat: int
    seat_label: str
    player_id: str
    display_name: str
    mode_label: str
    profile_found: bool


@dataclass(frozen=True, slots=True)
class ReplaySummary:
    """牌谱摘要。"""

    path: Path
    stem: str
    modified_at: datetime
    seed: int | None
    stopped_reason: str
    final_phase: str
    action_count: int
    step_count: int
    ranking_by_seat: tuple[int, int, int, int] | None
    final_scores: tuple[int, int, int, int] | None

    @property
    def time_label(self) -> str:
        """最后修改时间标签。"""
        return self.modified_at.strftime("%m-%d %H:%M")

    @property
    def status_label(self) -> str:
        """面向 UI 的结束状态，只表达完成度，不混入结束原因。"""
        reason = self.stopped_reason or ""
        if _is_error_stop_reason(reason):
            return "异常"
        if _is_truncated_stop_reason(reason):
            return "已截断"
        if (
            self.ranking_by_seat
            or self.final_phase == "match_end"
            or _is_normal_stop_reason(reason)
        ):
            return "已完成"
        return "未完成"

    @property
    def reason_label(self) -> str:
        """结束原因简写。"""
        reason = self.stopped_reason or "unknown"
        if reason.startswith("hands_completed:"):
            count = reason.split(":", 1)[1]
            return f"局数完成（{count}局）"
        if reason.startswith("negative_score:"):
            return _label_with_reason_detail("负分终止", reason, "negative_score:")
        if reason == "match_end":
            return "自然终局"
        if reason.startswith("begin_round_failed:"):
            return _label_with_reason_detail("开局失败", reason, "begin_round_failed:")
        if reason.startswith("illegal_action:"):
            return _label_with_reason_detail("非法动作", reason, "illegal_action:")
        if reason.startswith("noop_wall_failed:"):
            return _label_with_reason_detail("局间推进失败", reason, "noop_wall_failed:")
        if reason.startswith("step_failed:"):
            return _label_with_reason_detail("执行失败", reason, "step_failed:")
        if reason == "parse_error":
            return "牌谱解析失败"
        if reason.startswith("max_player_steps"):
            return "步数截断"
        if reason == "unknown":
            return "未知原因"
        return reason

    @property
    def ranking_label(self) -> str:
        """终局名次摘要。"""
        if not self.ranking_by_seat:
            return "未结算"
        return " ".join(
            f"{SEAT_LABELS[seat]}#{rank}"
            for seat, rank in enumerate(self.ranking_by_seat)
        )

    @property
    def score_label(self) -> str:
        """终局分数摘要。"""
        if not self.final_scores:
            return "未记录"
        return " / ".join(
            f"{SEAT_LABELS[seat]} {score:,}"
            for seat, score in enumerate(self.final_scores)
        )

    @property
    def menu_label(self) -> str:
        """选择菜单中的单行标签。"""
        return f"{self.time_label} | {self.status_label} | {self.stem}"


@dataclass(frozen=True, slots=True)
class HomeSnapshot:
    """主菜单首页需要的完整数据。"""

    model: ModelSummary
    roster: tuple[RosterEntry, ...]
    recent_replays: tuple[ReplaySummary, ...]


def _safe_load_yaml(path: Path) -> dict[str, Any]:
    """安全加载已合并配置；失败时返回空 dict。"""
    try:
        data = load_kernel_config(path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _provider_label(provider: str, base_url: str) -> str:
    """根据 provider/base_url 生成展示名。"""
    base = base_url.lower()
    if "localhost" in base or "127.0.0.1" in base or "ollama" in base:
        return "本地模型"
    if "openai.com" in base:
        return "OpenAI"
    if "deepseek" in base:
        return "DeepSeek"
    if provider == "anthropic":
        return "Anthropic"
    if provider == "openai":
        return "OpenAI 兼容"
    return "远程模型"


def _profile_status_from_config(name: str, profile_cfg: dict[str, Any]) -> LLMProfileStatus:
    api_key = str(profile_cfg.get("api_key", "")).strip()
    configured = api_key not in _PLACEHOLDER_KEYS
    provider = str(profile_cfg.get("provider", ""))
    base_url = str(profile_cfg.get("base_url", ""))
    cache_key = (provider, base_url, api_key, str(configured))
    cached_probe = llm_connection.get_cached_probe_status(cache_key)
    llm_connection.schedule_probe_refresh(
        cache_key=cache_key,
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        configured=configured,
    )

    if cached_probe is None:
        connection_label, connection_style, connection_note = ("探测中", "yellow", "正在后台刷新")
    else:
        connection_label, connection_style, connection_note = cached_probe

    return LLMProfileStatus(
        name=name,
        provider_label=_provider_label(provider, base_url),
        model=str(profile_cfg.get("model", "--")),
        configured=configured,
        connection_label=connection_label,
        connection_style=connection_style,
        connection_note=connection_note,
    )


def _missing_profile_status(name: str) -> LLMProfileStatus:
    return LLMProfileStatus(
        name=name,
        provider_label="未配置",
        model="--",
        configured=False,
        connection_label="未连接",
        connection_style="red",
        connection_note="profile 不存在",
    )


def _build_profile_statuses(
    profiles_cfg: dict[str, Any],
    seats_cfg: dict[str, Any],
) -> dict[str, LLMProfileStatus]:
    referenced = []
    for seat in range(4):
        seat_cfg = seats_cfg.get(f"seat{seat}")
        if isinstance(seat_cfg, dict):
            profile_name = str(seat_cfg.get("profile", "")).strip()
            if profile_name:
                referenced.append(profile_name)

    statuses: dict[str, LLMProfileStatus] = {}
    for profile_name in dict.fromkeys(referenced):
        profile_cfg = profiles_cfg.get(profile_name)
        if isinstance(profile_cfg, dict):
            statuses[profile_name] = _profile_status_from_config(profile_name, profile_cfg)
        else:
            statuses[profile_name] = _missing_profile_status(profile_name or "未绑定")
    return statuses


def _build_seat_bindings(
    seats_cfg: dict[str, Any],
    profile_statuses: dict[str, LLMProfileStatus],
) -> tuple[SeatModelBinding, ...]:
    bindings = []
    for seat, seat_label in enumerate(SEAT_LABELS):
        seat_cfg = seats_cfg.get(f"seat{seat}")
        profile_name = (
            str(seat_cfg.get("profile", "")).strip()
            if isinstance(seat_cfg, dict)
            else ""
        )
        status = profile_statuses.get(profile_name) or _missing_profile_status(
            profile_name or "未绑定"
        )
        bindings.append(
            SeatModelBinding(
                seat=seat,
                seat_label=seat_label,
                profile_name=status.name,
                model=status.model,
                connection_label=status.connection_label,
                connection_style=status.connection_style,
            )
        )
    return tuple(bindings)


def _summarize_profile_connections(profiles: tuple[LLMProfileStatus, ...]) -> tuple[str, str, str]:
    if not profiles:
        return ("未连接", "yellow", "未配置 LLM profile")
    labels = [f"{profile.name} {profile.connection_label}" for profile in profiles]
    if all(profile.connection_style == "green" for profile in profiles):
        style = "green"
    elif any(profile.connection_style == "red" for profile in profiles):
        style = "red"
    else:
        style = "yellow"
    return (" / ".join(labels), style, f"{len(profiles)} 个 profile")


def _summarize_config_note(profiles: tuple[LLMProfileStatus, ...]) -> tuple[bool, str]:
    missing = [profile.name for profile in profiles if not profile.configured]
    if missing:
        return False, "缺少 API Key: " + ", ".join(missing)
    if not profiles:
        return False, "缺少 LLM profile"
    return True, "所有 LLM profile 已配置"


def load_model_summary(config_path: Path = KERNEL_CONFIG_PATH) -> ModelSummary:
    """读取模型配置摘要。"""
    cfg = _safe_load_yaml(config_path)
    if not cfg:
        return ModelSummary(
            provider_label="未配置",
            model="--",
            configured=False,
            prompt_format="--",
            conversation_logging=False,
            note="缺少 configs/aima_kernel.yaml",
            connection_label="未连接",
            connection_style="yellow",
            connection_note="缺少配置文件",
        )

    llm_cfg = cfg.get("llm", {}) if isinstance(cfg.get("llm"), dict) else {}
    profiles = llm_cfg.get("profiles", {}) if isinstance(llm_cfg.get("profiles"), dict) else {}
    seats = llm_cfg.get("seats", {}) if isinstance(llm_cfg.get("seats"), dict) else {}
    profile_statuses = _build_profile_statuses(profiles, seats)
    profile_list = tuple(profile_statuses.values())
    seat_bindings = _build_seat_bindings(seats, profile_statuses)
    configured, note = _summarize_config_note(profile_list)
    connection_label, connection_style, connection_note = _summarize_profile_connections(
        profile_list
    )
    primary_profile = profile_list[0] if profile_list else None

    return ModelSummary(
        provider_label=primary_profile.provider_label if primary_profile else "未配置",
        model=primary_profile.model if primary_profile else "--",
        configured=configured,
        prompt_format=str(llm_cfg.get("prompt_format", "--")),
        conversation_logging=bool(
            (llm_cfg.get("conversation_logging") or {}).get("enabled", False),
        ),
        note=note,
        connection_label=connection_label,
        connection_style=connection_style,
        connection_note=connection_note,
        profiles=profile_list,
        seat_bindings=seat_bindings,
    )


def load_roster_entries(
    config_path: Path = KERNEL_CONFIG_PATH,
    players_dir: Path = PLAYERS_DIR,
) -> tuple[RosterEntry, ...]:
    """读取默认阵容摘要。"""
    del players_dir  # 预留给将来多路径扩展
    cfg = _safe_load_yaml(config_path)
    raw_players = cfg.get("players", [])
    players_by_seat: dict[int, str] = {}

    if isinstance(raw_players, list):
        for raw in raw_players:
            if not isinstance(raw, dict):
                continue
            try:
                seat = int(raw.get("seat", -1))
            except (TypeError, ValueError):
                continue
            if seat not in range(4):
                continue
            player_id = str(raw.get("id", "default")).strip() or "default"
            players_by_seat[seat] = player_id

    entries: list[RosterEntry] = []
    for seat, seat_label in enumerate(SEAT_LABELS):
        player_id = players_by_seat.get(seat, "default")
        profile = load_profile_data(player_id) if player_id != "default" else None
        entries.append(
            RosterEntry(
                seat=seat,
                seat_label=seat_label,
                player_id=player_id,
                display_name=(
                    str(profile.get("name", player_id))
                    if profile
                    else ("默认 AI" if player_id == "default" else player_id)
                ),
                mode_label="角色配置" if player_id != "default" else "Dry-run",
                profile_found=profile is not None or player_id == "default",
            ),
        )

    return tuple(entries)


def _extract_match_result(
    events: list[dict[str, Any]],
) -> tuple[tuple[int, int, int, int] | None, tuple[int, int, int, int] | None]:
    """从 replay 事件中提取终局名次和分数。"""
    for event in reversed(events):
        if not isinstance(event, dict) or event.get("event_type") != "match_end":
            continue

        ranking_raw = event.get("ranking")
        final_scores_raw = event.get("final_scores")
        ranking = None
        final_scores = None

        if isinstance(ranking_raw, list) and len(ranking_raw) == 4:
            try:
                ranking = tuple(int(x) for x in ranking_raw)
            except (TypeError, ValueError):
                ranking = None

        if isinstance(final_scores_raw, list) and len(final_scores_raw) == 4:
            try:
                final_scores = tuple(int(x) for x in final_scores_raw)
            except (TypeError, ValueError):
                final_scores = None

        return ranking, final_scores

    return None, None


def load_replay_summary(path: Path) -> ReplaySummary:
    """读取单个牌谱摘要。"""
    modified_at = datetime.fromtimestamp(path.stat().st_mtime)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ReplaySummary(
            path=path,
            stem=path.stem,
            modified_at=modified_at,
            seed=None,
            stopped_reason="parse_error",
            final_phase="unknown",
            action_count=0,
            step_count=0,
            ranking_by_seat=None,
            final_scores=None,
        )

    events = data.get("events", [])
    ranking, final_scores = _extract_match_result(events if isinstance(events, list) else [])

    seed = data.get("seed")
    try:
        seed_value = int(seed) if seed is not None else None
    except (TypeError, ValueError):
        seed_value = None

    actions = data.get("actions", [])
    action_count = len(actions) if isinstance(actions, list) else 0

    steps = data.get("steps", 0)
    try:
        step_count = int(steps)
    except (TypeError, ValueError):
        step_count = 0

    return ReplaySummary(
        path=path,
        stem=path.stem,
        modified_at=modified_at,
        seed=seed_value,
        stopped_reason=str(data.get("stopped_reason", "unknown")),
        final_phase=str(data.get("final_phase", "unknown")),
        action_count=action_count,
        step_count=step_count,
        ranking_by_seat=ranking,
        final_scores=final_scores,
    )


def load_recent_replay_summaries(
    replay_dir: Path = Path("logs/replay"),
    *,
    limit: int = 20,
) -> tuple[ReplaySummary, ...]:
    """读取最近的 replay 摘要。"""
    if not replay_dir.exists():
        return ()

    replay_files = sorted(
        replay_dir.glob("*.json"),
        key=lambda replay_path: replay_path.stat().st_mtime,
        reverse=True,
    )[:limit]
    return tuple(load_replay_summary(path) for path in replay_files)


def build_home_snapshot(
    *,
    config_path: Path = KERNEL_CONFIG_PATH,
    players_dir: Path = PLAYERS_DIR,
    replay_dir: Path = Path("logs/replay"),
    replay_limit: int = 3,
) -> HomeSnapshot:
    """组装主菜单首页所需数据。"""
    return HomeSnapshot(
        model=load_model_summary(config_path),
        roster=load_roster_entries(config_path, players_dir),
        recent_replays=load_recent_replay_summaries(replay_dir, limit=replay_limit),
    )
