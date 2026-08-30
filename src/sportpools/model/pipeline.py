"""
The prediction pipeline shared by the CLI and the web API.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from sportpools.model.draw import parse_draw, validate_draw
from sportpools.model.emulator import TennisPoolEmulator
from sportpools.model.ratings import EloRatingsFetcher, TA_ELO_URL
from sportpools.model.routes import RouteAnalyser
from sportpools.model.simulator import BracketSimulator
from sportpools.model.tennis import TennisPool, optimise_team
from sportpools.webcache import cache_age_hours, fetch_cached

LOGGER = logging.getLogger(__name__)

ROUNDS = ["r64", "r32", "r16", "qf", "sm", "f", "w"]

TOURNAMENT_URLS = {
    "australian-open": "https://en.wikipedia.org/wiki/{year}_Australian_Open_%E2%80%93_Men%27s_singles",
    "roland-garros": "https://en.wikipedia.org/wiki/{year}_French_Open_%E2%80%93_Men%27s_singles",
    "wimbledon": "https://en.wikipedia.org/wiki/{year}_Wimbledon_Championships_%E2%80%93_Men%27s_singles",
    "us-open": "https://en.wikipedia.org/wiki/{year}_US_Open_%E2%80%93_Men%27s_singles",
}

SURFACE_LABELS = {"hard": "hard-court", "clay": "clay", "grass": "grass", "all": "overall"}

ProgressCallback = Callable[[float, str], None]


@dataclass
class PredictionRequest:
    """Input options for one prediction run."""

    tournament: str = "us-open"
    year: int = 2026
    surfaces: Tuple[str, ...] = ("hard", "all")
    black_points: int = 20
    count: int = 15
    draw_url: Optional[str] = None
    ratings_file: Optional[str] = None
    cache_ttl: float = 6.0


@dataclass
class ModelResult:
    """Everything computed for one rating model (one surface)."""

    surface: str
    pool: pd.DataFrame
    team: dict
    joker_options: pd.DataFrame
    kluns_options: List[dict]
    routes: Dict[str, List[dict]]
    matchups: List[dict]
    reserves: pd.DataFrame
    coverage: dict


@dataclass
class PredictionResult:
    """The full outcome of a prediction run."""

    request: PredictionRequest
    models: Dict[str, ModelResult] = field(default_factory=dict)
    draw_source: str = ""
    ratings_source: str = ""
    draw_age_hours: Optional[float] = None
    ratings_age_hours: Optional[float] = None


def run_prediction(
    request: PredictionRequest,
    progress: Optional[ProgressCallback] = None,
) -> PredictionResult:
    """
    Run the full prediction pipeline for every requested surface.
    :param request: Prediction options.
    :param progress: Optional callback receiving (fraction in [0, 1], stage).
    :return: Prediction result with one model per surface.
    """

    def report(fraction: float, stage: str) -> None:
        if progress is not None:
            progress(min(fraction, 1.0), stage)

    report(0.02, "Loading draw")
    draw_df, draw_source, draw_age = _load_draw(request)
    validate_draw(draw_df)

    report(0.08, "Loading Elo ratings")
    ratings_html, ratings_source, ratings_age = _load_ratings_html(request)

    surfaces = list(request.surfaces) or ["hard"]
    n_models = len(surfaces)
    result = PredictionResult(
        request=request,
        draw_source=draw_source,
        ratings_source=ratings_source,
        draw_age_hours=draw_age,
        ratings_age_hours=ratings_age,
    )

    model_span = 0.9 / n_models
    for index, surface in enumerate(surfaces):
        base = 0.08 + index * model_span
        label = SURFACE_LABELS.get(surface, surface)

        report(base + 0.02, f"Simulating bracket ({label} Elo)")
        ratings = EloRatingsFetcher(surface=surface).load_from_html(ratings_html)
        simulator = BracketSimulator(draw_df, ratings, method="elo", best_of=5)
        simulated = simulator.simulate()

        pool = (
            TennisPool(ROUNDS)
            .load_simulated_data(simulated)
            .add_features()
            .get_results()
        )
        pool_results = (
            TennisPoolEmulator(pool)
            .play_draw(ROUNDS)
            .add_features(ROUNDS)
            .get_results()
        )
        # Bracket geometry for the UI (spread, sections), keyed by player.
        pool_results = pool_results.merge(
            draw_df[["player", "section", "position"]], on="player", how="left"
        )
        # Role economics shared by the optimiser and the web evaluator.
        pool_results = pool_results.assign(
            joker_bonus=(50 - 5 * pool_results["black"]) * pool_results[ROUNDS[2]],
            kluns_penalty=-10 * pool_results[ROUNDS[:5]].sum(axis=1),
        )

        report(base + 0.25 * model_span, f"Optimising team ({label} Elo)")
        team = optimise_team(
            pool_results,
            selection_limit=request.count,
            black_points_limit=request.black_points,
            rounds=ROUNDS,
        )

        joker_options = pool_results.nlargest(10, "joker_bonus")[
            ["player", "seed", "black", ROUNDS[2], "joker_bonus", "potency"]
        ].rename(columns={ROUNDS[2]: "p_r4"})

        kluns_options: List[dict] = []
        report(base + 0.32 * model_span, "Evaluating loser alternatives")
        candidates = pool_results["player"].tolist()
        for done, candidate in enumerate(candidates, start=1):
            forced = optimise_team(
                pool_results,
                selection_limit=request.count,
                black_points_limit=request.black_points,
                rounds=ROUNDS,
                forced_kluns=candidate,
            )
            row = pool_results[pool_results["player"] == candidate].iloc[0]
            kluns_options.append(
                {
                    "kluns": candidate,
                    "black": int(row["black"]),
                    "e_penalty": round(float(row["kluns_penalty"]), 2),
                    "team_ev": round(forced["expected_points"], 2),
                }
            )
            if done % 16 == 0 or done == len(candidates):
                share = 0.32 + 0.55 * done / len(candidates)
                report(
                    base + share * model_span,
                    f"Evaluating loser alternatives ({done}/{len(candidates)})",
                )

        kluns_options.sort(key=lambda option: option["team_ev"], reverse=True)
        kluns_options = kluns_options[:10]

        report(base + 0.90 * model_span, f"Computing routes and matchups ({label} Elo)")
        analyser = RouteAnalyser(draw_df, simulated, win_probability=simulator.win_probability)
        routes = analyser.all_routes()
        matchups = analyser.team_matchups(team["schedule"]["player"].tolist())
        reserves = pool_results[~pool_results["player"].isin(team["schedule"]["player"])].nlargest(
            6, "potency"
        )[["player", "seed", "black", "potency", ROUNDS[2], ROUNDS[6]]].rename(
            columns={ROUNDS[2]: "p_r4", ROUNDS[6]: "p_w"}
        )

        result.models[surface] = ModelResult(
            surface=surface,
            pool=pool_results,
            team=team,
            joker_options=joker_options,
            kluns_options=kluns_options,
            routes=routes,
            matchups=matchups,
            reserves=reserves,
            coverage=dict(simulator.coverage),
        )

    report(1.0, "Done")
    return result


def _load_draw(request: PredictionRequest) -> Tuple[pd.DataFrame, str, Optional[float]]:
    """
    Load the draw from an override (URL/file) or the tournament's Wikipedia page.
    :return: Draw DataFrame, a source description and the source's age in hours.
    """
    if request.draw_url:
        source = request.draw_url
        if source.startswith("http"):
            html = fetch_cached(source, ttl_hours=request.cache_ttl)
            description, age = source, cache_age_hours(source)
        else:
            html = Path(source).read_text(encoding="utf-8")
            description = source
            age = _file_age_hours(Path(source))
    else:
        template = TOURNAMENT_URLS.get(request.tournament)
        if not template:
            raise ValueError(
                f"Unknown tournament: {request.tournament}. "
                f"Use one of: {', '.join(TOURNAMENT_URLS)}"
            )
        url = template.format(year=request.year)
        html = fetch_cached(url, ttl_hours=request.cache_ttl)
        description, age = url, cache_age_hours(url)

    draw_df = parse_draw(html).get_results()
    if draw_df.empty:
        raise ValueError(f"No draw data found in {description}")

    LOGGER.info("Loaded draw with %d players from %s", len(draw_df), description)
    return draw_df, description, age


def _load_ratings_html(request: PredictionRequest) -> Tuple[str, str, Optional[float]]:
    """
    Load the Elo report HTML once, shared by all surfaces.
    :return: HTML content, a source description and the source's age in hours.
    """
    if request.ratings_file:
        path = Path(request.ratings_file)
        return path.read_text(encoding="utf-8"), str(path), _file_age_hours(path)
    return (
        fetch_cached(TA_ELO_URL, ttl_hours=request.cache_ttl),
        TA_ELO_URL,
        cache_age_hours(TA_ELO_URL),
    )


def _file_age_hours(path: Path) -> Optional[float]:
    """Age of a local file in hours, if it exists."""
    if not path.exists():
        return None
    return round((time.time() - path.stat().st_mtime) / 3600, 2)
