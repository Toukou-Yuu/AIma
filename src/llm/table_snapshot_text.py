"""全桌「读谱式」纯文本快照（简体中文），供 ``logs/simple`` 使用。

依赖 ``BoardState`` + ``TableSnapshot``；须全知手牌时直接读 ``board.hands``（不经过 LLM）。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from kernel.deal.model import BoardState
from kernel.engine.state import GameState
from kernel.event_log import FlowEvent, GameEvent, HandOverEvent
from kernel.flow.model import FlowKind
from kernel.hand.melds import Meld, MeldKind
from kernel.table.model import PrevailingWind, TableSnapshot
from kernel.tiles.model import Tile

_CALL_KIND_CN: dict[str, str] = {
    "chi": "吃",
    "pon": "碰",
    "daiminkan": "大明杠",
    "ankan": "暗杠",
    "shankuminkan": "加杠",
}

_WIND_SEAT = ("东", "南", "西", "北")


def _tile_sort_key(t: Tile) -> tuple[int, int, int, int]:
    return (t.suit.value, t.rank, 1 if t.is_red else 0)


def _tiles_sorted_str(tiles: list[Tile]) -> str:
    return "".join(t.to_code() for t in sorted(tiles, key=_tile_sort_key))


def _counter_sorted_str(c: Counter[Tile]) -> str:
    return _tiles_sorted_str(list(c.elements()))


def _wind_seat_label(dealer_seat: int, seat: int) -> str:
    r = (seat - dealer_seat) % 4
    return _WIND_SEAT[r]


def _absolute_seat_suffix(seat: int) -> str:
    """引擎座位绝对标号（0–3），与相对风位「东南西北」并列显示。"""
    return f"(S{seat})"


def _seat_wind_name(dealer_seat: int, seat: int | None) -> str:
    """东家 / 南家 …（相对当前亲席）。"""
    if seat is None:
        return "（未知席）"
    return _wind_seat_label(dealer_seat, seat) + "家"


def _discarder_seat_for_meld(owner_seat: int, m: Meld) -> int | None:
    """鸣牌 ``from_seat`` 为相对鸣牌者偏移，还原为绝对座位。"""
    if m.from_seat is None:
        return None
    return (owner_seat + m.from_seat) % 4


def _meld_segment(m: Meld, owner_seat: int, dealer_seat: int) -> str:
    """``碰东家[1z1z1z]``、``暗杠[...]`` 等（不含 ``副露：`` 前缀，多块用空格拼接）。"""
    k = m.kind
    tiles_s = "".join(t.to_code() for t in m.tiles)
    if k == MeldKind.ANKAN:
        return f"暗杠[{tiles_s}]"
    if k == MeldKind.SHANKUMINKAN:
        return f"加杠[{tiles_s}]"
    ds = _discarder_seat_for_meld(owner_seat, m)
    if ds is None:
        return f"{k.value}[{tiles_s}]"
    who = _seat_wind_name(dealer_seat, ds)
    ds_abs = _absolute_seat_suffix(ds) if ds is not None else ""
    if k == MeldKind.CHI:
        return f"吃{who}{ds_abs}[{tiles_s}]"
    if k == MeldKind.PON:
        return f"碰{who}{ds_abs}[{tiles_s}]"
    if k == MeldKind.DAIMINKAN:
        return f"大明杠{who}{ds_abs}[{tiles_s}]"
    return f"{k.value}{who}[{tiles_s}]"


def _melds_line(board: BoardState, owner_seat: int, dealer_seat: int) -> str:
    melds = board.melds[owner_seat]
    if not melds:
        return "副露：无"
    segs = [_meld_segment(m, owner_seat, dealer_seat) for m in melds]
    return "副露：" + " ".join(segs)


def _river_line_for_seat(board: BoardState, seat: int) -> str:
    """``牌河：`` 前缀由调用方加；此处为内容。``[x]``=立直宣言打、``<x>``=摸切、其余为手切。"""
    parts: list[str] = []
    for e in board.river:
        if e.seat != seat:
            continue
        code = e.tile.to_code()
        if e.riichi:
            parts.append(f"[{code}]")
        elif e.tsumogiri:
            parts.append(f"<{code}>")
        else:
            parts.append(code)
    return "".join(parts) if parts else ""


def _concealed_sorted_with_turn_draw_note(
    concealed: Counter[Tile],
    *,
    turn_draw_tile: Tile | None,
    annotate: bool,
) -> str:
    """
    门内排序串；若 ``annotate`` 且给定本巡摸牌，在行末用全角 ``（牌码）`` 标摸入，
    并从主串中**去掉一张同键牌**，避免 ``5mr…（5mr）`` 重复。
    摸切等导致手牌中已无该张时，主串保持 13 张排序，仅末尾标 ``（牌码）``。
    """
    if not annotate or turn_draw_tile is None:
        return _counter_sorted_str(concealed)
    code = turn_draw_tile.to_code()
    c = Counter(concealed)
    if c.get(turn_draw_tile, 0) >= 1:
        c[turn_draw_tile] -= 1
        if c[turn_draw_tile] == 0:
            del c[turn_draw_tile]
        base = _counter_sorted_str(c)
    else:
        base = _counter_sorted_str(concealed)
    return f"{base}（{code}）"


def _hand_line_with_draw_note(
    board: BoardState,
    seat: int,
    *,
    discard_seat: int | None,
    turn_draw_tile: Tile | None,
    discarded_tile: Tile | None = None,
) -> str:
    """
    手牌行：排序门内张数；若本块为「打牌」快照且带本巡摸牌（合并摸打日志时由 runner 传入），
    在**该家**行末用全角 ``（牌码）`` 标**本巡摸入的牌**（与牌河 ``<>`` 摸切、手切区分）。

    ``discarded_tile``：本步打出的牌。快照为「打后」局面时门内少 1 张；若与 ``turn_draw_tile`` 同
    时传入，则先把打出的牌加回计数，表示**摸入后、打出前**的门内（含 14 枚通常待打阶段），
    再与 ``（牌码）`` 去重，避免摸切后只剩 13 枚看起来像「少一张」。
    """
    c = Counter(board.hands[seat].elements())
    annotate = (
        discard_seat is not None
        and turn_draw_tile is not None
        and seat == discard_seat
    )
    if annotate and discarded_tile is not None:
        c[discarded_tile] += 1
    return _concealed_sorted_with_turn_draw_note(
        c,
        turn_draw_tile=turn_draw_tile,
        annotate=annotate,
    )


def _prevailing_cn(pw: PrevailingWind) -> str:
    return "東風" if pw == PrevailingWind.EAST else "南風"


def _round_title(table: TableSnapshot) -> str:
    w = _prevailing_cn(table.prevailing_wind)
    n = table.round_number.value
    return f"{w}{n}局"


def format_hand_over_section(
    events: tuple[GameEvent, ...],
    dealer_seat: int,
) -> str | None:
    """
    从 ``apply`` 返回的事件列中取出 ``HandOverEvent``，
    生成「本局和了」摘要（番型、荣和/自摸、番符、役、得点）。一炮多响时多行。
    """
    ho: HandOverEvent | None = None
    for ev in events:
        if isinstance(ev, HandOverEvent):
            ho = ev
            break
    if ho is None or not ho.win_lines:
        return None
    out: list[str] = []
    out.append("本局和了：")
    for ln in ho.win_lines:
        who = _seat_wind_name(dealer_seat, ln.seat)
        rk = "荣和" if ln.win_kind == "ron" else "自摸"
        yaku_txt = "、".join(ln.yakus) if ln.yakus else "—"
        out.append(
            f"  {who} {ln.hand_pattern} {rk} {ln.han}番{ln.fu}符 [{yaku_txt}] {ln.points:+d}点"
        )
    return "\n".join(out)


_FLOW_KIND_CN: dict[FlowKind, str] = {
    FlowKind.EXHAUSTED: "荒牌流局（牌山摸完）",
    FlowKind.NINE_NINE: "九种九牌流局",
    FlowKind.FOUR_WINDS: "四风连打流局",
    FlowKind.FOUR_KANS: "四杠散了流局",
    FlowKind.FOUR_RIICHI: "四家立直流局",
    FlowKind.THREE_RON: "三家和流局",
}


def format_flow_section(
    events: tuple[GameEvent, ...],
    dealer_seat: int,
) -> str | None:
    """
    从 ``apply`` 返回的事件列中取出 ``FlowEvent``，生成「本局流局」摘要（听牌席）。
    """
    fe: FlowEvent | None = None
    for ev in events:
        if isinstance(ev, FlowEvent):
            fe = ev
            break
    if fe is None:
        return None
    title = _FLOW_KIND_CN.get(fe.flow_kind, fe.flow_kind.value)
    lines: list[str] = [f"本局流局：{title}"]
    if fe.tenpai_seats:
        tp = "、".join(_seat_wind_name(dealer_seat, s) for s in sorted(fe.tenpai_seats))
        lines.append(f"听牌：{tp}")
        noten = [s for s in range(4) if s not in fe.tenpai_seats]
        if noten:
            nt = "、".join(_seat_wind_name(dealer_seat, s) for s in noten)
            lines.append(f"未听：{nt}")
    else:
        lines.append("听牌：无（四家均未听牌）")
    return "\n".join(lines)


def format_round_end_section(
    events: tuple[GameEvent, ...] | None,
    dealer_seat: int,
) -> str | None:
    """和了摘要或流局摘要，本步只会有一种。"""
    if not events:
        return None
    ho = format_hand_over_section(events, dealer_seat)
    if ho is not None:
        return ho
    return format_flow_section(events, dealer_seat)


def _format_points_and_winrate_lines(
    dealer_seat: int,
    scores: tuple[int, int, int, int],
    win_counts: tuple[int, int, int, int],
    hands_finished: int,
) -> tuple[str, str]:
    """点棒一行 + 和了/胜率一行（相对亲席：东→南→西→北；附绝对座位 S0–S3）。"""
    pt_parts: list[str] = []
    wr_parts: list[str] = []
    for rel in range(4):
        seat = (dealer_seat + rel) % 4
        wlab = _WIND_SEAT[rel]
        abs_s = _absolute_seat_suffix(seat)
        pt_parts.append(f"{wlab}{abs_s}{scores[seat]}")
        wc = win_counts[seat]
        if hands_finished <= 0:
            wr_parts.append(f"{wlab}家{abs_s}{wc}/0(—)")
        else:
            pct = 100.0 * wc / hands_finished
            wr_parts.append(f"{wlab}家{abs_s}{wc}/{hands_finished}({pct:.1f}%)")
    line_pt = "点数：" + "  ".join(pt_parts)
    line_wr = "和了胜率：" + "  ".join(wr_parts)
    return line_pt, line_wr


def action_wire_to_cn(
    w: dict[str, Any],
    *,
    dealer_seat: int = 0,
    draw_tile_code: str | None = None,
) -> str:
    """牌谱 wire → 一行中文说明（「执行…」用）。``dealer_seat`` 用于风位称呼。

    ``draw_tile_code``：合并摸打日志时传入本巡摸牌短码，与 ``discard`` 同现（如 ``摸9m 打牌 3s``）。
    """
    kind = w.get("kind")
    seat = w.get("seat")
    who = _seat_wind_name(dealer_seat, seat)
    if kind == "begin_round":
        return "开局配牌（BEGIN_ROUND）"
    if kind == "noop":
        return "局间推进并洗混牌山（NOOP）"
    if kind == "draw":
        return f"{who} 摸牌（DRAW）"
    if kind == "discard":
        t = w.get("tile", "?")
        ri = "立直宣言" if w.get("declare_riichi") else "打牌"
        if draw_tile_code:
            return f"{who} 摸{draw_tile_code} {ri} {t}"
        return f"{who} {ri} {t}"
    if kind == "pass_call":
        return f"{who} 鸣牌/荣和 PASS"
    if kind == "call_pass_drain":
        return "应答窗：连续过牌（CALL_PASS_DRAIN）"
    if kind == "ron":
        return f"{who} 荣和（RON）"
    if kind == "tsumo":
        return f"{who} 自摸和了（TSUMO）"
    if kind == "open_meld":
        m = w.get("meld") or {}
        mk = _CALL_KIND_CN.get(str(m.get("kind", "")), str(m.get("kind", "?")))
        ts = "".join(m.get("tiles") or [])
        return f"{who} {mk} [{ts}]"
    if kind == "ankan":
        m = w.get("meld") or {}
        ts = "".join(m.get("tiles") or [])
        return f"{who} 暗杠 [{ts}]"
    if kind == "shankuminkan":
        m = w.get("meld") or {}
        ts = "".join(m.get("tiles") or [])
        return f"{who} 加杠 [{ts}]"
    return f"{kind} seat={seat}"


def format_table_snapshot_block(
    state: GameState,
    *,
    hand_number: int,
    last_action_cn: str | None,
    win_counts: tuple[int, int, int, int] = (0, 0, 0, 0),
    hands_finished: int = 0,
    hand_over_section: str | None = None,
    turn_draw_tile: Tile | None = None,
    discard_seat: int | None = None,
    discarded_tile: Tile | None = None,
    llm_why: str | None = None,
    llm_why_seat: int | None = None,
) -> str:
    """
    输出一块多行快照；若不在局中或无 ``board`` 则返回简短说明。

    ``win_counts`` / ``hands_finished``：本场已终局数与各家和了次数，用于胜率（和了数/已终局数）。
    ``hand_over_section``：和了结算摘要（番型等），由 ``format_hand_over_section`` 从事件生成。
    ``turn_draw_tile`` / ``discard_seat`` / ``discarded_tile``：合并摸打后仅打牌快照时，
    用全角括号标本巡摸入牌；主串中去重同键牌。若传入 ``discarded_tile``，先加回打出张再标注，
    表示摸后打前的门内张数（含 14 枚通常待打）。
    ``llm_why`` / ``llm_why_seat``：模型对本步选择的简要理由，写在「执行：」下一行（``东南西北``家：…）。
    ``hand_over_section``：由 ``format_round_end_section`` 填入，可为「本局和了」或「本局流局」摘要。
    """
    lines: list[str] = []
    table = state.table
    board = state.board
    lines.append(f"============= round {hand_number} =============")

    if board is None:
        lines.append(f"（阶段：{state.phase.value}，无牌桌快照）")
        ds = table.dealer_seat
        ln_pt, ln_wr = _format_points_and_winrate_lines(
            ds, table.scores, win_counts, hands_finished
        )
        lines.append(ln_pt)
        lines.append(ln_wr)
        if hand_over_section:
            lines.append(hand_over_section)
        if last_action_cn:
            lines.append(f"执行：{last_action_cn}")
            if llm_why and llm_why_seat is not None:
                lines.append(
                    f"{_seat_wind_name(ds, llm_why_seat)}：{llm_why.strip()}"
                )
        lines.append("-----------------------------------------------------")
        return "\n".join(lines) + "\n"

    wall_rem = len(board.live_wall) - board.live_draw_index
    rnd = _round_title(table)
    hb = table.honba
    kt = table.kyoutaku
    lines.append(f"余牌：{wall_rem}            {rnd}          {hb}本场             场供：{kt}")
    if board.revealed_indicators:
        ind = " ".join(t.to_code() for t in board.revealed_indicators)
        lines.append(f"宝牌指示器：{ind}")
    else:
        lines.append("宝牌指示器：—")

    dealer = table.dealer_seat
    ln_pt, ln_wr = _format_points_and_winrate_lines(
        dealer, table.scores, win_counts, hands_finished
    )
    lines.append(ln_pt)
    lines.append(ln_wr)

    order = (dealer, (dealer + 1) % 4, (dealer + 2) % 4, (dealer + 3) % 4)

    for idx, s in enumerate(order):
        wlab = _wind_seat_label(dealer, s)
        hand_str = _hand_line_with_draw_note(
            board,
            s,
            discard_seat=discard_seat,
            turn_draw_tile=turn_draw_tile,
            discarded_tile=discarded_tile,
        )
        melds_txt = _melds_line(board, s, dealer)
        river_body = _river_line_for_seat(board, s)
        river_full = river_body if river_body else "—"
        is_last = idx == 3
        abs_s = _absolute_seat_suffix(s)
        if not is_last:
            lines.append(f"├── {wlab}家{abs_s}：{hand_str}")
            lines.append(f"│   ├── {melds_txt}")
            lines.append(f"│   └── 牌河：{river_full}")
        else:
            lines.append(f"└── {wlab}家{abs_s}：{hand_str}")
            lines.append(f"    ├── {melds_txt}")
            lines.append(f"    └── 牌河：{river_full}")

    if hand_over_section:
        lines.append(hand_over_section)
    if last_action_cn:
        lines.append(f"执行：{last_action_cn}")
        if llm_why and llm_why_seat is not None:
            lines.append(f"{_seat_wind_name(dealer, llm_why_seat)}：{llm_why.strip()}")
    lines.append("-----------------------------------------------------")
    return "\n".join(lines) + "\n"


def write_snapshot_block(
    fp,
    state: GameState,
    *,
    hand_number: int,
    last_action_cn: str | None,
    win_counts: tuple[int, int, int, int] = (0, 0, 0, 0),
    hands_finished: int = 0,
    events: tuple[GameEvent, ...] | None = None,
    turn_draw_tile: Tile | None = None,
    discard_seat: int | None = None,
    discarded_tile: Tile | None = None,
    llm_why: str | None = None,
    llm_why_seat: int | None = None,
) -> None:
    """写入快照块并 flush。若给定 ``events``，追加和了或流局摘要（``format_round_end_section``）。"""
    if fp is None:
        return
    ds = state.table.dealer_seat
    ho_sec = format_round_end_section(events, ds)
    fp.write(
        format_table_snapshot_block(
            state,
            hand_number=hand_number,
            last_action_cn=last_action_cn,
            win_counts=win_counts,
            hands_finished=hands_finished,
            hand_over_section=ho_sec,
            turn_draw_tile=turn_draw_tile,
            discard_seat=discard_seat,
            discarded_tile=discarded_tile,
            llm_why=llm_why,
            llm_why_seat=llm_why_seat,
        )
    )
    fp.flush()
