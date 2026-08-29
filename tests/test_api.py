"""
Tests for the web API: prediction jobs, evaluation, re-optimisation and
saved teams, running fully offline against the saved fixtures.
"""
import time

import pytest
from fastapi.testclient import TestClient

from sportpools.api.app import create_app
from sportpools.api.db import TeamStore

FIXTURES = "tests/fixtures"
DRAW = f"{FIXTURES}/tennistemple_us_open_2026_draw.html"
RATINGS = f"{FIXTURES}/atp_elo_ratings.html"

pytestmark = pytest.mark.skipif(
    not __import__("pathlib").Path(DRAW).exists(),
    reason="fixtures not available",
)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """App client with an isolated team database."""
    import sportpools.api.db as db_module

    original_store = db_module.STORE
    db_module.STORE = TeamStore(tmp_path_factory.mktemp("db") / "teams.db")

    import sportpools.api.app as app_module

    app_module.STORE = db_module.STORE
    with TestClient(create_app()) as test_client:
        yield test_client

    db_module.STORE = original_store
    app_module.STORE = original_store


@pytest.fixture(scope="module")
def prediction(client):
    """One completed prediction job reused by the module's tests."""
    response = client.post(
        "/api/predict",
        json={
            "tournament": "us-open",
            "year": 2026,
            "surfaces": ["hard"],
            "draw_url": DRAW,
            "ratings_file": RATINGS,
        },
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    for _ in range(600):
        status = client.get(f"/api/jobs/{job_id}").json()
        if status["status"] in ("done", "error"):
            break
        time.sleep(0.2)

    assert status["status"] == "done", status
    result = client.get(f"/api/jobs/{job_id}/result").json()
    return {"job_id": job_id, "result": result}


def test_progress_reaches_done(client, prediction):
    status = client.get(f"/api/jobs/{prediction['job_id']}").json()
    assert status["status"] == "done"
    assert status["progress"] == 1.0
    assert status["stage"] == "Done"


def test_result_structure(prediction):
    result = prediction["result"]

    assert result["surfaces"] == ["hard"]
    model = result["models"]["hard"]

    assert len(model["team"]["players"]) == 15
    roles = {p["role"] for p in model["team"]["players"]}
    assert roles == {"player", "joker", "kluns"}
    assert len(model["pool"]) == 128
    assert all(p["section"] >= 1 for p in model["pool"])
    assert len(model["joker_options"]) == 10
    assert 0 < len(model["kluns_options"]) <= 10
    assert model["kluns_options"][0]["kluns"] == model["team"]["kluns"]

    # every player has a 7-step modal route
    assert len(model["routes"]) == 128
    for route in model["routes"].values():
        assert len(route) == 7
        assert route[0]["round"] == 1 and route[-1]["round"] == 7
        assert route[0]["p_meet"] == 1.0  # first-round opponent is certain

    # team matchups cover all pairs of the 15 selected players
    assert len(model["matchups"]) == 15 * 14 // 2


def test_evaluate_matches_optimiser(prediction, client):
    model = prediction["result"]["models"]["hard"]
    team = model["team"]

    response = client.post(
        "/api/evaluate",
        json={
            "job_id": prediction["job_id"],
            "surface": "hard",
            "players": [p["player"] for p in team["players"]],
            "joker": team["joker"],
            "kluns": team["kluns"],
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["valid"] is True
    assert body["errors"] == []
    assert body["expected_points"] == pytest.approx(team["expected_points"], abs=0.05)


def test_evaluate_reports_rule_violations(prediction, client):
    model = prediction["result"]["models"]["hard"]
    players = [p["player"] for p in model["team"]["players"]]

    response = client.post(
        "/api/evaluate",
        json={
            "job_id": prediction["job_id"],
            "surface": "hard",
            "players": players,
            "joker": players[0],
            "kluns": players[0],  # same player in both roles
        },
    )
    body = response.json()
    assert body["valid"] is False
    assert any("Joker and kluns" in error for error in body["errors"])


def test_optimize_respects_locked_players(prediction, client):
    model = prediction["result"]["models"]["hard"]
    locked = ["C Alcaraz", "N Djokovic"]

    response = client.post(
        "/api/optimize",
        json={
            "job_id": prediction["job_id"],
            "surface": "hard",
            "locked": locked,
        },
    )
    assert response.status_code == 200
    body = response.json()

    selected = {p["player"] for p in body["players"]}
    assert locked[0] in selected and locked[1] in selected
    assert body["expected_points"] <= model["team"]["expected_points"] + 0.01


def test_teams_crud(client):
    listing = client.get("/api/teams").json()["teams"]
    assert listing == []

    saved = client.post(
        "/api/teams",
        json={
            "name": "test-team",
            "tournament": "us-open",
            "year": 2026,
            "surface": "hard",
            "players": ["A", "B"],
            "joker": "A",
            "kluns": "B",
        },
    ).json()
    assert saved["name"] == "test-team"
    team_id = saved["id"]

    assert client.get(f"/api/teams/{team_id}").json()["payload"]["joker"] == "A"

    listing = client.get("/api/teams").json()["teams"]
    assert [t["id"] for t in listing] == [team_id]

    assert client.delete(f"/api/teams/{team_id}").status_code == 200
    assert client.get("/api/teams").json()["teams"] == []
    assert client.delete(f"/api/teams/{team_id}").status_code == 404


def test_prediction_reuses_identical_request(client):
    body = {
        "tournament": "us-open",
        "year": 2026,
        "surfaces": ["hard"],
        "draw_url": DRAW,
        "ratings_file": RATINGS,
    }
    first = client.post("/api/predict", json=body).json()["job_id"]
    for _ in range(600):
        status = client.get(f"/api/jobs/{first}").json()
        if status["status"] in ("done", "error"):
            break
        time.sleep(0.2)
    assert status["status"] == "done"

    # identical request returns the cached job instead of recomputing
    second = client.post("/api/predict", json=body).json()["job_id"]
    assert second == first

    # different params start a new job
    other = client.post("/api/predict", json={**body, "surfaces": ["all"]}).json()["job_id"]
    assert other != first


def test_result_contains_source_ages(prediction):
    sources = prediction["result"]["sources"]
    assert "draw_age_hours" in sources
    assert "ratings_age_hours" in sources
    assert sources["draw_age_hours"] is not None  # fixture file exists
