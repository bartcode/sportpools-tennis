"""
Simulate tournament brackets to estimate round-by-round advancement probabilities.
"""
from __future__ import annotations

import logging
import math
import unicodedata
from typing import Dict, List, Optional, Tuple

import pandas as pd

LOGGER = logging.getLogger(__name__)

ROUNDS = ["r64", "r32", "r16", "qf", "sm", "f", "w"]

DEFAULT_SCALE = 1.50
DEFAULT_FALLBACK_DR = 0.95
DEFAULT_FALLBACK_ELO = 1550

QF_MATCHUPS = [(1, 2), (3, 4), (5, 6), (7, 8)]
SF_MATCHUPS = [((1, 2), (3, 4)), ((5, 6), (7, 8))]
F_MATCHUP = (((1, 2), (3, 4)), ((5, 6), (7, 8)))


def _normalize(name: str) -> str:
    """Remove accents and lowercase a name."""
    decomposed = unicodedata.normalize("NFD", name)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return stripped.lower()


def _parse_draw_name(name: str) -> Tuple[str, str]:
    """
    Parse a draw-style name like 'JM Cerundolo' or 'J-L Struff'.
    Returns (initials, last_name) where initials are lowercased and
    last_name is the normalized last word.
    """
    parts = name.strip().split(None, 1)
    if len(parts) < 2:
        return _normalize(name), ""
    raw_initials = parts[0].replace("-", "").replace(".", "")
    raw_last = parts[1].strip()
    last_word = raw_last.split()[-1] if raw_last else ""
    return _normalize(raw_initials), _normalize(last_word)


def _parse_rating_name(name: str) -> Tuple[str, str]:
    """
    Parse a rating-style name like 'Juan Manuel Cerundolo'.
    Returns (first_initial, last_name) where first_initial is the
    lowercased first character and last_name is the normalized last word.
    """
    parts = name.strip().split()
    if len(parts) < 2:
        return _normalize(name), ""
    first_initial = _normalize(parts[0])[0] if parts else ""
    last_word = parts[-1] if parts else ""
    return first_initial, _normalize(last_word)


def _fuzzy_match(draw_name: str, rating_names: List[str]) -> Optional[str]:
    """
    Find the best fuzzy match for a draw name among rating names.
    Tries last-word matching first, then full last-part matching.
    Returns the matched rating name or None.
    """
    draw_init, draw_last = _parse_draw_name(draw_name)
    if not draw_last:
        return None

    candidates = []
    for rname in rating_names:
        r_init, r_last = _parse_rating_name(rname)
        if r_last == draw_last and r_init == draw_init[0]:
            candidates.append(rname)

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        for rname in candidates:
            r_parts = rname.strip().split()
            r_initials = "".join(_normalize(p)[0] for p in r_parts[:-1])
            if r_initials == draw_init:
                return rname
        return candidates[0]

    draw_parts = draw_name.strip().split(None, 1)
    if len(draw_parts) >= 2:
        draw_last_full = _normalize(draw_parts[1]).replace(" ", "").replace("-", "")
        for rname in rating_names:
            r_parts = rname.strip().split(None, 1)
            if len(r_parts) < 2:
                continue
            r_init = _normalize(r_parts[0])[0]
            r_last_full = _normalize(r_parts[1]).replace(" ", "").replace("-", "")
            if r_last_full == draw_last_full and r_init == draw_init[0]:
                return rname

    # Compound-surname match: draws often shorten 'Daniel Merida Aguilar' to
    # 'D Merida', dropping later surname tokens. Match on any surname token.
    # The draw initial may reference any leading name ('D Vallejo' for
    # 'Adolfo Daniel Vallejo'), so accept any leading initial here.
    if len(draw_parts) >= 2:
        token_candidates = []
        for rname in rating_names:
            r_parts = rname.strip().split(None, 1)
            if len(r_parts) < 2:
                continue
            leading_initials = {_normalize(t)[0] for t in r_parts[0:1]}
            surname_tokens = _normalize(r_parts[1]).replace("-", " ").split()
            surname_leads = {t[0] for t in surname_tokens[:-1]} if len(surname_tokens) > 1 else set()
            if draw_init and draw_init[0] not in (leading_initials | surname_leads):
                continue
            if draw_last in surname_tokens:
                token_candidates.append(rname)
        if len(token_candidates) == 1:
            return token_candidates[0]

    return None


