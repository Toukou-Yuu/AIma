"""命令行：``python -m llm``。"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from kernel.replay import ReplayError, replay_from_actions
from kernel.replay_json import actions_from_match_log
from llm.config import load_llm_config
from llm.protocol import build_client
from llm.runner import run_llm_match


def _print_match_results_from_state(state, players: list[dict[str, Any]] | None = None) -> None:
    """打印对局结束后的四家成绩（从 final_state 读取）。"""
    from kernel.table.model import PrevailingWind

    table = state.table
    final_scores = table.scores
    final_dealer = table.dealer_seat

    # 计算排名
    sorted_seats = sorted(
        range(4),
        key=lambda s: (-final_scores[s], (s - final_dealer) % 4)
    )

    # 获取玩家名字
    player_names = {}
    if players:
        for p in players:
            seat = p.get("seat")
            player_id = p.get("id")
            if seat is not None and player_id:
                player_names[seat] = player_id

    print("\n" + "=" * 50)
    print("对局结束 - 最终成绩")
    print("=" * 50)
    print(f"{'排名':<6}{'座位':<8}{'玩家':<12}{'分数':>10}")
    print("-" * 50)

    for rank, seat in enumerate(sorted_seats, 1):
        name = player_names.get(seat, f"Player{seat}")
        seat_name = f"S{seat}"
        score = final_scores[seat]
        print(f"{rank}位{'':<4}{seat_name:<8}{name:<12}{score:>10,}")

    print("=" * 50 + "\n")

# 项目根相对路径：对局牌谱与调试文本日志共用同一文件名（stem）关联
_LOG_REPLAY_DIR = Path("logs") / "replay"
_LOG_DEBUG_DIR = Path("logs") / "debug"
_LOG_SIMPLE_DIR = Path("logs") / "simple"
_STEM_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$")


class _FlushingFileHandler(logging.FileHandler):
    """每条日志后 flush，进程被中断时尽量多落盘。"""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


class _HideHttpxOnConsole(logging.Filter):
    """控制台不显示 httpx/httpcore 行；会话日志下它们仍写入文件 Handler。"""

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name
        return not (name.startswith("httpx") or name.startswith("httpcore"))


def _resolve_log_stem(session_arg: str | None) -> str | None:
    """``None`` 表示不写会话日志；``\"\"`` 表示自动生成时间戳 stem。"""
    if session_arg is None:
        return None
    if session_arg == "":
        return datetime.now().strftime("%Y%m%d-%H%M%S")
    if not _STEM_SAFE.match(session_arg):
        msg = (
            "log-session stem 仅允许字母数字及 ._-，首字符须为字母或数字，"
            f"收到: {session_arg!r}"
        )
        raise ValueError(msg)
    return session_arg


def _setup_session_file_logging(debug_log: Path) -> None:
    """向根 logger 追加文件 Handler（与控制台并存）。

    文件接收 DEBUG 及以上；控制台仍保持 INFO（由下方 ``_cap_console_log_level`` 处理）。
    """
    debug_log.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fh = _FlushingFileHandler(debug_log, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"),
    )
    root.addHandler(fh)


def _allow_httpx_info_to_file_only() -> None:
    """httpx 的 HTTP 行写入文件；控制台通过 Filter 隐藏。"""
    logging.getLogger("httpx").setLevel(logging.INFO)
    flt = _HideHttpxOnConsole()
    for h in logging.getLogger().handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            h.addFilter(flt)


def _cap_console_handlers_info() -> None:
    """``basicConfig`` 的 stderr 控制台只打到 INFO，避免根 logger 降到 DEBUG 后刷屏。"""
    for h in logging.getLogger().handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            h.setLevel(logging.INFO)


