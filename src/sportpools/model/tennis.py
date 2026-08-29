"""
Generate dataset for pool.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Any, Dict

import pandas as pd
from pulp import LpMaximize, LpProblem, LpVariable, LpInteger, PULP_CBC_CMD

from sportpools.model.emulator import TennisPoolEmulator

LOGGER = logging.getLogger(__name__)

SOLVER = PULP_CBC_CMD(msg=False)


class TennisPool:
    """"Tennis pool data loader"""

    _data: pd.DataFrame = None

    def __init__(self, rounds: List[str]):
        """
        Create Pool object.
        :param rounds: Rounds to process.
        """
        self._ROUNDS = rounds

    def load_data(self, data_file: str) -> TennisPool:
        """
        Load data and apply basic filtering.
        :param data_file: Path to data file.
        :return: DataFrame with required columns.
        """
        LOGGER.info("Loading data from %s", data_file)
        table = pd.read_html(data_file, skiprows=1)[0].drop(1, axis=1)

        filtered = table[table.columns[0:8]]
        filtered.columns = ["player"] + self._ROUNDS

        self._data = filtered

        return self

    def load_simulated_data(self, simulated: pd.DataFrame) -> TennisPool:
        """
        Load pre-computed simulated round probabilities.
        :param simulated: DataFrame with player, seed, r64..w columns.
        :return: Self.
        """
        LOGGER.info("Loading simulated data with %d players", len(simulated))

        self._data = simulated[["player"] + self._ROUNDS].copy()
        self._data["seed"] = simulated["seed"].astype(int)

        return self

    def get_results(self) -> pd.DataFrame:
        """
        Return generated DataFrame.
        :return: DataFrame
        """
        return self._data

    def apply_filters(self) -> TennisPool:
        """
        Apply filters to clean the data.
        :return: Self
        """
        LOGGER.info("Applying filters")

        self._data = (
            self._data.pipe(TennisPool.extract_seed)
            .pipe(TennisPool.clean_invalid_rows)
            .pipe(TennisPool.convert_columns, self._ROUNDS)
        )

        return self

    def add_features(self) -> TennisPool:
        """
        Extract and add features.
        :return: Self
        """
        LOGGER.info("Adding features")

        if "seed" not in self._data.columns:
            self._data = self._data.pipe(TennisPool.extract_seed)
        else:
            self._data = self._data.assign(
                seed=self._data["seed"].fillna(0).astype(int)
            )

        self._data = (
            self._data.pipe(TennisPool.clean_player_name)
            .pipe(TennisPool.deduce_missing_seeds)
            .pipe(TennisPool.determine_black_points)
        )

        return self

    @staticmethod
    def determine_black_points(data: pd.DataFrame) -> pd.DataFrame:
        """
        Determine the number of self._ROUNDS a player will pass.
        Black points:
        5: 1 - 2
        4: 3 - 4
        3: 5 - 8
        2: 9 - 16
        1: 17 - 32
        0: None
        :param data: DataFrame
        :return: DataFrame with number of self._ROUNDS per player.
        """

        def seed_to_black_points(seed: int) -> int:
            """
            Translate seed number into black points.
            :param seed: Seed of player
            :return: Black points associated to seed.
            """
            points = 1

            if not seed or pd.isna(seed) or seed == 0 or seed > 32:
                points = 0
            elif seed < 3:
                points = 5
            elif seed < 5:
                points = 4
            elif seed < 9:
                points = 3
            elif seed < 17:
                points = 2

            return points

        data = data.assign(black=data["seed"].map(seed_to_black_points))

        return data

    @staticmethod
    def convert_columns(data: pd.DataFrame, rounds: List[str]) -> pd.DataFrame:
        """
        Convert column data to floats since they're in (string) percentages by default
        :param data: DataFrame
        :param rounds: Number of self._ROUNDS a player makes it through
        :return: DataFrame with converted columns
        """
        LOGGER.info("Converting column data to floats")

        for column in data.columns:
            if column in rounds:
                data = data.assign(
                    **{column: data[column].str.rstrip("%").astype(float) / 100}
                )

        return data

    @staticmethod
    def clean_player_name(data: pd.DataFrame) -> pd.DataFrame:
        """
        Remove any additional information from player names
        :param data: DataFrame
        :return: DataFrame with clean player names
        """
        LOGGER.info("Cleaning player names")

        data = data.assign(
            player=data["player"].str.replace(r"\(.*?\)", "", regex=True).str.strip()
        )

        return data

    @staticmethod
    def clean_invalid_rows(data: pd.DataFrame) -> pd.DataFrame:
        """
        Remove data which is generated for viewing on TennisAbstract.com.
        :param data: DataFrame
        :return: DataFrame with valid rows.
        """
        LOGGER.info("Cleaning invalid rows")

        return data[(data["player"] != "Player") & (~data["player"].isnull())]

    @staticmethod
    def extract_seed(data: pd.DataFrame) -> pd.DataFrame:
        """
        Extract seed information from player name.
        :param data: DataFrame
        :return: Enriched DataFrame.
        """
        LOGGER.info("Extracting seeds from player names")

        data = data.assign(
            seed=data["player"].str.extract(r"(\d+).*").fillna(0).astype(int)
        )

        return data

    @staticmethod
    def deduce_missing_seeds(data: pd.DataFrame) -> pd.DataFrame:
        """
        Backfill seed markers that Tennis Abstract dropped from the export.

        A Grand Slam draw splits into 16 sections of 8 players, each anchored by
        exactly two seeds at line positions 0 and 7 (32 seeds total). When the
        forecast HTML omits a ``(NN)`` marker, the seed is still recoverable:
        every anchor slot that is empty corresponds to a seed number missing from
        the contiguous 1..32 range.

        :param data: DataFrame in draw order, cleaned of separator rows.
        :return: DataFrame with backfilled seeds.
        """
        seeds = data["seed"].astype(int).tolist()
        section_size = 8
        n = len(seeds)
        # ponytail: anchor slots are the first/last line of each 8-player section;
        # multiple dropped markers in one draw are assigned in positional order,
        # which is exact for the common single-drop case and a heuristic beyond it.
        anchors = [i for i in range(n) if i % section_size in (0, section_size - 1)]

        expected = set(range(1, (n // section_size) * 2 + 1))
        marked = {s for s in seeds if s > 0}
        missing = sorted(expected - marked)
        empty = [i for i in anchors if seeds[i] == 0]

        for idx, seed_num in zip(empty, missing):
            seeds[idx] = seed_num
            player = data["player"].iloc[idx]
            LOGGER.info("Deduced seed %d for %s (marker missing from source)", seed_num, player)

        data = data.assign(seed=seeds)
        return data


def optimise_selection(
    schedule_input: pd.DataFrame,
    selection_limit: int,
    black_points_limit: int,
    rounds: List[str],
    loser: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Optimise player selection.
    :param schedule_input: Players and their schedule.
    :param selection_limit: Number of players to choose.
    :param black_points_limit: Maximum number of black points.
    :param rounds: Rounds to play
    :param loser: Selected loser
    :return: Optimal selection
    """
    LOGGER.info("Optimising selection")

    schedule = schedule_input.copy()
    black_extra = 0
    selection_limit_extra = 0
    extra_loss = 0

    if loser:
        loser_records = schedule[schedule["player"].str.lower() == loser.lower()]

        if loser_records.empty:
            LOGGER.warning("Unable to find player %s in draw", loser)
            loser = None
        else:
            loser_record = loser_records.iloc[0]
            loser = loser_record.player

            # extra_loss = TennisPoolEmulator.rounds_to_score(
            #     rounds=loser_record.rounds,
            #     black=loser_record.black,
            #     loser=True
            # )

            extra_loss = TennisPoolEmulator.probabilities_to_score(
                round_probs=loser_record[rounds], black=loser_record.black, loser=True
            )

            schedule.loc[schedule.player == loser, "potency"] = extra_loss

            black_extra = loser_record.black
            selection_limit_extra = 1
            LOGGER.info(
                "Allowing %d extra black points, because of your selected loser",
                black_extra,
            )
            LOGGER.info(
                "Adding the loser to your selection, and simultaneously increasing the limit of your"
                "selection, such that your loser is taken into account."
            )

    black_points_limit += black_extra

    players = schedule["player"].tolist()
    potency = schedule["potency"].tolist()
    black_points = schedule["black"].tolist()

    param_player = range(len(schedule))

    # Declare problem instance, maximization problem
    probability = LpProblem("PlayerSelection", LpMaximize)

    # Declare decision variable x, which is 1 if a
    # player is part of the selection and 0 else
    param_x = LpVariable.matrix("x", list(param_player), 0, 1, LpInteger)

    # Objective function -> Maximise potency
    probability += sum(potency[p] * param_x[p] for p in param_player)

    # Constraint definition
    probability += sum(param_x[p] for p in param_player) == (
        selection_limit + selection_limit_extra
    )
    probability += (
        sum(black_points[p] * param_x[p] for p in param_player) <= black_points_limit
    )

    if loser:
        probability += param_x[players.index(loser)] == 1

    # Start solving the problem instance
    probability.solve(SOLVER)

    # Extract solution
    player_selection = [players[p] for p in param_player if param_x[p].varValue]

    LOGGER.info("Optimiser finished")

    if loser:
        LOGGER.warning(
            "Do note you're going to lose %d points because of your loser.", -extra_loss
        )

    return {
        "schedule": schedule[schedule["player"].isin(player_selection)]
        .copy()
        .reset_index(),
        "loser": extra_loss,
    }


def optimise_team(
    schedule_input: pd.DataFrame,
    selection_limit: int,
    black_points_limit: int,
    rounds: List[str],
    forced_kluns: Optional[str] = None,
    forced_joker: Optional[str] = None,
    locked_players: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Optimise the full Sportpools team: normal players, joker and kluns.

    Maximises total expected points under the real Sportpools rules:
    - a team counts `selection_limit` players, one of which is the joker and
      one the kluns (distinct players, both within the selection);
    - normal players score 10-black per win, doubled from round 4, +50 for
      the title (`potency`);
    - the joker scores normally plus a one-time bonus of (50 - 5*black) for
      reaching round 4;
    - the kluns scores nothing but loses 10 points per round he advances
      (capped at 50);
    - the kluns's black points don't count against the budget and grant that
      many extra budget points for the remaining selection.

    :param schedule_input: Players with potency, black and round probabilities.
    :param selection_limit: Total team size (including joker and kluns).
    :param black_points_limit: Black points budget for the non-kluns players.
    :param rounds: Round column names, in win order (r64 first).
    :param forced_kluns: Player to force as kluns, for comparing alternatives.
    :param locked_players: Players forced into the selection (kept when
        re-optimising around manual choices).
    :return: Optimal selection with roles and expected points.
    """
    if selection_limit < 2:
        raise ValueError("selection_limit must be at least 2 (joker + kluns)")

    LOGGER.debug("Optimising team of %d players (joker and kluns included)", selection_limit)

    schedule = schedule_input.copy().reset_index(drop=True)

    # One-time joker bonus for reaching round 4 = winning the first 3 matches.
    # Expected kluns penalty: 10 per round advanced, capped at 50 in total.
    schedule = schedule.assign(
        joker_bonus=(50 - 5 * schedule["black"]) * schedule[rounds[2]],
        kluns_penalty=-10 * schedule[rounds[:5]].sum(axis=1),
    )

    players = schedule["player"].tolist()
    potency = schedule["potency"].tolist()
    black_points = schedule["black"].tolist()
    joker_bonus = schedule["joker_bonus"].tolist()
    kluns_penalty = schedule["kluns_penalty"].tolist()

    param_player = range(len(schedule))

    problem = LpProblem("TeamSelection", LpMaximize)

    # x: selected, j: joker, k: kluns
    param_x = LpVariable.matrix("x", list(param_player), 0, 1, LpInteger)
    param_j = LpVariable.matrix("j", list(param_player), 0, 1, LpInteger)
    param_k = LpVariable.matrix("k", list(param_player), 0, 1, LpInteger)

    problem += sum(
        potency[p] * (param_x[p] - param_k[p])
        + joker_bonus[p] * param_j[p]
        + kluns_penalty[p] * param_k[p]
        for p in param_player
    )

    problem += sum(param_x[p] for p in param_player) == selection_limit
    problem += sum(param_j[p] for p in param_player) == 1
    problem += sum(param_k[p] for p in param_player) == 1

    if forced_kluns is not None:
        if forced_kluns not in players:
            raise ValueError(f"Unknown forced kluns: {forced_kluns}")
        problem += param_k[players.index(forced_kluns)] == 1

    if forced_joker is not None:
        if forced_joker not in players:
            raise ValueError(f"Unknown forced joker: {forced_joker}")
        problem += param_j[players.index(forced_joker)] == 1

    for locked in locked_players or []:
        if locked not in players:
            raise ValueError(f"Unknown locked player: {locked}")
        problem += param_x[players.index(locked)] == 1

    for p in param_player:
        problem += param_j[p] <= param_x[p]
        problem += param_k[p] <= param_x[p]
        problem += param_j[p] + param_k[p] <= 1

    # The kluns's black points are recycled: they neither count against the
    # budget nor consume it, and add their value as extra budget.
    problem += (
        sum(black_points[p] * (param_x[p] - 2 * param_k[p]) for p in param_player)
        <= black_points_limit
    )

    problem.solve(SOLVER)

    selected = [players[p] for p in param_player if param_x[p].varValue]
    joker = [players[p] for p in param_player if param_j[p].varValue][0]
    kluns = [players[p] for p in param_player if param_k[p].varValue][0]

    result = schedule[schedule["player"].isin(selected)].copy().reset_index(drop=True)
    result = result.assign(
        role=[
            "joker" if player == joker else "kluns" if player == kluns else "player"
            for player in result["player"]
        ]
    )

    LOGGER.debug(
        "Optimiser finished: joker=%s, kluns=%s, expected points=%.1f",
        joker,
        kluns,
        _team_expected_points(result),
    )

    return {
        "schedule": result,
        "joker": joker,
        "kluns": kluns,
        "expected_points": _team_expected_points(result),
    }


def _team_expected_points(selection: pd.DataFrame) -> float:
    """
    Compute total expected points of a selection with roles assigned.
    """
    points = 0.0
    for _, row in selection.iterrows():
        if row["role"] == "kluns":
            points += row["kluns_penalty"]
        else:
            points += row["potency"]
            if row["role"] == "joker":
                points += row["joker_bonus"]
    return float(points)
