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

    只合并 CLI 显式指定的参数（非 None 或布尔值已设置）。
    """
    # YAML 默认值映射
    defaults = {
        "seed": yaml_cfg.get("match", {}).get("seed", 0),
        "max_player_steps": yaml_cfg.get("match", {}).get("max_player_steps", 500),
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
        "players": yaml_cfg.get("match", {}).get("players"),
    }

    # 显式指定的 CLI 参数覆盖 YAML
    result = argparse.Namespace()
    for key, default_val in defaults.items():
        cli_val = getattr(cli_args, key, None)
        # 对于布尔值，需要检查是否通过命令行显式设置（argparse 无法直接区分）
        # 这里简化处理：CLI 非 None 值覆盖
        if cli_val is not None or (isinstance(default_val, bool) and key in sys.argv):
            setattr(result, key, cli_val)
        else:
            setattr(result, key, default_val)

    # 特殊处理：若 log_session 非 null，自动启用 session_audit
    if result.log_session is not None:
        result.session_audit = True

    # 特殊处理 replay（没有默认值，CLI 显式指定才覆盖）
    result.replay = getattr(cli_args, "replay", None)

    # 特殊处理 players：CLI 字符串格式转为列表
    if isinstance(result.players, str) and result.players:
        # CLI 格式: "id0,id1,id2,id3"
        player_ids = result.players.split(",")
        result.players = [
            {"id": pid.strip() if pid.strip() else "default", "seat": i}
            for i, pid in enumerate(player_ids[:4])
        ]
        # 补充剩余座位为 default
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
        from ui.terminal_rich import LiveMatchViewer
    except ImportError as e:
        print(f"需要 rich: pip install rich ({e})", file=sys.stderr)
        return 2

    viewer = LiveMatchViewer(delay=delay, show_reason=False)
    viewer.run_from_replay_file(path, delay=delay)
    return 0


def _cmd_watch_dry_run(
    seed: int,
    max_player_steps: int,
    delay: float,
    dry_run: bool = True,
    max_history_rounds: int = 10,
    clear_history_per_hand: bool = False,
    show_reason: bool = True,
    timeout_sec: float | None = None,
    max_tokens: int | None = None,
    players: list[dict[str, Any]] | None = None,
) -> int:
    """实时观战（Rich + dry-run 或真实 LLM 模式）。"""
    try:
        from ui.terminal_rich import LiveMatchCallback
        from llm.runner import run_llm_match
        from llm.agent.profile import load_profile
    except ImportError as e:
        print(f"需要 rich: pip install rich ({e})", file=sys.stderr)
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
    if not dry_run:
        llm_cfg = load_llm_config(
            timeout_sec=timeout_sec,
            max_tokens=max_tokens,
        )
        if llm_cfg is None:
            print(
                "未设置 API Key（见 AIMA_OPENAI_* / AIMA_ANTHROPIC_*）。"
                "使用 --dry-run 可本地试跑。",
                file=sys.stderr,
            )
            return 2
        client = build_client(llm_cfg)

    with LiveMatchCallback(
        delay=delay,
        show_reason=show_reason and not dry_run,
        max_player_steps=max_player_steps,
    ) as callback:
        # 设置玩家名字
        if player_names:
            callback.set_player_names(player_names)
        rr = run_llm_match(
            seed=seed,
            max_player_steps=max_player_steps,
            client=client,
            dry_run=dry_run,
            verbose=False,
            session_audit=True,  # 启用审计日志以查看 prompt
            request_delay_seconds=0.0 if dry_run else delay,
            on_step_callback=callback.on_step,
            max_history_rounds=max_history_rounds,
            clear_history_on_new_hand=clear_history_per_hand,
            players=None,
        )
        print(
            f"\nplayer_steps={rr.player_steps} kernel_steps={rr.kernel_steps} "
            f"reason={rr.stopped_reason!r} phase={rr.final_state.phase.value}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    _load_dotenv_if_available()
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")
    _cap_console_handlers_info()
    # 避免 httpx 每条请求刷 INFO，盖住本程序摘要；需要调试 HTTP 时再改回 DEBUG
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # 第一遍解析：只取 --config（帮助信息会在第二遍完整显示）
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", metavar="PATH", help="YAML 配置文件路径")
    pre_args, remaining = pre_parser.parse_known_args(argv)

    # 加载 YAML 配置
    yaml_cfg = _load_yaml_config(pre_args.config)

    # 第二遍解析：完整参数列表
    p = argparse.ArgumentParser(description="AIma LLM 牌手跑局（内核闭环）")
    p.add_argument("--config", metavar="PATH", help="YAML 配置文件路径")
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
        "--show-stats",
        type=str,
        default=None,
        metavar="PLAYER_ID",
        help="显示指定玩家的统计数据",
    )
    args = p.parse_args(argv)

    # 合并配置（CLI 覆盖 YAML）
    cfg = _merge_config(yaml_cfg, args)

    # Phase 4: --show-stats 模式
    if getattr(args, "show_stats", None):
        return _cmd_show_stats(args.show_stats)

    # --watch 模式优先处理
    if cfg.watch:
        if cfg.replay:
            # 从牌谱实时观战
            return _cmd_watch_replay(cfg.replay, cfg.watch_delay)
        else:
            # 实时观战（dry-run 或真实 LLM）
            return _cmd_watch_dry_run(
                cfg.seed,
                cfg.max_player_steps,
                cfg.watch_delay,
                dry_run=cfg.dry_run,
                max_history_rounds=cfg.max_history_rounds,
                clear_history_per_hand=cfg.clear_history_per_hand,
                show_reason=cfg.show_reason,
                timeout_sec=yaml_cfg.get("llm", {}).get("timeout_sec"),
                max_tokens=yaml_cfg.get("llm", {}).get("max_tokens"),
                players=cfg.players,
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
    if not cfg.dry_run:
        llm_cfg = load_llm_config(
            timeout_sec=yaml_cfg.get("llm", {}).get("timeout_sec"),
            max_tokens=yaml_cfg.get("llm", {}).get("max_tokens"),
        )
        if llm_cfg is None:
            print(
                "未设置 API Key（见 AIMA_OPENAI_* / AIMA_ANTHROPIC_*）。"
                "使用 --dry-run 可本地试跑。",
                file=sys.stderr,
            )
            return 2
        client = build_client(llm_cfg)

    if simple_session_path is not None:
        with simple_session_path.open("w", encoding="utf-8") as simple_fp:
            rr = run_llm_match(
                seed=cfg.seed,
                max_player_steps=cfg.max_player_steps,
                client=client,
                dry_run=cfg.dry_run,
                verbose=cfg.verbose,
                session_audit=cfg.session_audit or log_stem is not None,
                simple_log_file=simple_fp,
                request_delay_seconds=0.0 if cfg.dry_run else cfg.request_delay,
                max_history_rounds=cfg.max_history_rounds,
                clear_history_on_new_hand=cfg.clear_history_per_hand,
                players=cfg.players,
            )
    else:
        rr = run_llm_match(
            seed=cfg.seed,
            max_player_steps=cfg.max_player_steps,
            client=client,
            dry_run=cfg.dry_run,
            verbose=cfg.verbose,
            session_audit=cfg.session_audit or log_stem is not None,
            simple_log_file=None,
            request_delay_seconds=0.0 if cfg.dry_run else cfg.request_delay,
            max_history_rounds=cfg.max_history_rounds,
            clear_history_on_new_hand=cfg.clear_history_per_hand,
            players=cfg.players,
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
