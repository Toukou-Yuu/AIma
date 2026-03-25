import { useCallback, useMemo, useState } from "react";
import "./App.css";
import {
  createMatch,
  getMatch,
  postAction,
  type LegalActionDTO,
  type MatchResponse,
  type MeldPayload,
  type ObservationDTO,
  type ObserveMode,
} from "./api";
import { backImageSrc, tileImageSrc } from "./tileAssets";

const WIND_CHARS = ["", "东", "南", "西", "北"];

function windLabel(w: string): string {
  if (w === "east") return "东场";
  if (w === "south") return "南场";
  return w;
}

function relSeat(absoluteSeat: number, viewerSeat: number): number {
  return (absoluteSeat - viewerSeat + 4) % 4;
}

/** 该席相对亲家的自风（东南西北） */
function seatWindChar(dealerSeat: number, absoluteSeat: number): string {
  const rank = ((absoluteSeat - dealerSeat + 4) % 4) + 1;
  return WIND_CHARS[rank] ?? "?";
}

function expandHand(hand: Record<string, number> | null | undefined): string[] {
  if (!hand) return [];
  const out: string[] = [];
  const keys = Object.keys(hand).sort();
  for (const code of keys) {
    const n = hand[code];
    for (let i = 0; i < n; i++) out.push(code);
  }
  return out;
}

function handMainAndTsumo(
  hand: Record<string, number> | null | undefined,
  absSeat: number,
  lastDrawSeat: number | null | undefined,
  lastDrawTile: string | null | undefined,
): { main: string[]; tsumo: string | null } {
  const all = expandHand(hand);
  if (
    lastDrawTile &&
    lastDrawSeat === absSeat &&
    all.includes(lastDrawTile)
  ) {
    const i = all.lastIndexOf(lastDrawTile);
    const main = all.filter((_, j) => j !== i);
    return { main, tsumo: lastDrawTile };
  }
  return { main: all, tsumo: null };
}

function pickDiscardAction(
  actions: LegalActionDTO[],
  tile: string,
  seat: number,
): LegalActionDTO | null {
  const candidates = actions.filter(
    (a) => a.kind === "discard" && a.seat === seat && a.tile === tile,
  );
  if (!candidates.length) return null;
  const plain = candidates.find((a) => !a.declare_riichi);
  return plain ?? candidates[0];
}

const KIND_ZH: Record<string, string> = {
  discard: "打牌",
  pass_call: "过",
  ron: "荣和",
  draw: "摸牌",
  tsumo: "自摸",
  noop: "继续",
  open_meld: "鸣牌",
  ankan: "暗杠",
  shankuminkan: "加杠",
};

function actionLabel(a: LegalActionDTO): string {
  const kz = KIND_ZH[a.kind] ?? a.kind;
  const parts = [`[seat ${a.seat}] ${kz}`];
  if (a.tile) parts.push(a.tile);
  if (a.declare_riichi) parts.push("立直宣言");
  return parts.join(" · ");
}

/** 牌图 404 时显示短码，避免白块 */
function TileFace({
  code,
  className,
}: {
  code: string;
  className?: string;
}) {
  return (
    <span className="tile-face">
      <img
        className={className ?? "tile-img"}
        src={tileImageSrc(code)}
        alt={code}
        onError={(ev) => {
          ev.currentTarget.style.display = "none";
          const el = ev.currentTarget.nextElementSibling;
          if (el) (el as HTMLElement).style.display = "flex";
        }}
      />
      <span className="tile-fallback" style={{ display: "none" }}>
        {code}
      </span>
    </span>
  );
}

function RiverGrid({
  entries,
  className,
}: {
  entries: ObservationDTO["river"];
  className?: string;
}) {
  return (
    <div className={`river-grid ${className ?? ""}`}>
      {entries.map((e, i) => (
        <div
          key={i}
          className={`river-cell${e.is_riichi ? " river-cell--riichi" : ""}`}
          title={`${e.tile}${e.is_tsumogiri ? " 摸切" : ""}${e.is_riichi ? " 立直" : ""}`}
        >
          <TileFace code={e.tile} />
        </div>
      ))}
    </div>
  );
}

