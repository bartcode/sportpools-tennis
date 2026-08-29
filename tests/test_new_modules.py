import math

import pandas as pd
import pytest

from sportpools.model.draw import DrawParser
from sportpools.model.ratings import RatingsCalculator
from sportpools.model.simulator import BracketSimulator, _win_prob, _bo3_to_bo5, _estimate_from_rank, _estimate_dr_from_rank, ROUNDS
from sportpools.model.tennis import TennisPool


class TestDrawParser:
    def test_parse_seed_cell_empty(self):
        seed, entry = DrawParser._parse_seed_cell("")
        assert seed == 0
        assert entry == ""

    def test_parse_seed_cell_number(self):
        seed, entry = DrawParser._parse_seed_cell("1")
        assert seed == 1
        assert entry == ""

    def test_parse_seed_cell_qualifier(self):
        seed, entry = DrawParser._parse_seed_cell("Q")
        assert seed == 0
        assert entry == "Q"

    def test_parse_seed_cell_wildcard(self):
        seed, entry = DrawParser._parse_seed_cell("WC")
        assert seed == 0
        assert entry == "WC"

    def test_parse_seed_cell_lucky_loser(self):
        seed, entry = DrawParser._parse_seed_cell("LL")
        assert seed == 0
        assert entry == "LL"

    def test_parse_seed_cell_protected_ranking(self):
        seed, entry = DrawParser._parse_seed_cell("PR")
        assert seed == 0
        assert entry == "PR"

    def test_parse_seed_cell_two_digit(self):
        seed, entry = DrawParser._parse_seed_cell("30")
        assert seed == 30
        assert entry == ""

    def test_get_results_empty(self):
        parser = DrawParser()
        result = parser.get_results()
        assert isinstance(result, pd.DataFrame)
        assert result.empty


class TestRatingsCalculator:
    def test_compute_ratings_empty(self):
        calc = RatingsCalculator()
        result = calc.compute_ratings()
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_parse_rankings(self):
        js = "crank = {'Novak Djokovic': 1, 'Jannik Sinner': 2};"
        rankings = RatingsCalculator._parse_rankings(js)
        assert rankings["Novak Djokovic"] == 1
        assert rankings["Jannik Sinner"] == 2

    def test_surface_filter_clay(self):
        calc = RatingsCalculator(surface="clay")
        assert calc._surface == "Clay"

    def test_surface_filter_hard(self):
        calc = RatingsCalculator(surface="hard")
        assert calc._surface == "Hard"

    def test_surface_filter_grass(self):
        calc = RatingsCalculator(surface="grass")
        assert calc._surface == "Grass"

    def test_surface_filter_all(self):
        calc = RatingsCalculator(surface="all")
        assert calc._surface is None

    def test_compute_ratings_with_data(self):
        calc = RatingsCalculator(surface="all", span="career")
        calc._matches = [
            {"player": "Player A", "surf": "Clay", "date": "20240101",
             "pts": 100, "fwon": 40, "swon": 30, "opts": 100, "ofwon": 40, "oswon": 30,
             "orank": 50},
            {"player": "Player A", "surf": "Hard", "date": "20240601",
             "pts": 100, "fwon": 45, "swon": 30, "opts": 100, "ofwon": 35, "oswon": 25,
             "orank": 60},
            {"player": "Player B", "surf": "Clay", "date": "20240201",
             "pts": 80, "fwon": 35, "swon": 25, "opts": 80, "ofwon": 30, "oswon": 20,
             "orank": 40},
        ]
        result = calc.compute_ratings()
        assert len(result) == 2
        assert "dr" in result.columns
        assert "spw" in result.columns
        assert "rpw" in result.columns
        assert result["dr"].notna().all()