def _load_dotenv_if_available() -> None:
    """若已安装 ``python-dotenv``，从当前工作目录加载 ``.env``（不覆盖已有环境变量）。"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _load_yaml_config(path: str | None) -> dict[str, Any]:
    """加载 YAML 配置文件，若路径为空或文件不存在返回空 dict。"""
    if path is None:
        return {}
    p = Path(path)
    if not p.exists():
        print(f"配置文件不存在: {p}", file=sys.stderr)
        return {}
    try:
        import yaml
    except ImportError:
        print("需要 PyYAML: pip install pyyaml", file=sys.stderr)
        return {}
    try:
        content = p.read_text(encoding="utf-8")
        cfg = yaml.safe_load(content)
        return cfg if isinstance(cfg, dict) else {}
    except Exception as e:
        print(f"配置文件解析失败: {e}", file=sys.stderr)
        return {}


def _merge_config(
    yaml_cfg: dict[str, Any],
    cli_args: argparse.Namespace,
) -> argparse.Namespace:
    """合并 YAML 配置与 CLI 参数，CLI 优先级更高。

    CLI 参数使用 None 作为 sentinel：None 表示"未设置"，使用 YAML 默认值；
    非 None 表示"用户显式设置"，使用 CLI 值。
    """
    # 从 YAML 提取默认值
    match_end_cfg = yaml_cfg.get("match", {}).get("match_end", {})
    yaml_defaults = {
        "seed": yaml_cfg.get("match", {}).get("seed", 0),
        "match_end": {
            "type": match_end_cfg.get("type", "hands"),
            "value": match_end_cfg.get("value", 8),
            "allow_negative": match_end_cfg.get("allow_negative", False),
        },
        "dry_run": yaml_cfg.get("debug", {}).get("dry_run", False),
        "log_json": yaml_cfg.get("logging", {}).get("json"),
        "log_session": yaml_cfg.get("logging", {}).get("session"),
        "verbose": yaml_cfg.get("debug", {}).get("verbose", False),
        "request_delay": yaml_cfg.get("llm", {}).get("request_delay", 0.5),
        "watch": yaml_cfg.get("watch", {}).get("enabled", False),
        "watch_delay": yaml_cfg.get("watch", {}).get("delay", 0.3),
        "max_history_rounds": yaml_cfg.get("llm", {}).get("max_history_rounds", 10),
        "clear_history_per_hand": yaml_cfg.get("llm", {}).get("clear_history_per_hand", False),
        "session_audit": yaml_cfg.get("logging", {}).get("session_audit", False),
        "show_reason": yaml_cfg.get("watch", {}).get("show_reason", True),
        "players": yaml_cfg.get("match", {}).get("players") or yaml_cfg.get("players"),
        "enable_conversation_logging": yaml_cfg.get("llm", {}).get("conversation_logging", {}).get("enabled", False),
    }

    # 合并：CLI 非 None → 用 CLI；否则用 YAML
    result = argparse.Namespace()
    for key, yaml_val in yaml_defaults.items():
        cli_val = getattr(cli_args, key, None)
        setattr(result, key, cli_val if cli_val is not None else yaml_val)

    # 特殊处理 --max-hands：转换为 match_end 格式
    if getattr(cli_args, "max_hands", None) is not None:
        result.match_end = {
            "type": "hands",
            "value": cli_args.max_hands,
            "allow_negative": False,
        }

    # 特殊处理：若 log_session 非 null，自动启用 session_audit
    if result.log_session is not None:
        result.session_audit = True

    # 特殊处理 replay：无 YAML 默认值，仅 CLI 显式设置时才有
    result.replay = getattr(cli_args, "replay", None)

    # 特殊处理 players：CLI 字符串格式转为列表
    if isinstance(result.players, str) and result.players:
        player_ids = result.players.split(",")
        result.players = [
            {"id": pid.strip() if pid.strip() else "default", "seat": i}
            for i, pid in enumerate(player_ids[:4])
        ]
        for i in range(len(result.players), 4):
            result.players.append({"id": "default", "seat": i})

    return result


def _cmd_show_stats(player_id: str) -> int:
    """显示玩家统计."""
    from llm.agent.stats import load_stats
    stats = load_stats(player_id)

    print(f"\n【{player_id} 统计数据】")
    print(f"累计对局: {stats.total_games}场")
    print(f"累计局数: {stats.total_hands}局")
    print(f"\n和了: {stats.wins}次 ({stats.win_rate:.1%})")
    print(f"放铳: {stats.deal_ins}次 ({stats.deal_in_rate:.1%})")
    print(f"立直: {stats.riichi_count}次 ({stats.riichi_rate:.1%})")
    if stats.riichi_count > 0:
        print(f"  └ 立直成功: {stats.riichi_wins}次 ({stats.riichi_success_rate:.1%})")
        print(f"  └ 立直放铳: {stats.riichi_deal_ins}次 ({stats.riichi_deal_in_rate:.1%})")
    print(f"\n平均顺位: {stats.avg_placement:.2f}")
    print(f"场均得点: {stats.avg_points_per_game:+.1f}")
    print(f"\n顺位分布:")
    print(f"  一位: {stats.first_place_count} ({stats.first_place_count/stats.total_games:.1%})")
    print(f"  二位: {stats.second_place_count} ({stats.second_place_count/stats.total_games:.1%})")
    print(f"  三位: {stats.third_place_count} ({stats.third_place_count/stats.total_games:.1%})")
    print(f"  四位: {stats.fourth_place_count} ({stats.fourth_place_count/stats.total_games:.1%})")
    return 0


def _cmd_replay(path: str) -> int:
    """从牌谱 JSON 执行 ``replay_from_actions``，打印终局摘要。"""
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    try:
        actions = actions_from_match_log(data)
    except (ValueError, KeyError, TypeError) as e:
        print(f"牌谱解析失败: {e}", file=sys.stderr)
        return 1
    try:
        final, outcomes = replay_from_actions(actions)
    except ReplayError as e:
        print(f"回放失败: {e}", file=sys.stderr)
        return 1
    n_events = sum(len(o.events) for o in outcomes)
    print(
        f"replay_ok phase={final.phase.value} "
        f"actions={len(actions)} kernel_events={n_events}"
    )
    return 0


def _cmd_watch_replay(path: str, delay: float) -> int:
    """从牌谱 JSON 实时观战（Rich）。"""
    try:
        from ui.terminal import LiveMatchViewer
    except ImportError as e:
        print(f"需要 rich: pip install rich ({e})", file=sys.stderr)
        return 2

    viewer = LiveMatchViewer(delay=delay, show_reason=False)
    viewer.run_from_replay_file(path, delay=delay)
    return 0


def _cmd_watch_dry_run(
    seed: int,
    delay: float,
    match_end: dict[str, Any] | None = None,
    dry_run: bool = True,
    max_history_rounds: int = 10,
    clear_history_per_hand: bool = False,
    show_reason: bool = True,
    llm_override: dict[str, Any] | None = None,
    players: list[dict[str, Any]] | None = None,
    kernel_config_path: str = "configs/aima_kernel.yaml",
    log_session: str | None = None,
    session_audit: bool = False,
    enable_conversation_logging: bool = False,
) -> int:
    """实时观战（Rich + dry-run 或真实 LLM 模式）。"""
    # 观战模式下，控制台只显示 WARNING 及以上级别日志，避免干扰 Rich UI
    for h in logging.getLogger().handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            h.setLevel(logging.WARNING)

    # 设置日志文件
    simple_log_file: TextIO | None = None
    if log_session is not None:
        log_stem = _resolve_log_stem(log_session)
        if log_stem:
            _LOG_REPLAY_DIR.mkdir(parents=True, exist_ok=True)
            _LOG_SIMPLE_DIR.mkdir(parents=True, exist_ok=True)
            _LOG_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            debug_session_path = _LOG_DEBUG_DIR / f"{log_stem}.log"
            _setup_session_file_logging(debug_session_path)
            simple_session_path = _LOG_SIMPLE_DIR / f"{log_stem}.txt"
            simple_log_file = simple_session_path.open("w", encoding="utf-8")
            logging.info(
                "观战日志：调试 logs/debug/%s.log | 可读 logs/simple/%s.txt",
                log_stem,
                log_stem,
            )

    try:
        from ui.terminal import LiveMatchCallback
        from llm.runner import run_llm_match
        from llm.agent.profile import load_profile
    except ImportError as e:
        print(f"需要 rich: pip install rich ({e})", file=sys.stderr)
        if simple_log_file:
            simple_log_file.close()
        return 2

    # 加载玩家名字
    player_names: dict[int, str] = {}
    if players:
        for p in players:
            seat = p["seat"]
            player_id = p.get("id")
            if player_id and player_id != "default":
                profile = load_profile(player_id)
                player_names[seat] = profile.name if profile else player_id
            else:
                player_names[seat] = "默认"

    client = None
    llm_cfg = None
    if not dry_run:
        llm_cfg = load_llm_config(
            config_path=kernel_config_path,
            override_cfg=llm_override,
        )
        if llm_cfg is None:
            print(
                "未设置 API Key（请在 configs/aima_kernel.yaml 中设置 api_key）。"
                "使用 --dry-run 可本地试跑。",
                file=sys.stderr,
            )
            return 2
        client = build_client(llm_cfg)

    from llm.config import MatchEndCondition

    # 构建 MatchEndCondition
    if match_end is None:
        me = MatchEndCondition(type="hands", value=8, allow_negative=False)
    else:
        me = MatchEndCondition(
            type=match_end.get("type", "hands"),
            value=match_end.get("value", 8),
            allow_negative=match_end.get("allow_negative", False),
        )

    with LiveMatchCallback(
        delay=delay,
        show_reason=show_reason and not dry_run,
        target_hands=me.value if me else 8,
    ) as callback:
        # 设置玩家名字
        if player_names:
            callback.set_player_names(player_names)
        rr = run_llm_match(
            seed=seed,
            match_end=me,
            client=client,
            dry_run=dry_run,
            verbose=False,
            session_audit=session_audit,
            simple_log_file=simple_log_file,
            request_delay_seconds=0.0 if dry_run else delay,
            on_step_callback=callback.on_step,
            max_history_rounds=max_history_rounds,
            clear_history_on_new_hand=clear_history_per_hand,
            players=players,
            system_prompt=llm_cfg.system_prompt if llm_cfg else None,
            prompt_format=llm_cfg.prompt_format if llm_cfg else "natural",
            enable_conversation_logging=enable_conversation_logging,
        )
        print(
            f"\nplayer_steps={rr.player_steps} kernel_steps={rr.kernel_steps} "
            f"reason={rr.stopped_reason!r} phase={rr.final_state.phase.value}"
        )

    # 保存 replay 日志
    if log_session is not None:
        import json
        log_stem = _resolve_log_stem(log_session)
        if log_stem:
            replay_path = _LOG_REPLAY_DIR / f"{log_stem}.json"
            payload = json.dumps(rr.as_match_log(), ensure_ascii=False, indent=2)
            replay_path.write_text(payload, encoding="utf-8")
            print(f"\n对局日志: {replay_path}")

    # 显示最终成绩（在 Live 退出后，避免被刷新掉）
    _print_match_results_from_state(rr.final_state, players)

    if simple_log_file:
        simple_log_file.close()

    return 0


def main(argv: list[str] | None = None) -> int:
    _load_dotenv_if_available()
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")
    _cap_console_handlers_info()
    # 避免 httpx 每条请求刷 INFO，盖住本程序摘要；需要调试 HTTP 时再改回 DEBUG
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # 单一 parser：所有参数默认 None（sentinel），表示"未设置"
    # config 路径有默认值，其他参数通过 YAML 或 CLI 设置
    p = argparse.ArgumentParser(description="AIma LLM 牌手跑局（内核闭环）")
    p.add_argument(
        "--config",
        metavar="PATH",
        default="configs/aima_kernel.yaml",
        help="YAML 配置文件路径（默认 configs/aima_kernel.yaml）",
    )
    p.add_argument("--seed", type=int, default=None, help="首局洗牌种子（默认 0）")
    p.add_argument(
        "--max-player-steps",
        type=int,
        default=None,
        help="最大玩家决策步数（默认 500，不含局间洗牌和自动过）",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="不调用 API；每步取 legal_actions 首项（确定性）",
    )
    p.add_argument(
        "--log-json",
        metavar="PATH",
        default=None,
        help="跑局结束后将牌谱写入指定路径的 JSON（与 --log-session 可同用）",
    )
    p.add_argument(
        "--log-session",
        nargs="?",
        const="",
        default=None,
        metavar="STEM",
        help=(
            "写入配对日志：logs/replay/{STEM}.json（对局/牌谱）、"
            "logs/debug/{STEM}.log（调试）、"
            "logs/simple/{STEM}.txt（简体中文可读）；省略 STEM 则用时间戳如 20260324-153045"
        ),
    )
    p.add_argument(
        "--replay",
        metavar="PATH",
        help="仅从牌谱 JSON 重放（不跑 LLM、不请求 API）",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=None,
        help="每步 apply 后向 stderr 打印阶段摘要（对局进度）",
    )
    p.add_argument(
        "--request-delay",
        type=float,
        default=None,
        metavar="SEC",
        help="每次调用 LLM API 前的间隔秒数（默认 0.5）",
    )
    p.add_argument(
        "--watch",
        action="store_true",
        default=None,
        help="实时终端观战（需要 rich）；与 --dry-run 同用可看实时演示",
    )
    p.add_argument(
        "--watch-delay",
        type=float,
        default=None,
        metavar="SEC",
        help="--watch 模式每步间隔秒数（默认 0.3）",
    )
    p.add_argument(
        "--max-history-rounds",
        type=int,
        default=None,
        metavar="N",
        help="LLM 每席保留的最大对话轮数（默认 10，设为 0 则禁用历史）",
    )
    p.add_argument(
        "--clear-history-per-hand",
        action="store_true",
        default=None,
        help="每局开始时清空该席的历史消息（默认跨局保留）",
    )
    p.add_argument(
        "--players",
        type=str,
        default=None,
        metavar="ID_LIST",
        help="指定对战玩家，格式: id0,id1,id2,id3（对应座位0-3），如: aggressive_bot_v1,defensive_bot_v1,default,default",
    )
    p.add_argument(
        "--max-hands",
        type=int,
        default=None,
        metavar="N",
        help="对局局数（4=东风战, 8=半庄战, 默认使用配置文件）",
    )
    p.add_argument(
        "--show-stats",
        type=str,
        default=None,
        metavar="PLAYER_ID",
        help="显示指定玩家的统计数据",
    )
    args = p.parse_args(argv)

    # 加载 YAML 配置（config 路径总有值，要么默认要么用户指定）
    yaml_cfg = _load_yaml_config(args.config)
    kernel_config_path = args.config

    # 合并配置（CLI 覆盖 YAML）
    cfg = _merge_config(yaml_cfg, args)

    # --show-stats 模式
    if getattr(args, "show_stats", None):
        return _cmd_show_stats(args.show_stats)

    # --watch 模式优先处理
    if cfg.watch:
        if cfg.replay:
            # 从牌谱实时观战
            return _cmd_watch_replay(cfg.replay, cfg.watch_delay)
        else:
            # 实时观战（dry-run 或真实 LLM）
            # 构建对局配置的 llm 覆盖
            match_llm_override = yaml_cfg.get("llm", {})
            return _cmd_watch_dry_run(
                cfg.seed,
                cfg.watch_delay,
                match_end=cfg.match_end,
                dry_run=cfg.dry_run,
                max_history_rounds=cfg.max_history_rounds,
                clear_history_per_hand=cfg.clear_history_per_hand,
                show_reason=cfg.show_reason,
                llm_override=match_llm_override,
                players=cfg.players,
                kernel_config_path=kernel_config_path,
                log_session=cfg.log_session,
                session_audit=cfg.session_audit,
                enable_conversation_logging=cfg.enable_conversation_logging,
            )

    if cfg.replay:
        return _cmd_replay(cfg.replay)

    try:
        log_stem = _resolve_log_stem(cfg.log_session)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    replay_session_path: Path | None = None
    simple_session_path: Path | None = None
    if log_stem is not None:
        _LOG_REPLAY_DIR.mkdir(parents=True, exist_ok=True)
        _LOG_SIMPLE_DIR.mkdir(parents=True, exist_ok=True)
        replay_session_path = _LOG_REPLAY_DIR / f"{log_stem}.json"
        simple_session_path = _LOG_SIMPLE_DIR / f"{log_stem}.txt"
        debug_session_path = _LOG_DEBUG_DIR / f"{log_stem}.log"
        _setup_session_file_logging(debug_session_path)
        _cap_console_handlers_info()
        _allow_httpx_info_to_file_only()
        logging.info(
            "会话日志：对局 logs/replay/%s.json"
            "（须跑完全程后才写入；内容为内核 replay wire，非读谱战报）| "
            "调试 logs/debug/%s.log | 可读 logs/simple/%s.txt",
            log_stem,
            log_stem,
            log_stem,
        )

    client = None
    llm_cfg = None
    if not cfg.dry_run:
        llm_cfg = load_llm_config(
            config_path=kernel_config_path,
            override_cfg=yaml_cfg.get("llm"),
        )
        if llm_cfg is None:
            print(
                "未设置 API Key（请在 configs/aima_kernel.yaml 中设置 api_key）。"
                "使用 --dry-run 可本地试跑。",
                file=sys.stderr,
            )
            return 2
        client = build_client(llm_cfg)

    from llm.config import MatchEndCondition

    # 构建 MatchEndCondition
    if cfg.match_end is None:
        me = MatchEndCondition(type="hands", value=8, allow_negative=False)
    else:
        me = MatchEndCondition(
            type=cfg.match_end.get("type", "hands"),
            value=cfg.match_end.get("value", 8),
            allow_negative=cfg.match_end.get("allow_negative", False),
        )

    if simple_session_path is not None:
        with simple_session_path.open("w", encoding="utf-8") as simple_fp:
            rr = run_llm_match(
                seed=cfg.seed,
                match_end=me,
                client=client,
                dry_run=cfg.dry_run,
                verbose=cfg.verbose,
                session_audit=cfg.session_audit or log_stem is not None,
                simple_log_file=simple_fp,
                request_delay_seconds=0.0 if cfg.dry_run else cfg.request_delay,
                max_history_rounds=cfg.max_history_rounds,
                clear_history_on_new_hand=cfg.clear_history_per_hand,
                players=cfg.players,
                system_prompt=llm_cfg.system_prompt if llm_cfg else None,
                prompt_format=llm_cfg.prompt_format if llm_cfg else "natural",
                enable_conversation_logging=cfg.enable_conversation_logging,
            )
    else:
        rr = run_llm_match(
            seed=cfg.seed,
            match_end=me,
            client=client,
            dry_run=cfg.dry_run,
            verbose=cfg.verbose,
            session_audit=cfg.session_audit or log_stem is not None,
            simple_log_file=None,
            request_delay_seconds=0.0 if cfg.dry_run else cfg.request_delay,
            max_history_rounds=cfg.max_history_rounds,
            clear_history_on_new_hand=cfg.clear_history_per_hand,
            players=cfg.players,
            system_prompt=llm_cfg.system_prompt if llm_cfg else None,
            prompt_format=llm_cfg.prompt_format if llm_cfg else "natural",
            enable_conversation_logging=cfg.enable_conversation_logging,
        )
    print(
        f"player_steps={rr.player_steps} kernel_steps={rr.kernel_steps} "
        f"reason={rr.stopped_reason!r} phase={rr.final_state.phase.value}"
    )
    if log_stem is not None:
        logging.info(
            "run_finished player_steps=%s kernel_steps=%s reason=%s phase=%s actions=%s events=%s",
            rr.player_steps,
            rr.kernel_steps,
            rr.stopped_reason,
            rr.final_state.phase.value,
            len(rr.actions_wire),
            len(rr.events_wire),
        )
    payload = json.dumps(rr.as_match_log(), ensure_ascii=False, indent=2)
    if cfg.log_json:
        pth = Path(cfg.log_json)
        pth.parent.mkdir(parents=True, exist_ok=True)
        pth.write_text(payload, encoding="utf-8")
    if replay_session_path is not None:
        replay_session_path.write_text(payload, encoding="utf-8")
        print(
            f"对局日志: {replay_session_path.as_posix()} | "
            f"调试日志: {(_LOG_DEBUG_DIR / f'{log_stem}.log').as_posix()} | "
            f"可读日志: {simple_session_path.as_posix()}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
