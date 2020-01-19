"""
Sportpools optimiser
"""
import argparse
import logging.config
import os
import sys

from src.sportpools.tennis import TennisPool, TennisPoolEmulator, optimise_selection

logging.config.fileConfig(os.path.join(sys.prefix, 'sportpools', 'logger.ini'), disable_existing_loggers=False)
LOGGER = logging.getLogger(__name__)


def main() -> None:
    """
    Parse arguments and perform main functionality.
    :return: None
    """
    parser = argparse.ArgumentParser(description='Optimise your Sportpools player selection')
    parser.add_argument(
        '-f', '--file',
        help='Path to file to import',
        type=str,
        default='./data/Tennis Abstract_ 2020 Australian Open Men\'s Draw Forecast Forecast.htm',
        required=True,
    )
    parser.add_argument(
        '-b', '--black-points',
        help='Path to file to import',
        type=int,
        default=20
    )
    parser.add_argument(
        '-c', '--count', '--player-count',
        help='Number of players to select',
        type=int,
        default=14
    )
    parser.add_argument(
        '-l', '--loser',
        help='Selected loser',
        default='Rafael Nadal',
        type=str,
    )

    args, _ = parser.parse_known_args()

    pool = TennisPool() \
        .load_data(args.file) \
        .apply_filters() \
        .add_features()

    emulator = TennisPoolEmulator(pool.get_results())

    pool_results = emulator.play_draw() \
        .add_features() \
        .get_results()

    selection_optimum = optimise_selection(
        pool_results,
        selection_limit=args.count,
        black_points_limit=args.black_points,
        loser=args.loser,
    )

    LOGGER.info('Optimal set of players is as follows:')
    LOGGER.info('\r\n%s', selection_optimum['schedule'].head(25))

    LOGGER.info('The selection of these players results in %d points with %d black points',
                selection_optimum['schedule']['potency'].sum(),
                selection_optimum['schedule']['black'].sum())
    LOGGER.info('Select your joker in this order:')
    LOGGER.info('\r\n%s',
                str(selection_optimum['schedule'][selection_optimum['schedule']['rounds'] >= 4]
                    .sort_values(by=['black'], ascending=True)
                    .head(5)))


if __name__ == '__main__':
    main()