class TestSimulator:
    @pytest.fixture
    def sample_draw(self):
        players = []
        for section in range(1, 9):
            for pos in range(16):
                seed = 0
                if pos == 0:
                    seed = (section - 1) * 2 + 1
                elif pos == 15:
                    seed = section * 2
                players.append({
                    "player": f"Player S{section}P{pos}",
                    "seed": seed,
                    "entry": "",
                    "section": section,
                    "position": pos,
                })
        return pd.DataFrame(players)

    @pytest.fixture
    def sample_ratings(self):
        rows = []
        for section in range(1, 9):
            for pos in range(16):
                dr = 1.0 + 0.05 * (16 - pos) / 16
                rows.append({
                    "player": f"Player S{section}P{pos}",
                    "dr": dr,
                    "elo": 1500 + 50 * (16 - pos) / 16,
                    "spw": 0.65,
                    "rpw": 0.35,
                    "matches": 50,
                    "rank": pos + 1,
                })
        return pd.DataFrame(rows)

    def test_win_prob_equal(self):
        prob = _win_prob(1.0, 1.0, 0.15)
        assert abs(prob - 0.5) < 1e-6

    def test_win_prob_higher_dr(self):
        prob = _win_prob(1.2, 0.8, 0.15)
        assert prob > 0.5

    def test_win_prob_lower_dr(self):
        prob = _win_prob(0.8, 1.2, 0.15)
        assert prob < 0.5

    def test_win_prob_elo_equal(self):
        prob = _win_prob(1800.0, 1800.0, 0.15, "elo")
        assert abs(prob - 0.5) < 1e-6

    def test_win_prob_elo_higher(self):
        prob = _win_prob(1900.0, 1700.0, 0.15, "elo")
        assert prob > 0.5

    def test_win_prob_elo_100_points(self):
        prob = _win_prob(1900.0, 1800.0, 0.15, "elo")
        assert abs(prob - 0.64) < 0.02

    def test_win_prob_elo_bo5_equal(self):
        prob = _win_prob(1800.0, 1800.0, 0.15, "elo", best_of=5)
        assert abs(prob - 0.5) < 1e-6

    def test_win_prob_elo_bo5_favorites_favored(self):
        p_bo3 = _win_prob(1900.0, 1800.0, 0.15, "elo")
        p_bo5 = _win_prob(1900.0, 1800.0, 0.15, "elo", best_of=5)
        assert p_bo5 > p_bo3

    def test_bo3_to_bo5_conversion(self):
        assert abs(_bo3_to_bo5(0.5) - 0.5) < 1e-6
        assert abs(_bo3_to_bo5(1.0) - 1.0) < 1e-6
        assert abs(_bo3_to_bo5(0.0) - 0.0) < 1e-6
        assert _bo3_to_bo5(0.64) > 0.64
        assert _bo3_to_bo5(0.76) > 0.76

    def test_simulate_basic(self, sample_draw, sample_ratings):
        sim = BracketSimulator(sample_draw, sample_ratings, scale=0.15, method="dr")
        result = sim.simulate()

        assert len(result) == 128
        for col in ["player", "seed"] + ROUNDS:
            assert col in result.columns

        for col in ROUNDS:
            assert (result[col] >= 0).all()
            assert (result[col] <= 1).all()

        for section in range(1, 9):
            sec_players = result[result["player"].str.contains(f"S{section}")]
            assert len(sec_players) == 16

    def test_simulate_probabilities_decreasing(self, sample_draw, sample_ratings):
        sim = BracketSimulator(sample_draw, sample_ratings, scale=0.15, method="dr")
        result = sim.simulate()

        for _, row in result.iterrows():
            probs = [row[r] for r in ROUNDS]
            for i in range(len(probs) - 1):
                assert probs[i] >= probs[i + 1] - 1e-6, \
                    f"Probabilities not decreasing for {row['player']}: {probs}"

    def test_simulate_top_seeded_favored(self, sample_draw, sample_ratings):
        sim = BracketSimulator(sample_draw, sample_ratings, scale=0.15, method="dr")
        result = sim.simulate()

        top_seeded = result[result["seed"].isin([1, 2, 3, 4])]

        if not top_seeded.empty:
            avg_top_qf = top_seeded["qf"].mean()
            all_avg_qf = result["qf"].mean()
            assert avg_top_qf >= all_avg_qf

    def test_estimate_dr_from_rank(self):
        assert _estimate_dr_from_rank(1, 0.9) == 1.10
        assert _estimate_dr_from_rank(15, 0.9) == 1.05
        assert _estimate_dr_from_rank(40, 0.9) == 1.00
        assert _estimate_dr_from_rank(75, 0.9) == 0.97
        assert _estimate_dr_from_rank(150, 0.9) == 0.93
        assert _estimate_dr_from_rank(300, 0.9) == 0.9

    def test_simulate_elo_basic(self, sample_draw, sample_ratings):
        sim = BracketSimulator(sample_draw, sample_ratings, method="elo")
        result = sim.simulate()
        assert len(result) == 128
        for col in ["player", "seed"] + ROUNDS:
            assert col in result.columns
        for col in ROUNDS:
            assert (result[col] >= 0).all()
            assert (result[col] <= 1).all()


