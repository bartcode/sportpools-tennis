"""
Emulates the Sportpools process.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, List

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)


@dataclass
class Player:
    """
    A single player.
    """

    player: str
    seed: int
    round_odds: float
    loser: bool = False
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

    def play_draw(self, rounds: List[str]) -> TennisPoolEmulator:
        """
        Emulate the draw.
        :return: None
        """
        LOGGER.info("Emulating the entire draw")

        for round_str in rounds:
            self.play_round(round_str)

        self.__update_schedule()

        return self

    def add_features(self, rounds: List[str]) -> TennisPoolEmulator:
        """
        Add features based on emulated properties.
        :param rounds: Rounds to play
        :return: DataFrame
        """
        self._schedule = self._schedule.pipe(
            TennisPoolEmulator.determine_score_potency, rounds
        )

        return self

    def get_results(self):
        """Return resulting DataFrame"""
        return self._schedule

    def __update_schedule(self) -> pd.DataFrame:
        """
        Update the original schedule DataFrame with updated rounds the player make it to.
        :return: DataFrame
        """
        LOGGER.info("Updating original schedule")

        player_rounds = pd.DataFrame(
            {
                "player": [p.player for p in self.standings],
                "rounds": [p.round_index for p in self.standings],
            }
        )

        self._schedule = self._schedule.merge(player_rounds, on="player")

        return self._schedule

    def __get_round_odds(self, round_str: str, name: str) -> float:
        """Determine odds per round"""
        return self._schedule[self._schedule["player"] == name][round_str].iloc[0]

    def play_round(self, round_str: str) -> None:
        """
        Play all matches from a single round and update the `standings` value.
        :param round_str: Round name
        :return: None
        """
        LOGGER.info("Emulating round %s", round_str)

        if not self.standings:
            LOGGER.debug("Converting pool into list of players")
            self.standings: List[Player] = list(
                map(
                    lambda x: Player(x["player"], x["seed"], -1),
                    self._schedule.to_dict(orient="records"),
                )
            )

        LOGGER.debug("Assigning odds to player for round %s", round_str)

        for player in self.standings:
            player.round_odds = self.__get_round_odds(round_str, player.player)

        LOGGER.debug("Playing matches")
        index = 0
        try:
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

                    LOGGER.info("%s d. %s", player_one.player, player_two.player)
                else:
                    player_one.terminated = True
                    player_two.round_index = player_two.round_index + 1
                    LOGGER.info("%s d. %s", player_two.player, player_one.player)

                self.standings[player_one.index] = player_one
                self.standings[player_two.index] = player_two

                index += 1
        except IndexError:
            pass

    @staticmethod
    def rounds_to_score(rounds: int, black: int, loser: bool) -> int:
        """
        Determine a player's score based on the number of rounds he makes it to and
        his associated black points.
        :param rounds: Rounds a player passes
        :param black: Black points
        :param loser: Whether the player is marked as 'loser'.
        :return: Score
        """
        if loser:
            return rounds * -10

        base_score = rounds * (10 - black)
        second_week_score = max(0, rounds - 3) * (10 - black)
        win_score = 0

        if rounds == 7:
            win_score = 50

        return base_score + second_week_score + win_score

    @staticmethod
    def probabilities_to_score(
        round_probs: List[float], black: int, loser: bool
    ) -> float:
        """
        Determine a player's score based on the probabilities per round
        his associated black points.
        :param round_probs: Probabilities per round.
        :param black: Black points
        :param loser: Whether the player is marked as 'loser'.
        :return: Score
        """
        first_week = sum(round_probs[round_probs.index[:3]] * (10 - black))
        second_week = sum(round_probs[round_probs.index[3:-1]] * (2 * (10 - black)))
        win = round_probs[-1] * 50

        if loser:
            return sum(np.array(round_probs) * (10 - black))

        return first_week + second_week + win

    @staticmethod
    def determine_score_potency(data: pd.DataFrame, rounds: List[str]) -> pd.DataFrame:
        """
        Determine the number of rounds a player will pass.
        :param data: DataFrame
        :param rounds: Rounds to play
        :return: DataFrame with number of rounds per player.
        """
        # This is an alternative scoring which can be used as well.
        # data['potency'] = data.apply(lambda x: TennisPoolEmulator.rounds_to_score(x['rounds'], x['black'], False),
        #                              axis=1)

        data["potency"] = data.apply(
            lambda x, r: TennisPoolEmulator.probabilities_to_score(
                x[r], x["black"], False
            ),
            axis=1,
            r=rounds,
        )

        return data
