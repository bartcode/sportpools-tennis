import pandas as pd
from pandas.testing import assert_frame_equal

from sportpools.model.tennis import TennisPool
from sportpools.model.emulator import TennisPoolEmulator


ROUNDS = ["r64", "r32", "r16", "qf", "sm", "f", "w"]

def test_determine_black_points():
    seeds = pd.DataFrame({
        'seed': [1, 4, 6, 32, 64, None],
    })

    seeds_result = seeds.copy()
    seeds_result['black'] = [5, 4, 3, 1, 0, 0]

    assert_frame_equal(TennisPool.determine_black_points(seeds), seeds_result)


def test_clean_player_name():
    players = pd.DataFrame({
        'player': ['(1)Roger Federer(SUI)', '(2)Rafael Nadal(ESP)', '(3)Novak Djokovic(SRB)'],
    })

    players_result = pd.DataFrame({
        'player': ['Roger Federer', 'Rafael Nadal', 'Novak Djokovic'],
    })

    assert_frame_equal(TennisPool.clean_player_name(players), players_result)


def test_convert_columns():
    percentages = pd.DataFrame({
        'perc': ['5%', '2.5%', '100.0%']
    })

    percentages_result = pd.DataFrame({
        'perc': [.05, .025, 1.]
    })

    assert_frame_equal(TennisPool.convert_columns(percentages, ['perc']), percentages_result)


# def test_determine_score_potency():
#     players = pd.DataFrame({
#         'rounds': [7, 6, 5, 4, 3, 2, 1],
#         'black': [0, 1, 1, 3, 5, 2, 0]})
#
#     players_result = players.copy()
#     players_result['potency'] = [160, 81, 63, 35, 15, 16, 10]
#
#     assert_frame_equal(TennisPoolEmulator.determine_score_potency(players, ROUNDS), players_result)


def test_extract_seed():
    players = pd.DataFrame({
        'player': ['(1)Roger Federer(SUI)', '(2)Rafael Nadal(ESP)', '(3)Novak Djokovic(SRB)'],
    })

    players_result = players.copy()
    players_result['seed'] = [1, 2, 3]

    assert_frame_equal(TennisPool.extract_seed(players), players_result)


def test_clean_invalid_rows():
    players = pd.DataFrame({
        'player': ['(1)Roger Federer(SUI)', '(2)Rafael Nadal(ESP)', '(3)Novak Djokovic(SRB)', 'Player', None],
    })

    players_result = pd.DataFrame({
        'player': ['(1)Roger Federer(SUI)', '(2)Rafael Nadal(ESP)', '(3)Novak Djokovic(SRB)'],
    })

    assert_frame_equal(TennisPool.clean_invalid_rows(players), players_result)