class TestTennisPoolSimulated:
    def test_load_simulated_data(self):
        simulated = pd.DataFrame({
            "player": ["Player A", "Player B", "Player C"],
            "seed": [1, 2, 0],
            "r64": [0.95, 0.90, 0.50],
            "r32": [0.85, 0.75, 0.25],
            "r16": [0.70, 0.55, 0.10],
            "qf": [0.50, 0.35, 0.03],
            "sm": [0.30, 0.20, 0.01],
            "f": [0.15, 0.10, 0.00],
            "w": [0.08, 0.05, 0.00],
        })

        pool = TennisPool(ROUNDS).load_simulated_data(simulated).add_features()

        result = pool.get_results()
        assert len(result) == 3
        assert "black" in result.columns
        assert result.iloc[0]["black"] == 5
        assert result.iloc[1]["black"] == 5
        assert result.iloc[2]["black"] == 0


# --- New: TennisTemple parser, validation, matching, scoring, team optimiser ---

from pathlib import Path

from sportpools.model.draw import (
    TennisTempleDrawParser,
    parse_draw,
    validate_draw,
)
from sportpools.model.simulator import _fuzzy_match
from sportpools.model.emulator import TennisPoolEmulator
from sportpools.model.tennis import optimise_team

FIXTURES = Path(__file__).parent / "fixtures"
TT_FIXTURE = FIXTURES / "tennistemple_us_open_2026_draw.html"
WIKI_FIXTURE = FIXTURES / "wikipedia_us_open_2026_mens_singles.html"

requires_tt_fixture = pytest.mark.skipif(
    not TT_FIXTURE.exists(), reason="TennisTemple fixture not available"
)
requires_wiki_fixture = pytest.mark.skipif(
    not WIKI_FIXTURE.exists(), reason="Wikipedia fixture not available"
)


