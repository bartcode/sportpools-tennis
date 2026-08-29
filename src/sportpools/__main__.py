"""
Sportpools optimiser
"""
import argparse
import logging.config

import coloredlogs
import pandas as pd

from sportpools.model.pipeline import (
    PredictionRequest,
    ROUNDS,
    TOURNAMENT_URLS,
    run_prediction,
)
from sportpools.model.tennis import optimise_selection

coloredlogs.install()
LOGGER = logging.getLogger(__name__)


def main() -> None:
    """
    Parse arguments and perform main functionality.
    :return: None
    """
    parser = argparse.ArgumentParser(
        description="Optimise your Sportpools player selection"
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "-f",
        "--file",
        help="Path to Tennis Abstract forecast HTML file (legacy mode)",
        type=str,
    )
    mode_group.add_argument(
        "--tournament",
        help="Tournament name (australian-open/roland-garros/wimbledon/us-open)",
        type=str,
    )

    parser.add_argument(
        "--year",
        help="Tournament year",
        type=int,
        default=2026,
    )
    parser.add_argument(
        "--draw-url",
        help="URL or file path for the draw (overrides tournament name)",
        type=str,
    )
    parser.add_argument(
        "--ratings-data",
        help="Path to ratings data: an Elo report HTML file (elo method) or "
        "Tennis Abstract JS data files (dr method)",
        nargs="+",
        type=str,
    )
    parser.add_argument(
        "--rating-method",
        help="Rating method: elo (default, uses TA Elo) or dr (legacy, uses DR)",
        type=str,
        default="elo",
        choices=["elo", "dr"],
    )
    parser.add_argument(
        "--surface",
        help="Surface filter for ratings (clay/grass/hard/all)",
        type=str,
        default="all",
    )
    parser.add_argument(
        "--span",
        help="Time span for ratings (last52/career)",
        type=str,
        default="last52",
    )
    parser.add_argument(
        "--scale",
        help="Scale parameter for win probability model",
        type=float,
        default=1.50,
    )
    parser.add_argument(
        "--cache-ttl",
        help="Hours fetched pages stay cached (0 always refetches)",
        type=float,
        default=6.0,
    )
    parser.add_argument(
        "-b",
        "--black-points",
        "--black",
        help="Total number of black points to use",
        type=int,
        default=20,
    )
    parser.add_argument(
        "-c",
        "--count",
        "--player-count",
        help="Number of players to select (default: 14 in forecast mode, "
        "15 in simulation mode where the joker and kluns count along)",
        type=int,
        default=None,
    )
    parser.add_argument(
        "-l", "--loser", help="Selected loser", type=str,
    )

    args, _ = parser.parse_known_args()

    if args.file:
        _run_forecast_mode(args)
    else:
        _run_simulation_mode(args)


def _run_forecast_mode(args) -> None:
    """
    Run the legacy forecast-based mode.
    :param args: Parsed arguments.
    """
    from sportpools.model.emulator import TennisPoolEmulator
    from sportpools.model.tennis import TennisPool

    pool = TennisPool(ROUNDS).load_data(args.file).apply_filters().add_features()

    emulator = TennisPoolEmulator(pool.get_results())

    pool_results = emulator.play_draw(ROUNDS).add_features(ROUNDS).get_results()

    selection_optimum = optimise_selection(
        pool_results,
        selection_limit=args.count or 14,
        black_points_limit=args.black_points,
        rounds=ROUNDS,
        loser=args.loser,
    )

    _print_results(selection_optimum)


def _run_simulation_mode(args) -> None:
    """
    Run the simulation-based mode using the shared prediction pipeline.
    :param args: Parsed arguments.
    """
    if args.rating_method != "elo":
        # The DR path predates the pipeline; it keeps its own loading logic.
        return _run_dr_mode(args)

    request = PredictionRequest(
        tournament=args.tournament,
        year=args.year,
        surfaces=(args.surface,),
        black_points=args.black_points,
        count=args.count or 15,
        draw_url=args.draw_url,
        ratings_file=args.ratings_data[0] if args.ratings_data else None,
        cache_ttl=args.cache_ttl,
    )

    result = run_prediction(request, progress=lambda f, s: LOGGER.info("[%3.0f%%] %s", f * 100, s))

    model = result.models[request.surfaces[0]]
    _print_team_results(model, black_points_limit=args.black_points)