function MeldStrip({ melds }: { melds: MeldPayload[] }) {
  if (!melds.length) return null;
  return (
    <div className="meld-strip">
      {melds.map((m, mi) => (
        <div key={mi} className="meld-group">
          {m.tiles.map((t, ti) => {
            const isCalled = m.called_tile === t;
            return (
              <div
                key={`${t}-${ti}`}
                className={`meld-tile-wrap${isCalled ? " meld-tile-wrap--called" : ""}`}
              >
                <TileFace code={t} className="tile-img tile-img--meld" />
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function TileBackStack({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <div className="tile-back-stack">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="tile-back-wrap">
          <img
            className="tile-img tile-img--back"
            src={backImageSrc()}
            alt="牌背"
            onError={(ev) => {
              ev.currentTarget.style.display = "none";
              ev.currentTarget.parentElement?.classList.add("tile-back-fallback");
            }}
          />
        </div>
      ))}
    </div>
  );
}

function HandTiles({
  main,
  tsumo,
  tileClassExtra,
  onTileClick,
  discardable,
}: {
  main: string[];
  tsumo: string | null;
  tileClassExtra?: string;
  onTileClick?: (code: string) => void;
  discardable?: Set<string>;
}) {
  const tileInner = (code: string, i: number, keyPrefix: string) => {
    const can = Boolean(onTileClick && discardable?.has(code));
    const cls = `hand-tile-wrap${can ? " hand-tile-wrap--discard" : ""} ${tileClassExtra ?? ""}`;
    if (onTileClick) {
      return (
        <button
          key={`${keyPrefix}-${code}-${i}`}
          type="button"
          className={cls}
          onClick={() => can && onTileClick(code)}
          disabled={!can}
          title={can ? "点击打牌" : undefined}
        >
          <TileFace code={code} />
        </button>
      );
    }
    return (
      <span key={`${keyPrefix}-${code}-${i}`} className={cls}>
        <TileFace code={code} />
      </span>
    );
  };

  return (
    <div className="hand-tiles">
      {main.map((code, i) => tileInner(code, i, "m"))}
      {tsumo && (
        <>
          <span className="tsumo-gap" aria-hidden />
          {tileInner(tsumo, 0, "t")}
        </>
      )}
    </div>
  );
}

function SeatBlock({
  obs,
  absoluteSeat,
  viewerSeat,
  dealerSeat,
  river,
  onTileClick,
  discardable,
  layout,
}: {
  obs: ObservationDTO;
  absoluteSeat: number;
  viewerSeat: number;
  dealerSeat: number;
  river: ObservationDTO["river"];
  onTileClick?: (code: string) => void;
  discardable?: Set<string>;
  layout: "top" | "bottom" | "left" | "right";
}) {
  const rel = relSeat(absoluteSeat, viewerSeat);
  const sw = seatWindChar(dealerSeat, absoluteSeat);
  const isDealer = absoluteSeat === dealerSeat;
  const handsBySeat = obs.hands_by_seat;
  const counts = obs.concealed_count_by_seat;
  const melds = obs.melds_by_seat[absoluteSeat] ?? [];
  const handRec =
    handsBySeat?.[absoluteSeat] ??
    (absoluteSeat === obs.seat ? obs.hand : null);
  const { main, tsumo } = handMainAndTsumo(
    handRec,
    absoluteSeat,
    obs.last_draw_seat ?? null,
    obs.last_draw_tile ?? null,
  );

  const orientClass =
    layout === "left"
      ? "seat-block--left"
      : layout === "right"
        ? "seat-block--right"
        : layout === "top"
          ? "seat-block--top"
          : "seat-block--bottom";

  return (
    <div className={`seat-block ${orientClass}`} data-rel={rel}>
      <div className="seat-head">
        <div className={`avatar-placeholder${isDealer ? " avatar-placeholder--dealer" : ""}`}>
          {absoluteSeat}
        </div>
        <div className="seat-meta">
          <span className="seat-wind">{sw}</span>
          {isDealer && <span className="seat-dealer">庄</span>}
          <span className="seat-score">{obs.scores[absoluteSeat] ?? "—"}</span>
        </div>
      </div>
      <RiverGrid entries={river} />
      <MeldStrip melds={melds} />
      {handsBySeat ? (
        <HandTiles
          main={main}
          tsumo={tsumo}
          onTileClick={layout === "bottom" ? onTileClick : undefined}
          discardable={layout === "bottom" ? discardable : undefined}
        />
      ) : (
        <TileBackStack count={counts?.[absoluteSeat] ?? 0} />
      )}
    </div>
  );
}

const PHASE_ZH: Record<string, string> = {
  call_response: "鸣牌应答",
  must_discard: "须打牌",
  need_draw: "须摸牌",
};

const CALL_SUB_ZH: Record<string, string> = {
  ron: "① 荣和收集",
  pon_kan: "② 碰/大明杠（下家起依次）",
  chi: "③ 上家是否吃",
};

function CenterHub({ obs }: { obs: ObservationDTO }) {
  const t = obs.table;
  const wall = obs.wall_remaining;
  const ph = obs.turn_phase;
  const phZh = ph ? (PHASE_ZH[ph] ?? ph) : "";
  const sub = obs.call_response_stage;
  const subZh = sub ? (CALL_SUB_ZH[sub] ?? sub) : "";
  const active = obs.call_active_seats;
  return (
    <div className="center-hub">
      <div className="hub-dora">
        <span className="hub-label">宝</span>
        {obs.dora_indicators.map((c, i) => (
          <TileFace key={i} code={c} className="tile-img tile-img--dora" />
        ))}
        {obs.ura_indicators && obs.ura_indicators.length > 0 && (
          <>
            <span className="hub-label">里</span>
            {obs.ura_indicators.map((c, i) => (
              <TileFace key={`u${i}`} code={c} className="tile-img tile-img--dora" />
            ))}
          </>
        )}
      </div>
      <div className="hub-main">
        <div className="hub-round">
          {windLabel(t.prevailing_wind)} {t.round_number}局
        </div>
        <div className="hub-counters">
          本场 {t.honba} · 供托 {t.kyoutaku}
          {wall != null && <span className="hub-wall"> · 余 {wall}</span>}
        </div>
        {ph && (
          <div className="hub-phase" title={ph}>
            {phZh}
            {sub && (
              <span className="hub-subphase">
                {" "}
                · {subZh}
                {active && active.length > 0 && (
                  <span className="hub-active-seats">
                    （待操作 seat: {active.join(", ")}）
                  </span>
                )}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [seat, setSeat] = useState(0);
  const [observeMode, setObserveMode] = useState<ObserveMode>("debug");
  const [seed, setSeed] = useState<number | "">("");
  const [data, setData] = useState<MatchResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const run = useCallback(async (fn: () => Promise<void>) => {
    setErr(null);
    setLoading(true);
    try {
      await fn();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const onNewMatch = () =>
    run(async () => {
      const s = seed === "" ? undefined : Number(seed);
      setData(await createMatch(s, observeMode));
    });

  const onRefresh = () =>
    run(async () => {
      if (!data) return;
      setData(await getMatch(data.match_id, seat, observeMode));
    });

  const onAction = useCallback(
    (a: LegalActionDTO) =>
      run(async () => {
        if (!data) return;
        setData(await postAction(data.match_id, a, observeMode));
      }),
    [data, observeMode, run],
  );

  const onTileClick = useCallback(
    (tile: string) => {
      if (!data) return;
      const picked = pickDiscardAction(data.legal_actions, tile, data.seat);
      if (picked) void onAction(picked);
    },
    [data, onAction],
  );

  const discardable = useMemo(() => {
    if (!data) return new Set<string>();
    return new Set(
      data.legal_actions
        .filter((a) => a.kind === "discard" && a.seat === data.seat && a.tile)
        .map((a) => a.tile as string),
    );
  }, [data]);

  const obs = data?.observation;
  const table = obs?.table;
  const phase = data?.phase ?? "";
  const turnSeat = obs?.turn_seat ?? 0;
  const dealerSeat = table?.dealer_seat ?? 0;

  const v = seat;
  const bottomS = v;
  const rightS = (v + 1) % 4;
  const topS = (v + 2) % 4;
  const leftS = (v + 3) % 4;

  const riverBySeat = useMemo(() => {
    if (!obs) return [[], [], [], []] as ObservationDTO["river"][];
    const buckets: ObservationDTO["river"][] = [[], [], [], []];
    for (const e of obs.river) {
      buckets[e.seat].push(e);
    }
    return buckets;
  }, [obs]);

  return (
    <div className="app">
      <header className="top-bar">
        <button type="button" onClick={onNewMatch} disabled={loading}>
          新开一局
        </button>
        <label>
          种子
          <input
            type="number"
            value={seed}
            onChange={(e) =>
              setSeed(e.target.value === "" ? "" : Number(e.target.value))
            }
            placeholder="随机"
          />
        </label>
        <label>
          视角 seat
          <input
            type="number"
            min={0}
            max={3}
            value={seat}
            onChange={(e) => setSeat(Number(e.target.value))}
          />
        </label>
        <label>
          观测
          <select
            value={observeMode}
            onChange={(e) => setObserveMode(e.target.value as ObserveMode)}
          >
            <option value="debug">debug（四家明牌）</option>
            <option value="human">human（仅自家）</option>
          </select>
        </label>
        <button type="button" onClick={onRefresh} disabled={loading || !data}>
          刷新
        </button>
        {data && (
          <>
            <span className="meta-chip">match {data.match_id.slice(0, 8)}…</span>
            <span className="meta-chip">{phase}</span>
          </>
        )}
        {table && (
          <span className="meta-chip">
            {windLabel(table.prevailing_wind)} {table.round_number}局 · 亲 seat
            {table.dealer_seat} · 本场{table.honba} · 供托{table.kyoutaku}
          </span>
        )}
        <div className="scores">
          {[0, 1, 2, 3].map((s) => (
            <span
              key={s}
              className={`score-seat${s === turnSeat ? " active" : ""}`}
            >
              {s}:{obs?.scores[s] ?? "—"}
            </span>
          ))}
        </div>
      </header>

      {err && <div className="error">{err}</div>}

      {!data && !err && (
        <div className="empty-hint">点击「新开一局」开始（请先启动 API :8000）</div>
      )}

      {data && obs && (
        <main className="mahjong-table">
          <div className="mt-cell mt-top">
            <SeatBlock
              obs={obs}
              absoluteSeat={topS}
              viewerSeat={v}
              dealerSeat={dealerSeat}
              river={riverBySeat[topS]}
              layout="top"
            />
          </div>
          <div className="mt-cell mt-mid">
            <div className="mt-cell mt-left">
              <SeatBlock
                obs={obs}
                absoluteSeat={leftS}
                viewerSeat={v}
                dealerSeat={dealerSeat}
                river={riverBySeat[leftS]}
                layout="left"
              />
            </div>
            <div className="mt-cell mt-center">
              <CenterHub obs={obs} />
            </div>
            <div className="mt-cell mt-right">
              <SeatBlock
                obs={obs}
                absoluteSeat={rightS}
                viewerSeat={v}
                dealerSeat={dealerSeat}
                river={riverBySeat[rightS]}
                layout="right"
              />
            </div>
          </div>
          <div className="mt-cell mt-bottom">
            <SeatBlock
              obs={obs}
              absoluteSeat={bottomS}
              viewerSeat={v}
              dealerSeat={dealerSeat}
              river={riverBySeat[bottomS]}
              onTileClick={onTileClick}
              discardable={discardable}
              layout="bottom"
            />
          </div>

          {obs.turn_phase === "call_response" && (
            <div className="call-response-hint" role="status">
              当前为<strong>鸣牌应答</strong>（同一巡内分三段，不是重复 bug）：
              <strong>荣和收集</strong>（三家各表态）→<strong>碰杠轮询</strong>（下家起依次一人一过）
              →<strong>吃</strong>（仅上家）。打完一段「过」后进入下一段仍会出现「过」，属日麻流程。
              打牌者无需操作；下栏按钮注意 <strong>seat</strong> 与中央「待操作 seat」一致。
            </div>
          )}

          <section className="actions-panel">
            <h3>
              合法动作
              {data.legal_actions.length > 0
                ? `（${data.legal_actions.length} 条，或点底部高亮手牌打牌）`
                : "（暂无）"}
            </h3>
            <div className="actions-list">
              {data.legal_actions.map((a, i) => (
                <button
                  key={`${a.kind}-${a.seat}-${a.tile ?? ""}-${a.declare_riichi ? "r" : ""}-${i}`}
                  type="button"
                  onClick={() => onAction(a)}
                  disabled={loading}
                >
                  {actionLabel(a)}
                </button>
              ))}
            </div>
          </section>
        </main>
      )}
    </div>
  );
}
