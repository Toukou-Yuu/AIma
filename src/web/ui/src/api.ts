export type ObserveMode = "human" | "debug";

export type MeldPayload = {
  kind: string;
  tiles: string[];
  called_tile?: string;
  from_seat?: number;
};

export type LegalActionDTO = {
  kind: string;
  seat: number;
  tile?: string;
  meld?: Record<string, unknown>;
  declare_riichi?: boolean;
};

/** 与后端 observation_to_json 对齐的主要字段 */
export type ObservationDTO = {
  seat: number;
  hand: Record<string, number> | null;
  melds: MeldPayload[];
  river: Array<{
    tile: string;
    seat: number;
    is_tsumogiri: boolean;
    is_riichi: boolean;
  }>;
  dora_indicators: string[];
  ura_indicators: string[] | null;
  riichi_state: boolean[];
  scores: number[];
  honba: number;
  kyoutaku: number;
  turn_seat: number;
  turn_phase?: string;
  current_seat?: number;
  /** 鸣牌应答子阶段：ron → pon_kan → chi（同一巡内依次进行） */
  call_response_stage?: "ron" | "pon_kan" | "chi";
  /** 当前子阶段有权操作的 seat（ron 为尚未表态的多家） */
  call_active_seats?: number[];
  last_discard: string | null;
  last_discard_seat: number | null;
  last_draw_tile?: string | null;
  last_draw_seat?: number | null;
  wall_remaining: number | null;
  hands_by_seat: Array<Record<string, number>> | null;
  melds_by_seat: MeldPayload[][];
  concealed_count_by_seat?: number[];
  table: {
    prevailing_wind: string;
    round_number: number;
    dealer_seat: number;
    honba: number;
    kyoutaku: number;
    scores: number[];
  };
};

export type MatchResponse = {
  match_id: string;
  phase: string;
  seat: number;
  observation: ObservationDTO;
  legal_actions: LegalActionDTO[];
};

function observeQuery(mode: ObserveMode): string {
  return mode === "human" ? "?observe_mode=human" : "";
}

export async function createMatch(
  seed?: number,
  observeMode: ObserveMode = "debug",
): Promise<MatchResponse> {
  const q = observeQuery(observeMode);
  const r = await fetch(`/api/matches${q}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(seed != null ? { seed } : {}),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<MatchResponse>;
}

export async function getMatch(
  matchId: string,
  seat: number,
  observeMode: ObserveMode = "debug",
): Promise<MatchResponse> {
  const om =
    observeMode === "human" ? "&observe_mode=human" : "&observe_mode=debug";
  const r = await fetch(`/api/matches/${matchId}?seat=${seat}${om}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<MatchResponse>;
}

export async function postAction(
  matchId: string,
  action: LegalActionDTO,
  observeMode: ObserveMode = "debug",
): Promise<MatchResponse> {
  const q = observeMode === "human" ? "?observe_mode=human" : "";
  const r = await fetch(`/api/matches/${matchId}/actions${q}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(action),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<MatchResponse>;
}