def _run_dr_mode(args) -> None:
    """
    Run the simulation mode with Dominance Ratio ratings.
    :param args: Parsed arguments.
    """
    from sportpools.model.draw import validate_draw
    from sportpools.model.emulator import TennisPoolEmulator
    from sportpools.model.pipeline import _load_draw
    from sportpools.model.ratings import RatingsCalculator
    from sportpools.model.simulator import BracketSimulator
    from sportpools.model.tennis import TennisPool, optimise_team

    request = PredictionRequest(
        tournament=args.tournament,
        year=args.year,
        draw_url=args.draw_url,
        cache_ttl=args.cache_ttl,
    )
    draw_df, _ = _load_draw(request)
    validate_draw(draw_df)

    calculator = RatingsCalculator(surface=args.surface, span=args.span)
    if args.ratings_data:
        calculator.load_from_files(args.ratings_data)
    else:
        calculator.fetch_from_web(ttl_hours=args.cache_ttl)
    ratings_df = calculator.compute_ratings()

    simulator = BracketSimulator(draw_df, ratings_df, scale=args.scale, method="dr", best_of=5)
    simulated = simulator.simulate()

    pool = TennisPool(ROUNDS).load_simulated_data(simulated).add_features()
    pool_results = (
        TennisPoolEmulator(pool.get_results())
        .play_draw(ROUNDS)
        .add_features(ROUNDS)
        .get_results()
    )
    pool_results = pool_results.assign(
        joker_bonus=(50 - 5 * pool_results["black"]) * pool_results[ROUNDS[2]],
        kluns_penalty=-10 * pool_results[ROUNDS[:5]].sum(axis=1),
    )

    team = optimise_team(
        pool_results,
        selection_limit=args.count or 15,
        black_points_limit=args.black_points,
        rounds=ROUNDS,
    )

    model = type("ModelResult", (), {
        "team": team,
        "kluns_options": [],
        "reserves": pool_results[~pool_results["player"].isin(
            team["schedule"]["player"]
        )].nlargest(6, "potency")[["player", "seed", "black", "potency"]],
    })()

    _print_team_results(model, black_points_limit=args.black_points)


def _print_team_results(model, black_points_limit: int = 20) -> None:
    """
    Print a model result with roles, probabilities and role analyses.
    :param model: A ModelResult-like object (team, pool, options).
    :param black_points_limit: Black points budget for the non-kluns players.
    """
    schedule = model.team["schedule"].sort_values(
        by=["role"], key=lambda s: s.map({"kluns": 2, "joker": 1, "player": 0})
    )

    report = schedule.assign(
        P_R4=schedule[ROUNDS[2]],
        P_QF=schedule[ROUNDS[3]],
        P_SF=schedule[ROUNDS[4]],
        P_F=schedule[ROUNDS[5]],
        P_W=schedule[ROUNDS[6]],
    )[
        [
            "role", "player", "seed", "black", "potency",
            "P_R4", "P_QF", "P_SF", "P_F", "P_W",
            "joker_bonus", "kluns_penalty",
        ]
    ].round(
        {"potency": 1, "P_R4": 3, "P_QF": 3, "P_SF": 3, "P_F": 3, "P_W": 3,
         "joker_bonus": 1, "kluns_penalty": 1}
    )

    LOGGER.info("=== OPTIMAL SPORTPOOLS TEAM ===")
    LOGGER.info("\r\n%s", report.to_string(index=False))

    kluns_row = schedule[schedule["role"] == "kluns"].iloc[0]
    kluns_black = int(kluns_row["black"])
    black_used = int(schedule.loc[schedule["role"] != "kluns", "black"].sum())

    LOGGER.info(
        "Expected points: %.1f | Black points: %d/%d used (%d recycled from kluns)",
        model.team["expected_points"],
        black_used,
        black_points_limit + kluns_black,
        kluns_black,
    )

    _print_joker_analysis(model, schedule)
    _print_kluns_analysis(model, kluns_row, black_points_limit)

    reserves = model.reserves
    table = reserves.assign(
        P_R4=reserves[ROUNDS[2]],
        P_W=reserves[ROUNDS[6]],
    )[["player", "seed", "black", "potency", "P_R4", "P_W"]].round(
        {"potency": 1, "P_R4": 3, "P_W": 3}
    )

    LOGGER.info("=== RESERVE SUGGESTIONS ===")
    LOGGER.info("\r\n%s", table.to_string(index=False))


