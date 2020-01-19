"""
Generate dataset for pool.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Any, Dict

import pandas as pd
from pulp import LpMaximize, LpProblem, LpVariable, LpInteger

from src.sportpools.emulator import TennisPoolEmulator

LOGGER = logging.getLogger(__name__)


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
        LOGGER.info('Loading data from %s', data_file)
        table = pd.read_html(data_file, skiprows=1)[0].drop(1, axis=1)

        filtered = table[table.columns[0:8]]
        filtered.columns = ['player'] + self._ROUNDS

        self._data = filtered

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
        LOGGER.info('Applying filters')

        self._data = self._data \
            .pipe(TennisPool.extract_seed) \
            .pipe(TennisPool.clean_invalid_rows) \
            .pipe(TennisPool.convert_columns, self._ROUNDS)

        return self

    def add_features(self) -> TennisPool:
        """
        Extract and add features.
        :return: Self
        """
        LOGGER.info('Adding features')

        self._data = self._data \
            .pipe(TennisPool.extract_seed) \
            .pipe(TennisPool.clean_player_name) \
            .pipe(TennisPool.determine_black_points)

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

        data['black'] = data['seed'].map(seed_to_black_points)

        return data

    @staticmethod
    def convert_columns(data: pd.DataFrame, rounds: List[str]) -> pd.DataFrame:
        """
        Convert column data to floats since they're in (string) percentages by default
        :param data: DataFrame
        :param rounds: Number of self._ROUNDS a player makes it through
        :return: DataFrame with converted columns
        """
        LOGGER.info('Converting column data to floats')

        pd.options.mode.chained_assignment = None

        for column in data.columns:
            if column in rounds:
                data[column] = data[column].str.rstrip('%').astype(float) / 100

        return data

    @staticmethod
    def clean_player_name(data: pd.DataFrame) -> pd.DataFrame:
        """
        Remove any additional information from player names
        :param data: DataFrame
        :return: DataFrame with clean player names
        """
        LOGGER.info('Cleaning player names')

        data['player'] = data['player'] \
            .str.replace(r'\(.*?\)', '') \
            .str.strip()

        return data

    @staticmethod
    def clean_invalid_rows(data: pd.DataFrame) -> pd.DataFrame:
        """
        Remove data which is generated for viewing on TennisAbstract.com.
        :param data: DataFrame
        :return: DataFrame with valid rows.
        """
        LOGGER.info('Cleaning invalid rows')

        return data[(data['player'] != 'Player') & (~data['player'].isnull())]

    @staticmethod
    def extract_seed(data: pd.DataFrame) -> pd.DataFrame:
        """
        Extract seed information from player name.
        :param data: DataFrame
        :return: Enriched DataFrame.
        """
        LOGGER.info('Extracting seeds from player names')

        data['seed'] = data['player'] \
            .str.extract(r'(\d+).*') \
            .fillna(0) \
            .astype(int)

        return data


def optimise_selection(schedule_input: pd.DataFrame, selection_limit: int,
                       black_points_limit: int, loser: Optional[str] = None) -> Dict[str, Any]:
    """
    Optimise player selection.
    :param schedule_input: Players and their schedule.
    :param selection_limit: Number of players to choose.
    :param black_points_limit: Maximum number of black points.
    :param loser: Selected loser
    :return: Optimal selection
    """
    LOGGER.info('Optimising selection')

    schedule = schedule_input.copy()
    black_extra = 0
    selection_limit_extra = 0
    extra_loss = 0

    if loser:
        loser_record = schedule[schedule['player'].str.lower() == loser.lower()].iloc[0]

        if loser_record.empty:
            LOGGER.warning('Unable to find player %s in draw', loser)
            loser = None
        else:
            loser = loser_record.player

            extra_loss = TennisPoolEmulator.rounds_to_score(
                loser_record.rounds,
                loser_record.black,
                True
            )

            schedule.loc[schedule.player == loser, 'potency'] = extra_loss

            black_extra = loser_record.black
            selection_limit_extra = 1
            LOGGER.info('Allowing %d extra black points, because of your selected loser', black_extra)
            LOGGER.info('Adding the loser to your selection, and simultaneously increasing the limit of your'
                        'selection, such that your loser is taken into account.')

    black_points_limit += black_extra

    players = schedule['player'].tolist()
    potency = schedule['potency'].tolist()
    black_points = schedule['black'].tolist()

    param_player = range(len(schedule))

    # Declare problem instance, maximization problem
    probability = LpProblem('PlayerSelection', LpMaximize)

    # Declare decision variable x, which is 1 if a
    # player is part of the selection and 0 else
    param_x = LpVariable.matrix('x', list(param_player), 0, 1, LpInteger)

    # Objective function -> Maximize potency
    probability += sum(potency[p] * param_x[p] for p in param_player)

    # Constraint definition
    probability += sum(param_x[p] for p in param_player) == (selection_limit + selection_limit_extra)
    probability += sum(black_points[p] * param_x[p] for p in param_player) <= black_points_limit

    if loser:
        probability += param_x[players.index(loser)] == 1

    # Start solving the problem instance
    probability.solve()

    # Extract solution
    player_selection = [players[p] for p in param_player if param_x[p].varValue]

    LOGGER.info('Optimiser finished')

    if loser:
        LOGGER.warning('Do note you\'re going to lose %d points because of your loser.', -extra_loss)

    return {
        'schedule': schedule[schedule['player'].isin(player_selection)].copy().reset_index(),
        'loser': extra_loss
    }