class TestTennisTempleParser:
    def test_reorder_name(self):
        assert TennisTempleDrawParser._reorder_name("Zverev A.") == "A Zverev"
        assert TennisTempleDrawParser._reorder_name("Diaz Acosta F.") == "F Diaz Acosta"
        assert TennisTempleDrawParser._reorder_name("Wu Y.") == "Y Wu"
        assert TennisTempleDrawParser._reorder_name("Cerundolo J. M.") == "JM Cerundolo"
        # No trailing initial: unchanged
        assert TennisTempleDrawParser._reorder_name("Novak Djokovic") == "Novak Djokovic"

    @requires_tt_fixture
    def test_parse_real_draw(self):
        df = TennisTempleDrawParser().parse_file(str(TT_FIXTURE)).get_results()

        assert len(df) == 128
        assert set(df["section"]) == {i for i in range(1, 9)}

        first = df.iloc[0]
        assert first["player"] == "A Zverev"
        assert first["seed"] == 1
        assert first["section"] == 1
        assert first["position"] == 0

        last = df.iloc[-1]
        assert last["player"] == "C Alcaraz"
        assert last["seed"] == 2
        assert last["section"] == 8
        assert last["position"] == 15

        dimitrov = df[df["player"] == "G Dimitrov"].iloc[0]
        assert dimitrov["entry"] == "Q"

    @requires_tt_fixture
    def test_parse_draw_factory_detects_tennistemple(self):
        parser = parse_draw(TT_FIXTURE.read_text(encoding="utf-8"))
        assert isinstance(parser, TennisTempleDrawParser)
        assert not parser.get_results().empty

    @requires_tt_fixture
    @requires_wiki_fixture
    def test_cross_source_agreement(self):
        tt = TennisTempleDrawParser().parse_file(str(TT_FIXTURE)).get_results()
        wiki = DrawParser().parse_file(str(WIKI_FIXTURE)).get_results()

        merged = tt.merge(wiki, on=["section", "position"], suffixes=("_tt", "_wiki"))
        assert len(merged) == 128
        assert (merged["seed_tt"] == merged["seed_wiki"]).all()

        # Sources abbreviate compound surnames differently (TennisTemple
        # 'D Merida Aguilar' vs Wikipedia 'D Merida') and diacritics differ;
        # after accent-stripping, the shorter surname must be a token-prefix
        # of the longer one.
        import unicodedata

        def strip_accents(text):
            return "".join(
                c for c in unicodedata.normalize("NFD", text)
                if unicodedata.category(c) != "Mn"
            )

        def surname_tokens(name):
            # Drop initial-style tokens (J, JM, J-M): initials are all
            # uppercase while surnames keep mixed case (Wu, Dar, Diaz).
            tokens = [t for t in name.split() if not t.replace("-", "").isupper()]
            return [strip_accents(t).lower().rstrip(".") for t in tokens]

        for a, b in zip(merged["player_tt"], merged["player_wiki"]):
            ta, tb = set(surname_tokens(a)), set(surname_tokens(b))
            assert ta & tb, (a, b)


class TestDrawValidation:
    @requires_tt_fixture
    def test_valid_draw_passes(self):
        df = TennisTempleDrawParser().parse_file(str(TT_FIXTURE)).get_results()
        validate_draw(df)

    @requires_tt_fixture
    def test_wrong_player_count_fails(self):
        df = TennisTempleDrawParser().parse_file(str(TT_FIXTURE)).get_results()
        with pytest.raises(ValueError, match="128 players"):
            validate_draw(df.iloc[:-1])

    @requires_tt_fixture
    def test_missing_seed_fails(self):
        df = TennisTempleDrawParser().parse_file(str(TT_FIXTURE)).get_results()
        df.loc[df["seed"] == 32, "seed"] = 0
        with pytest.raises(ValueError, match="Seed set invalid"):
            validate_draw(df)


class TestFuzzyMatching:
    def test_compound_surname_shortened(self):
        names = ["Daniel Merida Aguilar", "Facundo Diaz Acosta", "Jaume Munar"]
        assert _fuzzy_match("D Merida", names) == "Daniel Merida Aguilar"

    def test_hyphenated_surname(self):
        names = ["Felix Auger Aliassime", "Benjamin Bonzi"]
        assert _fuzzy_match("F Auger-Aliassime", names) == "Felix Auger Aliassime"

    def test_siblings_disambiguated_by_initial(self):
        names = ["Francisco Cerundolo", "Juan Manuel Cerundolo"]
        assert _fuzzy_match("JM Cerundolo", names) == "Juan Manuel Cerundolo"
        assert _fuzzy_match("F Cerundolo", names) == "Francisco Cerundolo"

    def test_double_initials_rating_side(self):
        names = ["J J Wolf", "Jeffrey John Wolf"]
        assert _fuzzy_match("J Wolf", names) == "J J Wolf"

    def test_no_match_returns_none(self):
        assert _fuzzy_match("X Nobody", ["Alexander Zverev"]) is None


