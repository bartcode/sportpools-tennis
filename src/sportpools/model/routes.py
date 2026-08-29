"""
Bracket route analysis: most-likely opponents per round and intra-team
matchup probabilities, derived from the draw geometry and the simulated
round probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

ROUNDS = ["r64", "r32", "r16", "qf", "sm", "f", "w"]

SECTION_QF_PAIR = {1: 2, 2: 1, 3: 4, 4: 3, 5: 6, 6: 5, 7: 8, 8: 7}
# Sections 1-4 form the top half, 5-8 the bottom half.
TOP_HALF = {1, 2, 3, 4}


@dataclass(frozen=True)
class Slot:
    """A player's position in the 128 draw."""

    player: str
    section: int
    position: int


def meet_round(slot_a: Slot, slot_b: Slot) -> int:
    """
    The unique round (1-7) in which two players can meet, given the bracket.

    Within a section the meet round follows from the XOR of their positions;
    across sections it is QF for paired sections (1-2, 3-4, 5-6, 7-8),
    SF within the same half, and the final across halves.
    """
    if slot_a.section == slot_b.section:
        diff = slot_a.position ^ slot_b.position
        return diff.bit_length()

    if SECTION_QF_PAIR[slot_a.section] == slot_b.section:
        return 5
    same_half = (slot_a.section in TOP_HALF) == (slot_b.section in TOP_HALF)
    return 6 if same_half else 7


def opponent_region(section: int, position: int, round_index: int) -> List[Tuple[int, int]]:
    """
    All (section, position) slots a player can face in a given round.

    Rounds 1-4 stay within the player's own section; round 5 is the paired
    section, round 6 the two sections in the same half, round 7 the four
    sections in the other half.
    """
    if round_index <= 4:
        block = 2 ** round_index
        half = block // 2
        block_start = (position // block) * block
        sibling_start = block_start if position % block >= half else block_start + half
        return [
            (section, pos)
            for pos in range(sibling_start, sibling_start + half)
        ]

    if round_index == 5:
        pair = SECTION_QF_PAIR[section]
        return [(pair, pos) for pos in range(16)]

    if round_index == 6:
        same_half_sections = [1, 2, 3, 4] if section in TOP_HALF else [5, 6, 7, 8]
        pair = SECTION_QF_PAIR[section]
        others = [s for s in same_half_sections if s != pair]
        return [(s, pos) for s in others for pos in range(16)]

    other_half = [5, 6, 7, 8] if section in TOP_HALF else [1, 2, 3, 4]
    return [(s, pos) for s in other_half for pos in range(16)]


def wins_before(round_index: int) -> Optional[str]:
    """Round column holding the probability of reaching a given round."""
    if round_index <= 1:
        return None
    return ROUNDS[round_index - 2]


class RouteAnalyser:
    """
    Compute modal routes (most-likely opponent per round) and pair meeting
    probabilities for a simulated draw.
    """

    def __init__(
        self,
        draw_df: pd.DataFrame,
        probs_df: pd.DataFrame,
        win_probability=None,
    ):
        """
        :param draw_df: Draw with player, seed, section, position.
        :param probs_df: Simulated probabilities with player and r64..w columns.
        :param win_probability: Callable (player, opponent) -> win probability;
            optional, beat-chances are omitted when not provided.
        """
        self._slots: Dict[str, Slot] = {
            row["player"]: Slot(row["player"], int(row["section"]), int(row["position"]))
            for _, row in draw_df.iterrows()
        }
        self._probs: Dict[str, Dict[str, float]] = {
            row["player"]: {r: float(row[r]) for r in ROUNDS}
            for _, row in probs_df.iterrows()
        }
        self._win_probability = win_probability

        self._by_slot: Dict[Tuple[int, int], str] = {
            (slot.section, slot.position): slot.player for slot in self._slots.values()
        }

    def _reach(self, player: str, round_index: int) -> float:
        """Probability the player wins his first (round_index - 1) matches."""
        column = wins_before(round_index)
        if column is None:
            return 1.0
        return self._probs.get(player, {}).get(column, 0.0)

    def _wins(self, player: str, round_index: int) -> float:
        """Probability the player wins his first round_index matches."""
        if round_index < 1:
            return 1.0
        return self._probs.get(player, {}).get(ROUNDS[round_index - 1], 0.0)

    def modal_route(self, player: str) -> List[dict]:
        """
        The most likely opponent for each round, with the chance the opponent
        is actually there, the chance of beating him, and the chance of
        surviving the round.
        """
        slot = self._slots.get(player)
        if slot is None:
            return []

        route = []
        for round_index in range(1, 8):
            region = opponent_region(slot.section, slot.position, round_index)
            candidates = []
            for section, position in region:
                opponent = self._by_slot.get((section, position))
                if opponent is None or opponent == player:
                    continue
                candidates.append((self._reach(opponent, round_index), opponent))

            if not candidates:
                continue

            p_there, opponent = max(candidates, key=lambda c: (c[0], c[1]))
            entry = {
                "round": round_index,
                "opponent": opponent,
                "p_opponent": round(p_there, 4),
                "p_meet": round(self._reach(player, round_index) * p_there, 4),
                "p_reach": round(self._wins(player, round_index), 4),
            }
            if self._win_probability is not None:
                entry["p_beat"] = round(self._win_probability(player, opponent), 4)
            route.append(entry)

        return route

    def all_routes(self) -> Dict[str, List[dict]]:
        """Modal routes for every player in the draw."""
        return {player: self.modal_route(player) for player in self._slots}

    def meeting_probability(self, player_a: str, player_b: str) -> Optional[dict]:
        """
        Probability two players meet, and the round at which that can happen.
        """
        slot_a, slot_b = self._slots.get(player_a), self._slots.get(player_b)
        if slot_a is None or slot_b is None:
            return None

        round_index = meet_round(slot_a, slot_b)
        p_meet = self._reach(player_a, round_index) * self._reach(player_b, round_index)

        return {
            "a": player_a,
            "b": player_b,
            "round": round_index,
            "p_meet": round(p_meet, 4),
        }

    def team_matchups(self, players: List[str]) -> List[dict]:
        """
        All pairwise meeting chances within a selection, ordered by the
        round they would meet and then by probability.
        """
        matchups = []
        for i, player_a in enumerate(players):
            for player_b in players[i + 1:]:
                result = self.meeting_probability(player_a, player_b)
                if result:
                    matchups.append(result)

        matchups.sort(key=lambda m: (m["round"], -m["p_meet"]))
        return matchups
