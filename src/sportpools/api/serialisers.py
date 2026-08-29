"""
Serialise pipeline results into plain JSON payloads for the web API.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from sportpools.model.pipeline import ROUNDS, PredictionResult

PROB_COLUMNS = {column: f"p_{i + 1}" for i, column in enumerate(ROUNDS)}


def _pool_records(pool: pd.DataFrame) -> List[dict]:
    """Convert a pool DataFrame into JSON-safe records."""
    frame = pool.copy()
    frame = frame.rename(columns=PROB_COLUMNS)
    numeric_round = {column: 4 for column in PROB_COLUMNS.values()}
    numeric_round.update(
        {"potency": 2, "joker_bonus": 2, "kluns_penalty": 2, "rounds": 0}
    )
    frame = frame.round(numeric_round)
    records = []
    for record in frame.to_dict(orient="records"):
        records.append(
            {
                "player": record["player"],
                "seed": int(record["seed"]),
                "black": int(record["black"]),
                "section": int(record.get("section", 0) or 0),
                "potency": float(record["potency"]),
                "joker_bonus": float(record["joker_bonus"]),
                "kluns_penalty": float(record["kluns_penalty"]),
                "probs": [
                    round(float(record[f"p_{i}"]), 4) for i in range(1, 8)
                ],
            }
        )
    return records


def _team_records(team: dict) -> List[dict]:
    """Convert the optimiser's team schedule into JSON-safe records."""
    schedule = team["schedule"]
    records = []
    for _, row in schedule.iterrows():
        records.append(
            {
                "player": row["player"],
                "seed": int(row["seed"]),
                "black": int(row["black"]),
                "section": int(row.get("section", 0) or 0),
                "role": row["role"],
                "potency": round(float(row["potency"]), 2),
                "joker_bonus": round(float(row["joker_bonus"]), 2),
                "kluns_penalty": round(float(row["kluns_penalty"]), 2),
                "probs": [round(float(row[r]), 4) for r in ROUNDS],
            }
        )
    return records


def _table_records(frame: pd.DataFrame) -> List[dict]:
    """Generic DataFrame -> JSON records with numeric rounding."""
    rounded = frame.round(4)
    result = []
    for record in rounded.to_dict(orient="records"):
        clean = {}
        for key, value in record.items():
            if pd.isna(value):
                continue
            if hasattr(value, "item"):
                value = value.item()
            clean[key] = value
        result.append(clean)
    return result


def serialise_result(result: PredictionResult) -> Dict[str, Any]:
    """
    Convert a PredictionResult into the JSON payload served to the frontend.
    """
    models = {}
    for surface, model in result.models.items():
        models[surface] = {
            "surface": surface,
            "label": {"hard": "Hard-court Elo", "all": "Overall Elo",
                      "clay": "Clay Elo", "grass": "Grass Elo"}.get(surface, surface),
            "team": {
                "players": _team_records(model.team),
                "joker": model.team["joker"],
                "kluns": model.team["kluns"],
                "expected_points": round(float(model.team["expected_points"]), 2),
            },
            "pool": _pool_records(model.pool),
            "joker_options": _table_records(model.joker_options),
            "kluns_options": model.kluns_options,
            "routes": model.routes,
            "matchups": model.matchups,
            "reserves": _table_records(model.reserves),
            "coverage": model.coverage,
        }

    return {
        "tournament": result.request.tournament,
        "year": result.request.year,
        "surfaces": list(result.models.keys()),
        "black_points": result.request.black_points,
        "count": result.request.count,
        "draw_source": result.draw_source,
        "ratings_source": result.ratings_source,
        "sources": {
            "draw_age_hours": result.draw_age_hours,
            "ratings_age_hours": result.ratings_age_hours,
        },
        "models": models,
    }
