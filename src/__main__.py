"""
Sportpools optimiser
"""
import logging.config
import os
import sys

from src.sportpools.tennis import TennisPool, TennisPoolEmulator, TennisSelectionOptimizer

logging.config.fileConfig(os.path.join(sys.prefix, 'sportpools', 'logger.ini'), disable_existing_loggers=False)
LOGGER = logging.getLogger(__name__)


def main() -> None:
    """
    Parse arguments and perform main functionality.
    :return: None
    """
    pool = TennisPool() \
        .load_data('./data/Tennis Abstract_ 2020 Australian Open Men\'s Draw Forecast Forecast.htm') \
        .apply_filters() \
        .add_features()

    emulator = TennisPoolEmulator(pool.get_results())

    pool_results = emulator.play_draw() \
        .add_features() \
        .get_results()

    optimizer = TennisSelectionOptimizer(pool_results)


if __name__ == '__main__':
    main()
