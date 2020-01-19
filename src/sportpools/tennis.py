"""
Generate dataset for pool.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd
from pulp import LpMaximize, LpProblem, LpVariable, LpInteger

LOGGER = logging.getLogger(__name__)
ROUNDS = ['r64', 'r32', 'r16', 'qf', 'sm', 'f', 'w']


@dataclass
class Player:
    """
    A single player.
    """
    player: str
    seed: int
    round_odds: float
    terminated: bool = False
    round_index: Optional[int] = 0
    index: Optional[int] = 0

    def __gt__(self, other: Player) -> bool:
        """Determine whether this wins against other."""
        return self.round_odds > other.round_odds

    def __lt__(self, other: Player) -> bool:
        """Determine whether other wins against this player."""
        return self.round_odds < other.round_odds


class TennisPoolEmulator:
    """
    Emulate tennis pool matches.
    """
    standings: pd.DataFrame = None

    def __init__(self, schedule: pd.DataFrame):
        """Initialize object"""
        self._schedule = schedule

    def play_draw(self) -> TennisPoolEmulator:
        """
        Emulate the draw.
        :return: None
        """
        LOGGER.info('Emulating the entire draw')

        for round_str in ROUNDS:
            self.play_round(round_str)

        self.__update_schedule()

        return self

    def add_features(self) -> TennisPoolEmulator:
        """
        Add features based on emulated properties.
        :return:
        """
        self._schedule = self._schedule \
            .pipe(TennisPoolEmulator.determine_score_potency)

        return self

    def get_results(self):
        """Return resulting DataFrame"""
        return self._schedule

    def __update_schedule(self) -> pd.DataFrame:
        """
        Update the original schedule DataFrame with updated rounds the player make it to.
        :return: DataFrame
        """
        LOGGER.info('Updating original schedule')

        player_rounds = pd.DataFrame({
            'player': [p.player for p in self.standings],
            'rounds': [p.round_index for p in self.standings]
        })

        self._schedule = self._schedule.merge(player_rounds, on='player')

        return self._schedule

    def __get_round_odds(self, round_str: str, name: str) -> float:
        """Determine odds per round"""
        return self._schedule[self._schedule['player'] == name][round_str].iloc[0]

    def play_round(self, round_str: str) -> None:
        """
        Play all matches from a single round and update the `standings` value.
        :param round_str: Round name
        :return: None
        """
        LOGGER.info('Emulating round %s', round_str)

        if not self.standings:
            LOGGER.info('Converting pool into list of players')
            self.standings: List[Player] = list(map(
                lambda x: Player(x['player'], x['seed'], -1),
                self._schedule.to_dict(orient='records')))

        LOGGER.info('Assigning odds to player for round %s', round_str)

        for player in self.standings:
            player.round_odds = self.__get_round_odds(round_str, player.player)

        LOGGER.info('Playing matches')
        index = 0
        while index < len(self.standings):
            while self.standings[index].terminated:
                index += 1

            player_one = self.standings[index]
            player_one.index = index

            index += 1
            while self.standings[index].terminated:
                index += 1

            player_two = self.standings[index]
            player_two.index = index

            if player_one > player_two:
                player_two.terminated = True
                player_one.round_index = player_one.round_index + 1

                LOGGER.info('%s d. %s', player_one.player, player_two.player)
            else:
                player_one.terminated = True
                player_two.round_index = player_two.round_index + 1
                LOGGER.info('%s d. %s', player_two.player, player_one.player)

            self.standings[player_one.index] = player_one
            self.standings[player_two.index] = player_two

            index += 1

    @staticmethod
    def determine_score_potency(data: pd.DataFrame) -> pd.DataFrame:
        """
        Determine the number of rounds a player will pass.
        :param data: DataFrame
        :return: DataFrame with number of rounds per player.
        """

        def rounds_to_score(rounds: int, black: int) -> int:
            """
            Determine a player's score based on the number of rounds he makes it to and
            his associated black points.
            :param rounds: Rounds a player passes
            :param black: Black points
            :return: Score
            """
            base_score = rounds * (10 - black)
            second_week_score = max(0, rounds - 3) * (10 - black)
            win_score = 0

            if rounds == 7:
                win_score = 50

            return base_score + second_week_score + win_score

        data['potency'] = data.apply(lambda x: rounds_to_score(x['rounds'], x['black']), axis=1)

        return data


class TennisPool:
    """"Tennis pool data loader"""
    _data: pd.DataFrame = None

    def __init__(self):
        """
        Create Pool object.
        """

    def load_data(self, data_file: str) -> TennisPool:
        """
        Load data and apply basic filtering.
        :param data_file: Path to data file.
        :return: DataFrame of
        """
        LOGGER.info('Loading data from %s', data_file)

        table = pd.read_html(data_file, skiprows=2)[0].drop(1, axis=1)

        filtered = table[table.columns[0:8]]
        filtered.columns = ['player'] + ROUNDS

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
            .pipe(TennisPool.convert_columns, ROUNDS)

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
        Determine the number of rounds a player will pass.
        Black points:
        5: 1 - 2
        4: 3 - 4
        3: 5 - 8
        2: 9 - 16
        1: 17 - 32
        0: None
        :param data: DataFrame
        :return: DataFrame with number of rounds per player.
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
        :param rounds: Number of rounds a player makes it through
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


def optimise_selection(schedule: pd.DataFrame, selection_limit: int, black_points_limit: int) -> pd.DataFrame:
    """
    Optimise player selection.
    :param schedule: Players and their schedule.
    :param selection_limit: Number of players to choose.
    :param black_points_limit: Maximum number of black points.
    :return: Optimal selection
    """
    LOGGER.info('Optimising selection')

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
    probability += sum(param_x[p] for p in param_player) == selection_limit
    probability += sum(black_points[p] * param_x[p] for p in param_player) <= black_points_limit

    # Start solving the problem instance
    probability.solve()

    # Extract solution
    player_selection = [players[p] for p in param_player if param_x[p].varValue]

    LOGGER.info('Optimiser finished')

    return schedule[schedule['player'].isin(player_selection)].copy().reset_index()