class BracketSimulator:
    """Simulate a tennis tournament bracket to compute round probabilities."""

    def __init__(
        self,
        draw: pd.DataFrame,
        ratings: pd.DataFrame,
        scale: float = DEFAULT_SCALE,
        method: str = "elo",
        best_of: int = 5,
    ):
        self._draw = draw.copy()
        self._ratings = ratings.copy()
        self._scale = scale
        self._method = method.lower()
        self._best_of = best_of
        self._rating_col = "elo" if self._method == "elo" else "dr"
        self._player_strength: Dict[str, float] = {}
        self.coverage: Dict[str, object] = {}

    def simulate(self) -> pd.DataFrame:
        """
        Run full bracket simulation and compute per-player round probabilities.
        :return: DataFrame with player, seed, r64..w.
        """
        self._merge_ratings()

        section_results = {}
        for section_idx in sorted(self._draw["section"].unique()):
            players = self._draw[self._draw["section"] == section_idx].sort_values("position")["player"].tolist()
            section_results[section_idx] = self._simulate_section(players)

        full_results = self._propagate_sections(section_results)

        rows = []
        for section_idx in sorted(self._draw["section"].unique()):
            section_draw = self._draw[self._draw["section"] == section_idx].sort_values("position")
            for _, draw_row in section_draw.iterrows():
                player = draw_row["player"]
                seed = int(draw_row["seed"])
                pos = int(draw_row["position"])
                probs = full_results[section_idx].get(pos, {})
                row = {"player": player, "seed": seed}
                for r in ROUNDS:
                    row[r] = probs.get(r, 0.0)
                rows.append(row)

        return pd.DataFrame(rows)

    def _merge_ratings(self):
        """Merge draw with ratings using fuzzy name matching."""
        rating_map = dict(zip(self._ratings["player"], self._ratings[self._rating_col]))
        rank_map = dict(zip(
            self._ratings["player"],
            self._ratings["rank"].fillna(999).astype(int),
        ))

        valid_vals = [v for v in rating_map.values() if not (isinstance(v, float) and math.isnan(v))]
        if self._method == "elo":
            default_val = min(valid_vals) - 50 if valid_vals else DEFAULT_FALLBACK_ELO
        else:
            default_val = min(valid_vals) - 0.05 if valid_vals else DEFAULT_FALLBACK_DR

        rating_names = list(rating_map.keys())

        exact = fuzzy = fallback = 0
        fallback_players = []
        for player in self._draw["player"].unique():
            val = None
            rank = 999

            if player in rating_map and not (
                isinstance(rating_map[player], float) and math.isnan(rating_map[player])
            ):
                val = rating_map[player]
                rank = rank_map.get(player, 999)
                exact += 1
            else:
                matched = _fuzzy_match(player, rating_names)
                if matched:
                    val = rating_map[matched]
                    rank = rank_map.get(matched, 999)
                    fuzzy += 1
                    LOGGER.debug("Fuzzy matched draw '%s' -> rating '%s'", player, matched)
                else:
                    fallback += 1
                    fallback_players.append(player)

            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                self._player_strength[player] = val
            else:
                self._player_strength[player] = _estimate_from_rank(
                    rank if val is not None else 999, default_val, self._method
                )

        LOGGER.info(
            "Rating coverage: %d exact, %d fuzzy, %d estimated from ranking",
            exact, fuzzy, fallback,
        )
        if fallback_players:
            LOGGER.warning(
                "No rating found for %s; using rank-based estimates", ", ".join(fallback_players)
            )
        self.coverage = {
            "exact": exact,
            "fuzzy": fuzzy,
            "estimated": fallback,
            "unmatched": fallback_players,
        }

    def _simulate_section(self, players: List[str]) -> Dict[int, Dict[str, float]]:
        """
        Simulate a 16-player section to compute probabilities for rounds 1-4.
        :param players: 16 players in bracket order.
        :return: Dict mapping position index to {round_name: probability}.
        """
        n = len(players)
        reach = {}
        for i in range(n):
            reach[(i, 0)] = 1.0

        half_size = 1
        round_idx = 1

        while half_size * 2 <= n:
            block_size = half_size * 2

            for block_start in range(0, n, block_size):
                left = list(range(block_start, min(block_start + half_size, n)))
                right = list(range(block_start + half_size, min(block_start + half_size * 2, n)))

                for i in left:
                    reach_before = reach.get((i, round_idx - 1), 0)
                    if reach_before == 0:
                        reach[(i, round_idx)] = 0.0
                        continue
                    win_prob = sum(
                        reach.get((j, round_idx - 1), 0) * self._wp(players[i], players[j])
                        for j in right
                    )
                    reach[(i, round_idx)] = reach_before * win_prob

                for j in right:
                    reach_before = reach.get((j, round_idx - 1), 0)
                    if reach_before == 0:
                        reach[(j, round_idx)] = 0.0
                        continue
                    win_prob = sum(
                        reach.get((i, round_idx - 1), 0) * self._wp(players[j], players[i])
                        for i in left
                    )
                    reach[(j, round_idx)] = reach_before * win_prob

            round_idx += 1
            half_size *= 2

        n_rounds = round_idx - 1
        section_round_names = _section_round_names(n)

        result = {}
        for i in range(n):
            probs = {}
            for r in range(1, n_rounds + 1):
                idx = r - 1
                rname = section_round_names[idx] if idx < len(section_round_names) else f"r{r}"
                probs[rname] = reach.get((i, r), 0.0)
            result[i] = probs

        return result

    def _propagate_sections(
        self, section_results: Dict[int, Dict[int, Dict[str, float]]]
    ) -> Dict[int, Dict[int, Dict[str, float]]]:
        """
        Propagate section-level results to full tournament QF/SF/F/W probabilities.
        :param section_results: Per-section round probabilities.
        :return: Updated per-section probabilities with full tournament rounds.
        """
        full = {}
        for sec, positions in section_results.items():
            full[sec] = {}
            for pos, probs in positions.items():
                full[sec][pos] = dict(probs)

        section_winner_probs = {}
        for sec in range(1, 9):
            section_winner_probs[sec] = {}
            for pos, probs in section_results.get(sec, {}).items():
                qf_prob = probs.get("qf", 0.0)
                if qf_prob > 0:
                    players = self._draw[self._draw["section"] == sec].sort_values("position")["player"].tolist()
                    if pos < len(players):
                        section_winner_probs[sec][pos] = (players[pos], qf_prob)

        sf_probs = self._compute_sf_probs(section_winner_probs)
        f_probs = self._compute_f_probs(sf_probs, section_winner_probs)
        w_probs = self._compute_w_probs(f_probs, sf_probs, section_winner_probs)

        for sec in range(1, 9):
            for pos in full.get(sec, {}):
                player_entry = section_winner_probs.get(sec, {}).get(pos)
                if player_entry:
                    full[sec][pos]["sm"] = sf_probs.get(sec, {}).get(pos, 0.0)
                    full[sec][pos]["f"] = f_probs.get(sec, {}).get(pos, 0.0)
                    full[sec][pos]["w"] = w_probs.get(sec, {}).get(pos, 0.0)
                else:
                    full[sec][pos]["sm"] = 0.0
                    full[sec][pos]["f"] = 0.0
                    full[sec][pos]["w"] = 0.0

        return full

    def _strength(self, player: str) -> float:
        """Get player strength with appropriate default."""
        default = DEFAULT_FALLBACK_ELO if self._method == "elo" else DEFAULT_FALLBACK_DR
        return self._player_strength.get(player, default)

    def win_probability(self, player_a: str, player_b: str) -> float:
        """
        Probability that player_a beats player_b under this simulator's model.
        :param player_a: Player name as it appears in the draw.
        :param player_b: Opponent name.
        :return: Win probability in [0, 1].
        """
        return self._wp(player_a, player_b)

    def _wp(self, player_a: str, player_b: str) -> float:
        """Win probability helper using stored strengths."""
        return _win_prob(self._strength(player_a), self._strength(player_b), self._scale, self._method, self._best_of)

    def _compute_sf_probs(
        self, section_winner_probs: Dict[int, Dict[int, tuple]]
    ) -> Dict[int, Dict[int, float]]:
        """Compute SF (semifinal) reaching probabilities."""
        sf_probs = {}

        for sec_a, sec_b in QF_MATCHUPS:
            for pos_a, (player_a, qf_a) in section_winner_probs.get(sec_a, {}).items():
                p_beat_b = sum(
                    qf_b * self._wp(player_a, player_b)
                    for _, (player_b, qf_b) in section_winner_probs.get(sec_b, {}).items()
                )
                sf_probs.setdefault(sec_a, {})[pos_a] = qf_a * p_beat_b

            for pos_b, (player_b, qf_b) in section_winner_probs.get(sec_b, {}).items():
                p_beat_a = sum(
                    qf_a * self._wp(player_b, player_a)
                    for _, (player_a, qf_a) in section_winner_probs.get(sec_a, {}).items()
                )
                sf_probs.setdefault(sec_b, {})[pos_b] = qf_b * p_beat_a

        return sf_probs

    def _compute_f_probs(
        self,
        sf_probs: Dict[int, Dict[int, float]],
        section_winner_probs: Dict[int, Dict[int, tuple]],
    ) -> Dict[int, Dict[int, float]]:
        """Compute F (final) reaching probabilities."""
        f_probs = {}

        for (sec_a, sec_b), (sec_c, sec_d) in SF_MATCHUPS:
            sections_left = [sec_a, sec_b]
            sections_right = [sec_c, sec_d]

            for sec in sections_left:
                for pos, (player, _) in section_winner_probs.get(sec, {}).items():
                    sf_p = sf_probs.get(sec, {}).get(pos, 0.0)
                    if sf_p == 0:
                        f_probs.setdefault(sec, {})[pos] = 0.0
                        continue
                    p_beat_right = sum(
                        sf_probs.get(sec_r, {}).get(pos_r, 0.0)
                        * self._wp(player, player_r)
                        for sec_r in sections_right
                        for pos_r, (player_r, _) in section_winner_probs.get(sec_r, {}).items()
                    )
                    f_probs.setdefault(sec, {})[pos] = sf_p * p_beat_right

            for sec in sections_right:
                for pos, (player, _) in section_winner_probs.get(sec, {}).items():
                    sf_p = sf_probs.get(sec, {}).get(pos, 0.0)
                    if sf_p == 0:
                        f_probs.setdefault(sec, {})[pos] = 0.0
                        continue
                    p_beat_left = sum(
                        sf_probs.get(sec_l, {}).get(pos_l, 0.0)
                        * self._wp(player, player_l)
                        for sec_l in sections_left
                        for pos_l, (player_l, _) in section_winner_probs.get(sec_l, {}).items()
                    )
                    f_probs.setdefault(sec, {})[pos] = sf_p * p_beat_left

        return f_probs

    def _compute_w_probs(
        self,
        f_probs: Dict[int, Dict[int, float]],
        sf_probs: Dict[int, Dict[int, float]],
        section_winner_probs: Dict[int, Dict[int, tuple]],
    ) -> Dict[int, Dict[int, float]]:
        """Compute W (winner) probabilities."""
        w_probs = {}
        top_sections = [1, 2, 3, 4]
        bottom_sections = [5, 6, 7, 8]

        for sec in top_sections:
            for pos, (player, _) in section_winner_probs.get(sec, {}).items():
                f_p = f_probs.get(sec, {}).get(pos, 0.0)
                if f_p == 0:
                    w_probs.setdefault(sec, {})[pos] = 0.0
                    continue
                p_beat_bottom = sum(
                    f_probs.get(sec_b, {}).get(pos_b, 0.0)
                    * self._wp(player, player_b)
                    for sec_b in bottom_sections
                    for pos_b, (player_b, _) in section_winner_probs.get(sec_b, {}).items()
                )
                w_probs.setdefault(sec, {})[pos] = f_p * p_beat_bottom

        for sec in bottom_sections:
            for pos, (player, _) in section_winner_probs.get(sec, {}).items():
                f_p = f_probs.get(sec, {}).get(pos, 0.0)
                if f_p == 0:
                    w_probs.setdefault(sec, {})[pos] = 0.0
                    continue
                p_beat_top = sum(
                    f_probs.get(sec_t, {}).get(pos_t, 0.0)
                    * self._wp(player, player_t)
                    for sec_t in top_sections
                    for pos_t, (player_t, _) in section_winner_probs.get(sec_t, {}).items()
                )
                w_probs.setdefault(sec, {})[pos] = f_p * p_beat_top

        return w_probs


