"""Web API MVP：开桌、GET、一步 DISCARD。"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from web.api.app import create_app
from web.api.store import MatchStore


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(MatchStore()))


def test_create_match_and_get(client: TestClient) -> None:
    r = client.post("/api/matches", json={"seed": 42})
    assert r.status_code == 200
    data = r.json()
    assert "match_id" in data
    assert data["phase"] == "in_round"
    assert data["seat"] == 0
    hand = data["observation"]["hand"]
    assert hand is not None
    assert sum(hand.values()) >= 13
    assert any(a["kind"] == "discard" for a in data["legal_actions"])
    # 默认 observe_mode=debug：回放式全显
    obs = data["observation"]
    assert obs["hands_by_seat"] is not None
    assert len(obs["hands_by_seat"]) == 4
    assert len(obs["melds_by_seat"]) == 4
    for hb in obs["hands_by_seat"]:
        assert isinstance(hb, dict)
        assert sum(hb.values()) >= 0

    mid = data["match_id"]
    r2 = client.get(f"/api/matches/{mid}", params={"seat": 0})
    assert r2.status_code == 200
    assert r2.json()["match_id"] == mid


def test_observe_mode_human_hides_hands_by_seat(client: TestClient) -> None:
    r = client.post("/api/matches?observe_mode=human", json={"seed": 7})
    assert r.status_code == 200
    obs = r.json()["observation"]
    assert obs["hands_by_seat"] is None
    assert "concealed_count_by_seat" in obs
    assert len(obs["concealed_count_by_seat"]) == 4
    assert all(n >= 0 for n in obs["concealed_count_by_seat"])


def test_discard_one_tile(client: TestClient) -> None:
    r = client.post("/api/matches", json={"seed": 1})
    data = r.json()
    mid = data["match_id"]
    river_len_before = len(data["observation"]["river"])
    # 非立直宣言的打牌，避免复杂分支
    plain = next(
        a
        for a in data["legal_actions"]
        if a["kind"] == "discard" and not a.get("declare_riichi")
    )
    r2 = client.post(f"/api/matches/{mid}/actions", json=plain)
    assert r2.status_code == 200, r2.text
    after = r2.json()
    assert len(after["observation"]["river"]) == river_len_before + 1


def test_after_discard_legal_actions_include_other_seats(client: TestClient) -> None:
    """CALL_RESPONSE 时打牌者本人无动作，合并列表须含他家 pass/荣和 等。"""
    r = client.post("/api/matches", json={"seed": 1})
    data = r.json()
    mid = data["match_id"]
    plain = next(
        a
        for a in data["legal_actions"]
        if a["kind"] == "discard" and not a.get("declare_riichi")
    )
    r2 = client.post(f"/api/matches/{mid}/actions", json=plain)
    assert r2.status_code == 200, r2.text
    after = r2.json()
    assert after["observation"].get("turn_phase") == "call_response"
    acts = after["legal_actions"]
    assert len(acts) > 0
    seats = {a["seat"] for a in acts}
    assert seats != {plain["seat"]} or any(
        a["kind"] != "discard" for a in acts
    )


def test_unknown_match_404(client: TestClient) -> None:
    r = client.get("/api/matches/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