class TestExpectedScore:
    def test_certain_champion_scores_11x_plus_50(self):
        probs = pd.Series([1.0] * 7, index=ROUNDS)
        # 11 * (10 - black) + 50
        assert TennisPoolEmulator.probabilities_to_score(probs, black=2, loser=False) == pytest.approx(11 * 8 + 50)
        assert TennisPoolEmulator.probabilities_to_score(probs, black=0, loser=False) == pytest.approx(160)
        assert TennisPoolEmulator.probabilities_to_score(probs, black=5, loser=False) == pytest.approx(105)

    def test_doubled_points_start_round_four(self):
        # Only the 4th win (reaching QF) with certainty: 3 * (10-b) + 2 * (10-b)
        probs = pd.Series([1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0], index=ROUNDS)
        assert TennisPoolEmulator.probabilities_to_score(probs, black=0, loser=False) == pytest.approx(50)

    def test_loser_penalty_negative_and_capped(self):
        probs = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0], index=ROUNDS)
        score = TennisPoolEmulator.probabilities_to_score(probs, black=0, loser=True)
        assert score == pytest.approx(-50)

        probs = pd.Series([0.5, 0.4, 0.3, 0.2, 0.1, 0.0, 0.0], index=ROUNDS)
        score = TennisPoolEmulator.probabilities_to_score(probs, black=0, loser=True)
        assert score == pytest.approx(-10 * (0.5 + 0.4 + 0.3 + 0.2 + 0.1))

        # 6th and 7th wins add nothing beyond the 50 cap
        probs = pd.Series([1.0] * 7, index=ROUNDS)
        assert TennisPoolEmulator.probabilities_to_score(probs, black=0, loser=True) == pytest.approx(-50)

    def test_rounds_to_score_loser_capped(self):
        assert TennisPoolEmulator.rounds_to_score(rounds=3, black=0, loser=True) == -30
        assert TennisPoolEmulator.rounds_to_score(rounds=7, black=0, loser=True) == -50


def _team_schedule():
    """Synthetic 5-player schedule with clear role economics."""
    return pd.DataFrame(
        {
            "player": ["Strong A", "Strong B", "Cheap C", "Weak D", "Weak E"],
            "seed": [1, 3, 0, 32, 0],
            "black": [5, 4, 0, 1, 0],
            "potency": [100.0, 90.0, 20.0, 10.0, 5.0],
            "r64": [0.95, 0.9, 0.85, 0.05, 0.04],
            "r32": [0.9, 0.8, 0.7, 0.02, 0.02],
            "r16": [0.9, 0.1, 0.8, 0.01, 0.01],
            "qf": [0.5, 0.4, 0.3, 0.0, 0.0],
            "sm": [0.3, 0.2, 0.1, 0.0, 0.0],
            "f": [0.2, 0.1, 0.05, 0.0, 0.0],
            "w": [0.1, 0.05, 0.02, 0.0, 0.0],
        }
    )


class TestOptimiseTeam:
    def test_roles_assigned_and_distinct(self):
        result = optimise_team(_team_schedule(), selection_limit=3, black_points_limit=6, rounds=ROUNDS)

        assert len(result["schedule"]) == 3
        roles = set(result["schedule"]["role"])
        assert roles == {"player", "joker", "kluns"}
        assert result["joker"] != result["kluns"]

    def test_joker_goes_to_best_bonus(self):
        result = optimise_team(_team_schedule(), selection_limit=3, black_points_limit=6, rounds=ROUNDS)
        # Cheap C has by far the best joker bonus (50 - 0) * 0.8
        assert result["joker"] == "Cheap C"

    def test_kluns_budget_recycling(self):
        # Strong A (5) + Strong B (4) = 9 > 8: only feasible if the kluns
        # recycles his black points into the budget.
        schedule = _team_schedule()
        result = optimise_team(schedule, selection_limit=3, black_points_limit=8, rounds=ROUNDS)

        selected = result["schedule"]
        non_kluns_black = selected.loc[selected["role"] != "kluns", "black"].sum()
        kluns_black = selected.loc[selected["role"] == "kluns", "black"].iloc[0]
        assert non_kluns_black == 9
        assert non_kluns_black <= 8 + kluns_black

    def test_expected_points_accounting(self):
        result = optimise_team(_team_schedule(), selection_limit=3, black_points_limit=6, rounds=ROUNDS)

        schedule = result["schedule"]
        manual = 0.0
        for _, row in schedule.iterrows():
            if row["role"] == "kluns":
                manual += row["kluns_penalty"]
            else:
                manual += row["potency"]
                if row["role"] == "joker":
                    manual += row["joker_bonus"]

        assert result["expected_points"] == pytest.approx(manual)


