# Sportpools selection optimiser
This package runs a simple script to optimise your Sportpools selection. It uses the Singles forecast as
described on [TennisAbstract](https://tennisabstract.com/).

## Game rules
- A selection of players consists of 14 regular players.
- One should choose 1 "loser" (this is still a manual step, see [Limitations](#Limitations)).
- Each round a loser makes it through, subtracts 10 points from the score total.
- Each player has an amount of "black points", ranging from 0 up to 5, depending on his seed.
- Each selected player reaching a next round receives `10 - bp` points.
- Each selected player reaching a next round _as of the fourth round_ receives `2  * (10 - bp)` points per win.
- A joker is someone who gets extra points for reaching the fourth round: `score = 50 - 5 * bp`.

## Installation
```bash
$ pip install git+https://github.com/bartcode/sportpools-tennis.git
```

## Usage
1. Install this package.
2. Go to [TennisAbstract](https://tennisabstract.com/) and select the forecast of the upcoming Grand Slam.
3. Save the page as HTML-only and save it to your disk.
4. Run `sportpools -f ./page.htm`.
```text
usage: sportpools [-h] -f FILE [-b BLACK_POINTS] [-c COUNT] [-l LOSER]

Optimise your Sportpools player selection

optional arguments:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  Path to file to import
  -b BLACK_POINTS, --black BLACK_POINTS, --black-points BLACK_POINTS
                        Total number of black points to use
  -c COUNT, --count COUNT, --player-count COUNT
                        Number of players to select
  -l LOSER, --loser LOSER
                        Selected loser
```

## Notes
- The number of available black points is 20 by default, but can be adjusted using the `-b` argument.
  Do note it is automatically adjusted when you define your loser.

## Limitations
- A loser should still be chosen by the player and can be passed as an argument to the script with `-l`.
- The joker is eventually chosen manually, but a list of suggestions is created.
