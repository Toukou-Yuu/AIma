"""交互层的数据装配器。"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from llm.config import load_kernel_config
from ui.interactive.utils import KERNEL_CONFIG_PATH, PLAYERS_DIR, load_profile_data

SEAT_LABELS = ("东家", "南家", "西家", "北家")
_PLACEHOLDER_KEYS = {"", "your-api-key", "your-api-key-here"}


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

    @property
    def headline(self) -> str:
        """面向 UI 的主标题。"""
        if not self.configured:
            return "未完成模型配置"
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
        """面向 UI 的结束状态。"""
        reason = self.stopped_reason or ""
        if self.ranking_by_seat:
            return "正常结束"
        if reason.startswith("hands_completed"):
            return "局数结束"
        if "failed" in reason or "error" in reason:
            return "异常结束"
        if "max_player_steps" in reason:
            return "步数截断"
        return "未完成"

    @property
    def reason_label(self) -> str:
        """结束原因简写。"""
        reason = self.stopped_reason or "unknown"
        if reason.startswith("hands_completed:"):
            count = reason.split(":", 1)[1]
            return f"{count}局完成"
        if reason.startswith("negative_score:"):
            return "出现负分"
        if reason.startswith("begin_round_failed:"):
            return "开局失败"
        if reason.startswith("illegal_action:"):
            return "非法动作"
        if reason.startswith("max_player_steps"):
            return "达到步数上限"
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


_PROBE_CACHE: dict[tuple[str, str, str, str], tuple[float, tuple[str, str, str]]] = {}
_PROBE_IN_FLIGHT: set[tuple[str, str, str, str]] = set()
_PROBE_LOCK = threading.Lock()
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


def _probe_openai_connection(
    *,
    base_url: str,
    api_key: str,
    timeout_sec: float,
) -> tuple[str, str, str]:
    """探测 OpenAI 兼容接口。"""
    import httpx

    url = base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=timeout_sec) as client:
        response = client.get(url, headers=headers)
    if response.status_code == 200:
        return ("已连接", "green", "接口可达")
    if response.status_code in (401, 403):
        return ("鉴权失败", "red", f"HTTP {response.status_code}")
    return ("连接异常", "yellow", f"HTTP {response.status_code}")


def _probe_anthropic_connection(
    *,
    base_url: str,
    api_key: str,
    timeout_sec: float,
) -> tuple[str, str, str]:
    """探测 Anthropic 接口。"""
    import httpx

    url = base_url.rstrip("/") + "/v1/models"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    with httpx.Client(timeout=timeout_sec) as client:
        response = client.get(url, headers=headers)
    if response.status_code == 200:
        return ("已连接", "green", "接口可达")
    if response.status_code in (401, 403):
        return ("鉴权失败", "red", f"HTTP {response.status_code}")
    return ("连接异常", "yellow", f"HTTP {response.status_code}")


def _probe_connection_status(
    *,
    provider: str,
    base_url: str,
    api_key: str,
    configured: bool,
    timeout_sec: float = 1.5,
) -> tuple[str, str, str]:
    """探测当前配置是否已连接到 LLM。"""
    if not configured:
        return ("未连接", "yellow", "缺少 API Key")

    try:
        if provider == "anthropic":
            result = _probe_anthropic_connection(
                base_url=base_url,
                api_key=api_key,
                timeout_sec=timeout_sec,
            )
        else:
            result = _probe_openai_connection(
                base_url=base_url,
                api_key=api_key,
                timeout_sec=timeout_sec,
            )
    except ImportError:
        result = ("未检查", "yellow", "缺少 httpx")
    except Exception as exc:
        try:
            import httpx
        except ImportError:
            result = ("未检查", "yellow", exc.__class__.__name__)
        else:
            if isinstance(exc, httpx.TimeoutException):
                result = ("未连接", "yellow", "探测超时")
            elif isinstance(exc, httpx.HTTPError):
                result = ("未连接", "yellow", exc.__class__.__name__)
            else:
                result = ("未连接", "yellow", exc.__class__.__name__)
    return result


def _get_cached_probe_status(
    cache_key: tuple[str, str, str, str],
) -> tuple[str, str, str] | None:
    """读取已缓存的探测结果。"""
    with _PROBE_LOCK:
        cached = _PROBE_CACHE.get(cache_key)
        if cached is None:
            return None
        return cached[1]


def _store_probe_status(
    cache_key: tuple[str, str, str, str],
    result: tuple[str, str, str],
) -> None:
    """写入探测缓存。"""
    with _PROBE_LOCK:
        _PROBE_CACHE[cache_key] = (time.monotonic(), result)
        _PROBE_IN_FLIGHT.discard(cache_key)


def _schedule_probe_refresh(
    *,
    cache_key: tuple[str, str, str, str],
    provider: str,
    base_url: str,
    api_key: str,
    configured: bool,
) -> None:
    """后台刷新探测结果，不阻塞页面渲染。"""
    with _PROBE_LOCK:
        if cache_key in _PROBE_IN_FLIGHT:
            return
        _PROBE_IN_FLIGHT.add(cache_key)

    def _worker() -> None:
        try:
            result = _probe_connection_status(
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                configured=configured,
            )
            _store_probe_status(cache_key, result)
        except Exception:
            _store_probe_status(cache_key, ("未连接", "yellow", "探测失败"))

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


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
    seat0 = seats.get("seat0", {}) if isinstance(seats.get("seat0"), dict) else {}
    profile_name = str(seat0.get("profile", ""))
    profile = profiles.get(profile_name)
    profile_cfg = profile if isinstance(profile, dict) else {}

    api_key = str(profile_cfg.get("api_key", "")).strip()
    configured = api_key not in _PLACEHOLDER_KEYS
    provider = str(profile_cfg.get("provider", ""))
    base_url = str(profile_cfg.get("base_url", ""))
    cache_key = (provider, base_url, api_key, str(configured))
    cached_probe = _get_cached_probe_status(cache_key)
    _schedule_probe_refresh(
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

    return ModelSummary(
        provider_label=_provider_label(
            provider,
            base_url,
        ),
        model=str(profile_cfg.get("model", "--")),
        configured=configured,
        prompt_format=str(llm_cfg.get("prompt_format", "--")),
        conversation_logging=bool(
            (llm_cfg.get("conversation_logging") or {}).get("enabled", False),
        ),
        note="API Key 已配置" if configured else "缺少 API Key",
        connection_label=connection_label,
        connection_style=connection_style,
        connection_note=connection_note,
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