def _win_prob(val_a: float, val_b: float, scale: float, method: str = "dr", best_of: int = 3) -> float:
    """
    Probability that player A beats player B.
    For Elo: P = 1 / (1 + 10^((B - A) / 400)), then convert to best-of-N.
    For DR: adaptive sigmoid.
    """
    if method == "elo":
        p_bo3 = 1.0 / (1.0 + 10 ** ((val_b - val_a) / 400.0))
        if best_of == 5:
            return _bo3_to_bo5(p_bo3)
        return p_bo3
    diff = val_a - val_b
    abs_diff = abs(diff)
    effective_scale = scale / (1.0 + 4.0 * abs_diff)
    try:
        return 1.0 / (1.0 + math.exp(-diff / effective_scale))
    except OverflowError:
        return 1.0 if diff > 0 else 0.0


def _bo3_to_bo5(p_bo3: float) -> float:
    """
    Convert best-of-3 match win probability to best-of-5.
    
    Solves p_bo3 = 3s^2 - 2s^3 for s (set win probability),
    then computes p_bo5 = 10s^3 - 15s^4 + 6s^5.
    """
    if abs(p_bo3 - 0.5) < 1e-10:
        return 0.5
    lo, hi = 0.0, 1.0
    for _ in range(50):
        mid = (lo + hi) / 2.0
        p = 3.0 * mid * mid - 2.0 * mid * mid * mid
        if p < p_bo3:
            lo = mid
        else:
            hi = mid
    s = (lo + hi) / 2.0
    return 10 * s**3 - 15 * s**4 + 6 * s**5