class TestWebCache:
    def test_fetch_stores_and_reuses(self, tmp_path, monkeypatch):
        from sportpools import webcache

        calls = []

        class FakeResponse:
            text = "<html>draw</html>"

            def raise_for_status(self):
                pass

        def fake_get(url, headers=None, timeout=None):
            calls.append(url)
            return FakeResponse()

        monkeypatch.setattr(webcache.requests, "get", fake_get)

        first = webcache.fetch_cached("https://example.com/draw", ttl_hours=1, cache_dir=tmp_path)
        second = webcache.fetch_cached("https://example.com/draw", ttl_hours=1, cache_dir=tmp_path)

        assert first == "<html>draw</html>"
        assert second == first
        assert calls == ["https://example.com/draw"]  # second call came from cache

    def test_expired_ttl_refetches(self, tmp_path, monkeypatch):
        import os
        import time
        from sportpools import webcache

        calls = []

        class FakeResponse:
            text = "<html>new</html>"

            def raise_for_status(self):
                pass

        monkeypatch.setattr(webcache.requests, "get", lambda *a, **k: calls.append(1) or FakeResponse())

        webcache.fetch_cached("https://example.com/x", ttl_hours=0, cache_dir=tmp_path)
        webcache.fetch_cached("https://example.com/x", ttl_hours=1, cache_dir=tmp_path)
        assert len(calls) == 1
        # Age every cache file beyond the TTL
        old = time.time() - 7200
        for f in tmp_path.iterdir():
            os.utime(f, (old, old))
        webcache.fetch_cached("https://example.com/x", ttl_hours=1, cache_dir=tmp_path)
        assert len(calls) == 2

    def test_stale_cache_served_on_failure(self, tmp_path, monkeypatch):
        import requests as real_requests
        from sportpools import webcache

        class FakeResponse:
            text = "<html>draw</html>"

            def raise_for_status(self):
                pass

        monkeypatch.setattr(
            webcache.requests, "get", lambda *a, **k: FakeResponse()
        )
        webcache.fetch_cached("https://example.com/y", ttl_hours=1, cache_dir=tmp_path)

        def failing_get(*args, **kwargs):
            raise real_requests.RequestException("network down")

        monkeypatch.setattr(webcache.requests, "get", failing_get)

        result = webcache.fetch_cached("https://example.com/y", ttl_hours=0, cache_dir=tmp_path)
        assert result == "<html>draw</html>"


class TestForcedKluns:
    def test_forced_kluns_is_respected(self):
        result = optimise_team(
            _team_schedule(), selection_limit=3, black_points_limit=6,
            rounds=ROUNDS, forced_kluns="Weak E",
        )
        assert result["kluns"] == "Weak E"

    def test_forced_kluns_changes_ev(self):
        free = optimise_team(_team_schedule(), selection_limit=3, black_points_limit=6, rounds=ROUNDS)
        forced = optimise_team(
            _team_schedule(), selection_limit=3, black_points_limit=6,
            rounds=ROUNDS, forced_kluns="Strong A",
        )
        # Burning your best player as kluns must hurt
        assert forced["expected_points"] < free["expected_points"]

    def test_unknown_forced_kluns_raises(self):
        with pytest.raises(ValueError, match="Unknown forced kluns"):
            optimise_team(
                _team_schedule(), selection_limit=3, black_points_limit=6,
                rounds=ROUNDS, forced_kluns="Nobody",
            )
