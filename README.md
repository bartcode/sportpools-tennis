# Sportpools selection optimiser
This package runs a simple script to optimise your Sportpools selection. It uses the Singles forecast as
described on [TennisAbstract](https://tennisabstract.com/).

## Game rules
- A selection of players consists of 14 regular players.
- One should choose 1 "loser" (this is still a manual step, see [Limitations](#Limitations)).
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
2. Go to [TennisAbstract](https://tennisabstract.com/) and select the forecast of the upcoming grand slam.
3. Save the page as HTML-only and save it to your disk.
4. Run `sportpools -f ./page.htm`.
```text
usage: sportpools [-h] -f FILE [-b BLACK_POINTS] [-c COUNT]

Optimise your Sportpools player selection

optional arguments:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  Path to file to import
  -b BLACK_POINTS, --black-points BLACK_POINTS
                        Path to file to import
  -c COUNT, --count COUNT, --player-count COUNT
                        Number of players to select
```

## Limitations
- A loser should still be chosen by the player.
- The number of available black points is 20 by default, but can be adjusted using the `-b` argument.