def _print_joker_analysis(model, schedule: pd.DataFrame) -> None:
    """
    Explain the joker choice: bonus formula and candidates within the team.
    """
    joker_row = schedule[schedule["role"] == "joker"].iloc[0]
    black = int(joker_row["black"])
    p_r4 = float(joker_row[ROUNDS[2]])

    LOGGER.info("=== JOKER: %s ===", joker_row["player"])
    LOGGER.info(
        "One-time bonus for reaching round 4: (50 - 5*%d) x %.0f%% = %.1f points",
        black,
        p_r4 * 100,
        float(joker_row["joker_bonus"]),
    )

    candidates = schedule.assign(P_R4=schedule[ROUNDS[2]]).nlargest(5, "joker_bonus")[
        ["player", "black", "P_R4", "joker_bonus", "potency"]
    ].round({"P_R4": 3, "joker_bonus": 1, "potency": 1})

    LOGGER.info("Joker candidates within the team (by bonus):")
    LOGGER.info("\r\n%s", candidates.to_string(index=False))


def _print_kluns_analysis(model, kluns_row, black_points_limit: int) -> None:
    """
    Explain the kluns choice: exit-round chances, penalty and alternatives.
    """
    p_win1, p_win2, p_win3 = (float(kluns_row[r]) for r in ROUNDS[:3])

    LOGGER.info("=== KLUNS: %s (seed %s, %d black point(s)) ===",
                kluns_row["player"], int(kluns_row["seed"]) or "unseeded",
                int(kluns_row["black"]))
    LOGGER.info(
        "Chances: out in R1 %.0f%% | out in R2 %.0f%% | out in R3 %.0f%% | reaches R4+ %.1f%%"
        " | title %.1f%%",
        (1 - p_win1) * 100,
        (p_win1 - p_win2) * 100,
        (p_win2 - p_win3) * 100,
        p_win3 * 100,
        float(kluns_row[ROUNDS[6]]) * 100,
    )
    LOGGER.info(
        "Expected penalty: %.1f points (-10 per round advanced, capped at 50); "
        "black points recycled: +%d (budget %d -> %d)",
        float(kluns_row["kluns_penalty"]),
        int(kluns_row["black"]),
        black_points_limit,
        black_points_limit + int(kluns_row["black"]),
    )

    if model.kluns_options:
        table = pd.DataFrame(model.kluns_options[:8])
        table = table.assign(delta_vs_best=(table["team_ev"] - table["team_ev"].max()).round(1))
        LOGGER.info(
            "Best kluns choices (total team expected points with that kluns):"
        )
        LOGGER.info("\r\n%s", table.to_string(index=False))


def _print_results(selection_optimum: dict) -> None:
    """
    Print legacy forecast-mode results.
    :param selection_optimum: Optimisation output dict.
    """
    LOGGER.info("Optimal set of players is as follows:")
    LOGGER.info("\r\n%s", selection_optimum["schedule"].head(25))

    LOGGER.info(
        "The selection of these players results in %d points with %d black points",
        selection_optimum["schedule"]["potency"].sum(),
        selection_optimum["schedule"]["black"].sum(),
    )
    LOGGER.info("Select your joker in this order:")
    LOGGER.info(
        "\r\n%s",
        str(
            selection_optimum["schedule"][selection_optimum["schedule"]["rounds"] >= 4]
                .sort_values(by=["black"], ascending=True)
                .head(5)
        ),
    )


if __name__ == "__main__":
    main()