def _section_round_names(n: int) -> List[str]:
    """Map section round indices to tournament round names."""
    if n >= 16:
        return ["r64", "r32", "r16", "qf", "sm", "f", "w"]
    elif n == 8:
        return ["r64", "r32", "r16", "qf", "sm", "f", "w"]
    elif n == 4:
        return ["r32", "r16", "qf", "sm", "f", "w"]
    else:
        return ROUNDS


def _estimate_from_rank(rank: int, default_val: float, method: str = "elo") -> float:
    """Estimate rating from ATP ranking for players without match data."""
    if method == "elo":
        if rank <= 5:
            return 2100
        elif rank <= 10:
            return 1950
        elif rank <= 20:
            return 1900
        elif rank <= 50:
            return 1825
        elif rank <= 100:
            return 1750
        elif rank <= 200:
            return 1650
        else:
            return default_val
    else:
        if rank <= 10:
            return 1.10
        elif rank <= 20:
            return 1.05
        elif rank <= 50:
            return 1.00
        elif rank <= 100:
            return 0.97
        elif rank <= 200:
            return 0.93
        else:
            return default_val


def _estimate_dr_from_rank(rank: int, default_dr: float) -> float:
    """Estimate DR from ATP ranking for players without match data."""
    return _estimate_from_rank(rank, default_dr, "dr")
