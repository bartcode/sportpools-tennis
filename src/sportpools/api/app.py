"""
The Sportpools web application: FastAPI backend serving the API and the
built frontend bundle.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sportpools.api.db import STORE
from sportpools.api.jobs import JOBS
from sportpools.api.schemas import (
    EvaluateRequest,
    OptimizeRequest,
    PredictRequest,
    SavedTeamIn,
)
from sportpools.api.serialisers import _team_records
from sportpools.model.pipeline import ROUNDS, TOURNAMENT_URLS, PredictionRequest

TOURNAMENT_LABELS = {
    "us-open": "US Open",
    "wimbledon": "Wimbledon",
    "roland-garros": "Roland Garros",
    "australian-open": "Australian Open",
}

# Month in which each slam's edition typically concludes.
TOURNAMENT_CONCLUSION_MONTHS = {
    "australian-open": 1,
    "roland-garros": 6,
    "wimbledon": 7,
    "us-open": 9,
}
from sportpools.model.tennis import optimise_team

LOGGER = logging.getLogger(__name__)

ROUNDS = ROUNDS


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(title="Sportpools Optimiser", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/tournaments")
    def tournaments() -> dict:
        """
        Selectable tournaments with their edition years. The years are derived
        from the server date (next edition of each slam and its neighbours),
        so new seasons become available without rebuilding the frontend.
        """
        current_year = datetime.now().year
        current_month = datetime.now().month

        tournaments = []
        for key in TOURNAMENT_URLS:
            # Month in which the slam's edition typically concludes; the
            # default year is the next edition that has not finished yet.
            conclusion_month = TOURNAMENT_CONCLUSION_MONTHS.get(key, 12)
            default_year = (
                current_year
                if current_month <= conclusion_month
                else current_year + 1
            )
            tournaments.append(
                {
                    "key": key,
                    "label": TOURNAMENT_LABELS.get(
                        key, key.replace("-", " ").title()
                    ),
                    "years": [default_year - 1, default_year, default_year + 1],
                    "default_year": default_year,
                }
            )

        return {"tournaments": tournaments}

    @app.post("/api/predict")
    def predict(request: PredictRequest) -> dict:
        unknown = [s for s in request.surfaces if s not in ("hard", "clay", "grass", "all")]
        if unknown:
            raise HTTPException(400, f"Unknown surfaces: {unknown}")
        job_id = JOBS.start(
            PredictionRequest(
                tournament=request.tournament,
                year=request.year,
                surfaces=tuple(request.surfaces),
                black_points=request.black_points,
                count=request.count,
                draw_url=request.draw_url,
                ratings_file=request.ratings_file,
                cache_ttl=request.cache_ttl,
            )
        )
        return {"job_id": job_id}

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str) -> dict:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(404, "Unknown job")
        return job.public()

    @app.get("/api/jobs/{job_id}/result")
    def job_result(job_id: str) -> dict:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(404, "Unknown job")
        if job.status == "error":
            raise HTTPException(400, job.error)
        if job.status != "done" or job.result_payload is None:
            raise HTTPException(409, f"Job is {job.status}: {job.stage}")
        return job.result_payload

    @app.post("/api/evaluate")
    def evaluate(request: EvaluateRequest) -> dict:
        job = JOBS.get(request.job_id)
        if job is None or job.status != "done" or job.result_object is None:
            raise HTTPException(404, "Prediction job not available (run one first)")

        model = job.result_object.models.get(request.surface)
        if model is None:
            raise HTTPException(400, f"Model '{request.surface}' not in this prediction")

        return _evaluate_team(model.pool, request.players, request.joker, request.kluns,
                              request.black_points, count=request.count)

    @app.post("/api/optimize")
    def optimize(request: OptimizeRequest) -> dict:
        job = JOBS.get(request.job_id)
        if job is None or job.status != "done" or job.result_object is None:
            raise HTTPException(404, "Prediction job not available (run one first)")

        model = job.result_object.models.get(request.surface)
        if model is None:
            raise HTTPException(400, f"Model '{request.surface}' not in this prediction")

        try:
            team = optimise_team(
                model.pool,
                selection_limit=request.count,
                black_points_limit=request.black_points,
                rounds=ROUNDS,
                forced_kluns=request.kluns,
                forced_joker=request.joker,
                locked_players=request.locked,
            )
        except ValueError as error:
            raise HTTPException(400, str(error)) from error

        return {
            "players": _team_records(team),
            "joker": team["joker"],
            "kluns": team["kluns"],
            "expected_points": round(float(team["expected_points"]), 2),
        }

    @app.get("/api/teams")
    def list_teams() -> dict:
        return {"teams": STORE.list_teams()}

    @app.post("/api/teams")
    def save_team(request: SavedTeamIn) -> dict:
        record = STORE.save_team(
            name=request.name,
            tournament=request.tournament,
            year=request.year,
            surface=request.surface,
            payload={
                "players": request.players,
                "joker": request.joker,
                "kluns": request.kluns,
            },
        )
        return record

    @app.get("/api/teams/{team_id}")
    def get_team(team_id: int) -> dict:
        record = STORE.get_team(team_id)
        if record is None:
            raise HTTPException(404, "Unknown team")
        return record

    @app.delete("/api/teams/{team_id}")
    def delete_team(team_id: int) -> dict:
        if not STORE.delete_team(team_id):
            raise HTTPException(404, "Unknown team")
        return {"deleted": team_id}

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    _mount_frontend(app)
    return app


def _evaluate_team(
    pool: pd.DataFrame,
    players: list,
    joker: str,
    kluns: str,
    black_points_limit: int,
    count: int = 15,
) -> dict:
    """
    Validate a manual selection against the Sportpools rules and compute its
    expected points from the pool's precomputed columns.
    """
    errors = []

    if len(set(players)) != len(players):
        errors.append("Duplicate players in selection")
    if len(players) != count:
        errors.append(f"Selection must have exactly {count} players (now {len(players)})")
    known = pool[pool["player"].isin(players)]
    unknown = [p for p in players if p not in set(pool["player"])]
    if unknown:
        errors.append(f"Unknown players: {', '.join(unknown)}")
    if joker not in players:
        errors.append("Joker is not part of the selection")
    if kluns not in players:
        errors.append("Loser is not part of the selection")
    if joker == kluns:
        errors.append("Joker and loser must be different players")

    rows = known.set_index("player")
    black_used = int(
        rows.loc[[p for p in players if p in rows.index and p != kluns], "black"].sum()
    )
    kluns_black = int(rows.loc[kluns, "black"]) if kluns in rows.index else 0
    if black_used > black_points_limit + kluns_black:
        errors.append(
            f"Black points over budget: {black_used} > {black_points_limit} + {kluns_black} (kluns)"
        )

    breakdown = []
    total = 0.0
    for player in players:
        if player not in rows.index:
            continue
        row = rows.loc[player]
        role = "joker" if player == joker else "kluns" if player == kluns else "player"
        contribution = float(row["potency"])
        if role == "kluns":
            contribution = float(row["kluns_penalty"])
        elif role == "joker":
            contribution += float(row["joker_bonus"])
        total += contribution
        breakdown.append(
            {
                "player": player,
                "seed": int(row["seed"]),
                "black": int(row["black"]),
                "section": int(row.get("section", 0) or 0),
                "position": int(row.get("position", -1) if row.get("position") == row.get("position") else -1),
                "role": role,
                "contribution": round(contribution, 2),
                "potency": round(float(row["potency"]), 2),
                "joker_bonus": round(float(row["joker_bonus"]), 2),
                "kluns_penalty": round(float(row["kluns_penalty"]), 2),
                "probs": [round(float(row[r]), 4) for r in ROUNDS],
            }
        )

    return {
        "valid": not errors,
        "errors": errors,
        "expected_points": round(total, 2),
        "black_points": {
            "used": black_used,
            "limit": black_points_limit + kluns_black,
            "kluns_recycled": kluns_black,
        },
        "players": breakdown,
    }


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built frontend when the bundle exists."""
    web_dir = Path(os.environ.get("SPORTPOOLS_WEB_DIR", "")) if os.environ.get(
        "SPORTPOOLS_WEB_DIR"
    ) else Path(__file__).resolve().parents[3] / "web" / "dist"

    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="frontend")
    else:
        LOGGER.warning(
            "Frontend bundle not found at %s; the API is available under /api. "
            "Build it with: cd web && npm install && npm run build",
            web_dir,
        )


app = create_app()


def main() -> None:
    """Entry point for the `sportpools-ui` console script."""
    import uvicorn

    host = os.environ.get("SPORTPOOLS_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("SPORTPOOLS_UI_PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
