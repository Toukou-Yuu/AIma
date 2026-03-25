"""FastAPI 应用：开桌、查询、提交动作。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from kernel import apply, build_deck, shuffle_deck
from kernel.api.legal_actions import LegalAction, legal_actions
from kernel.api.observation import observation
from kernel.engine.actions import Action, ActionKind
from kernel.engine.apply import IllegalActionError
from kernel.engine.state import GameState, initial_game_state
from web.api.codec import action_from_payload, legal_action_to_payload
from web.api.serialize import observation_to_json
from web.api.store import MatchStore

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_TILES_DIR = _REPO_ROOT / "assets" / "mahjong_tiles"


def _collect_web_legal_actions(state: GameState) -> tuple[LegalAction, ...]:
    """合并四家合法动作。

    ``CALL_RESPONSE`` 时表态权在他家，仅查 ``legal_actions(state, 0)`` 会得到空列表。
    单页调试/回放需要可操作所有席，故合并 0..3。终局四家同质 ``NOOP`` 只保留一条。
    """
    merged: list[LegalAction] = []
    for s in range(4):
        merged.extend(legal_actions(state, s))
    if merged and all(a.kind == ActionKind.NOOP for a in merged):
        return (merged[0],)
    return tuple(merged)


def _parse_observe_mode(raw: str | None) -> Literal["human", "debug"]:
    """缺省 debug（回放式全显）；非法值 400。"""
    if raw is None or raw == "":
        return "debug"
    if raw in ("human", "debug"):
        return raw  # type: ignore[return-value]
    raise HTTPException(
        status_code=400,
        detail="observe_mode must be 'human' or 'debug'",
    )


class CreateMatchBody(BaseModel):
    """开桌可选体。"""

    seed: int | None = Field(default=None, description="洗牌种子，缺省随机")


def create_app(store: MatchStore | None = None) -> FastAPI:
    """创建应用；传入独立 ``MatchStore`` 便于测试隔离。"""
    _store = store if store is not None else MatchStore()
    app = FastAPI(title="AIma Web API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if _TILES_DIR.is_dir():
        app.mount("/assets/tiles", StaticFiles(directory=str(_TILES_DIR)), name="tiles")

    @app.get("/")
    def root() -> dict[str, Any]:
        """浏览器打开根路径时不至于 404；正式对局走 ``/api``。"""
        return {
            "service": "AIma Web API",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "create_match": "POST /api/matches",
        }

    @app.post("/api/matches")
    def create_match(
        body: CreateMatchBody | None = Body(default=None),
        observe_mode: str | None = Query(default=None),
    ) -> dict[str, Any]:
        seed = body.seed if body else None
        mode = _parse_observe_mode(observe_mode)
        g0 = initial_game_state()
        wall = tuple(shuffle_deck(build_deck(), seed=seed))
        try:
            outcome = apply(g0, Action(ActionKind.BEGIN_ROUND, wall=wall))
        except (IllegalActionError, ValueError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        state = outcome.new_state
        match_id = _store.create(state)
        seat = 0
        obs = observation(state, seat, mode=mode)
        acts = _collect_web_legal_actions(state)
        return {
            "match_id": match_id,
            "phase": state.phase.value,
            "seat": seat,
            "observation": observation_to_json(obs, table=state.table, board=state.board),
            "legal_actions": [legal_action_to_payload(a) for a in acts],
        }

    @app.get("/api/matches/{match_id}")
    def get_match(
        match_id: str,
        seat: int = 0,
        observe_mode: str | None = Query(default=None),
    ) -> dict[str, Any]:
        if not 0 <= seat <= 3:
            raise HTTPException(status_code=400, detail="seat must be 0..3")
        mode = _parse_observe_mode(observe_mode)
        state = _store.get(match_id)
        if state is None:
            raise HTTPException(status_code=404, detail="match not found")
        obs = observation(state, seat, mode=mode)
        acts = _collect_web_legal_actions(state)
        return {
            "match_id": match_id,
            "phase": state.phase.value,
            "seat": seat,
            "observation": observation_to_json(obs, table=state.table, board=state.board),
            "legal_actions": [legal_action_to_payload(a) for a in acts],
        }

    @app.post("/api/matches/{match_id}/actions")
    def post_action(
        match_id: str,
        payload: dict[str, Any] = Body(...),
        observe_mode: str | None = Query(default=None),
    ) -> dict[str, Any]:
        mode = _parse_observe_mode(observe_mode)
        state = _store.get(match_id)
        if state is None:
            raise HTTPException(status_code=404, detail="match not found")
        try:
            action = action_from_payload(payload)
        except (KeyError, ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail=f"invalid action: {e}") from e
        try:
            outcome = apply(state, action)
        except IllegalActionError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        new_state = outcome.new_state
        _store.put(match_id, new_state)
        seat = int(payload.get("seat", 0))
        if not 0 <= seat <= 3:
            seat = 0
        obs = observation(new_state, seat, mode=mode)
        acts = _collect_web_legal_actions(new_state)
        return {
            "match_id": match_id,
            "phase": new_state.phase.value,
            "seat": seat,
            "observation": observation_to_json(obs, table=new_state.table, board=new_state.board),
            "legal_actions": [legal_action_to_payload(a) for a in acts],
        }

    return app


app = create_app()
