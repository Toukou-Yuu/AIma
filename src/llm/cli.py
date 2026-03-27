"""命令行：``python -m llm``。"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

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


def main(argv: list[str] | None = None) -> int:
    _load_dotenv_if_available()
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")
    _cap_console_handlers_info()
    # 避免 httpx 每条请求刷 INFO，盖住本程序摘要；需要调试 HTTP 时再改回 DEBUG
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    p = argparse.ArgumentParser(description="AIma LLM 牌手跑局（内核闭环）")
    p.add_argument("--seed", type=int, default=0, help="首局洗牌种子")
    p.add_argument("--max-steps", type=int, default=500, help="最大 apply 步数（含局间 NOOP）")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="不调用 API；每步取 legal_actions 首项（确定性）",
    )
    p.add_argument(
        "--log-json",
        metavar="PATH",
        help="跑局结束后将牌谱写入指定路径的 JSON（与 --log-session 可同用）",
    )
    p.add_argument(
        "--log-session",
        nargs="?",
        const="",
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
        help="每步 apply 后向 stderr 打印阶段摘要（对局进度）",
    )
    p.add_argument(
        "--request-delay",
        type=float,
        default=0.5,
        metavar="SEC",
        help="每次调用 LLM API 前的间隔秒数（减压控/减少连接被远端掐断）；默认 0.5；设为 0 可关闭；--dry-run 不请求 API，此项无效",
    )
    args = p.parse_args(argv)

    if args.replay:
        return _cmd_replay(args.replay)

    try:
        log_stem = _resolve_log_stem(args.log_session)
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
    if not args.dry_run:
        cfg = load_llm_config()
        if cfg is None:
            print(
                "未设置 API Key（见 AIMA_OPENAI_* / AIMA_ANTHROPIC_*）。"
                "使用 --dry-run 可本地试跑。",
                file=sys.stderr,
            )
            return 2
        client = build_client(cfg)

    if simple_session_path is not None:
        with simple_session_path.open("w", encoding="utf-8") as simple_fp:
            rr = run_llm_match(
                seed=args.seed,
                max_steps=args.max_steps,
                client=client,
                dry_run=args.dry_run,
                verbose=args.verbose,
                session_audit=log_stem is not None,
                simple_log_file=simple_fp,
                request_delay_seconds=0.0 if args.dry_run else args.request_delay,
            )
    else:
        rr = run_llm_match(
            seed=args.seed,
            max_steps=args.max_steps,
            client=client,
            dry_run=args.dry_run,
            verbose=args.verbose,
            session_audit=log_stem is not None,
            simple_log_file=None,
            request_delay_seconds=0.0 if args.dry_run else args.request_delay,
        )
    print(f"steps={rr.steps} reason={rr.stopped_reason!r} phase={rr.final_state.phase.value}")
    if log_stem is not None:
        logging.info(
            "run_finished steps=%s reason=%s phase=%s actions=%s events=%s",
            rr.steps,
            rr.stopped_reason,
            rr.final_state.phase.value,
            len(rr.actions_wire),
            len(rr.events_wire),
        )
    payload = json.dumps(rr.as_match_log(), ensure_ascii=False, indent=2)
    if args.log_json:
        pth = Path(args.log_json)
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
