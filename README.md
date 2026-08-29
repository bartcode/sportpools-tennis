# Sportpools selection optimiser

This package optimises your Sportpools selection for a Grand Slam. It supports a **web UI**
and a **CLI**, both running on the same prediction pipeline:

- Elo ratings from [Tennis Abstract](https://tennisabstract.com/), an exact
  dynamic-programming bracket simulation, and an integer program that optimises the full
  team (13 players + joker + kluns) under the real Sportpools rules.

## Web UI

```bash
uv run sportpools-ui
```

Then open <http://127.0.0.1:8000>. One command runs the FastAPI backend and serves the
built React frontend. The UI offers:

- a prediction runner with live stage-by-stage progress;
- the optimal team with per-player round probabilities (R4/QF/SF/F/title);
- **joker and kluns alternatives** with the underlying statistics (bonus formula,
  exit-round chances, and the total team value when forcing each kluns);
- **the most probable route to the final** for every player (most likely opponent per
  round with win chances) via the player drawer;
- **intra-team matchups**: when your own selections can meet, and how likely;
- interactive editing: swap players, change roles, live rule validation and expected
  points, plus re-optimisation around your locked players;
- side-by-side comparison of hard-court vs overall Elo models;
- saved teams (SQLite) and one-click export of your selection.

Frontend development (requires Node): `cd web && npm install && npm run dev` (proxies
`/api` to `localhost:8000`), build with `npm run build`.

The CLI shares the pipeline with the web UI.

## Game rules

- A team consists of 15 players: 13 regular players, one joker and one kluns.
- Each player has an amount of "black points" (0-5), derived from his seed:
  seeds 1-2 → 5, 3-4 → 4, 5-8 → 3, 9-16 → 2, 17-32 → 1, unseeded → 0.
- The non-kluns players may use at most 20 black points combined; the kluns's black
  points don't count and are added to the budget instead (the "kluns trick").
- Each win earns `10 - bp` points, doubled from the fourth round onward.
- The tournament winner earns 50 bonus points.
- The joker earns a one-time bonus of `50 - 5 * bp` for reaching round 4.
- The kluns earns nothing but subtracts 10 points per round he advances
  (capped at 50 if he wins the tournament).

## Installation

```bash
pip install git+https://github.com/bartcode/sportpools-tennis.git
```

### Simulation mode (default)

Fetch the draw from Wikipedia and the Elo ratings from Tennis Abstract, simulate and optimise:

```bash
sportpools --tournament us-open --year 2026 --surface hard
```

Recommend `--surface hard` for the US Open: hard-court Elo is the better predictor
for a hard-court slam. Use `--surface all` for overall Elo as a sensitivity check.

Fetched pages are cached in `.cache/` for 6 hours (adjust with `--cache-ttl`, set
`0` to always refetch); if a fetch fails, a stale cached copy is used when available.

The report contains:

- the optimal 15 with each player's expected points and round-by-round chances
  (P(reach R4), P(QF), P(SF), P(F), P(title)) to tune the risk profile;
- a joker analysis: the bonus formula and the best joker candidates in the team;
- a kluns analysis: exit-round chances, expected penalty, recycled black points,
  and the best kluns alternatives with the total team value for each (the whole
  team is re-optimised for every candidate kluns);
- reserve suggestions.

Alternative inputs:

- `--draw-url <url>` fetches the draw from any URL (Wikipedia article or TennisTemple
  draw page; the format is auto-detected).
- `--draw-url <file>` reads a draw saved to disk. TennisTemple is behind Cloudflare, so
  for a TennisTemple draw save the page from your browser (HTML only) and point
  `--draw-url` at the file.
- `--ratings-data <file>` reads Elo ratings from a saved copy of
  [the Elo report page](https://tennisabstract.com/reports/atp_elo_ratings.html) instead of
  fetching it live.
- `--rating-method dr` computes Dominance Ratio ratings from Tennis Abstract JS match logs
  (pass the log files via `--ratings-data`) instead of using Elo.

The output lists the optimal team with each player's expected points, the joker and kluns
choices, the black points budget usage, and reserve suggestions.

### Forecast mode (legacy)

1. Go to [TennisAbstract](https://tennisabstract.com/) and select the forecast of the upcoming Grand Slam.
2. Save the page as HTML-only and save it to your disk.
3. Run `sportpools -f ./page.htm`.

In this mode you choose the kluns yourself with `-l`; the joker is suggested afterwards.

## Notes

- The number of available black points is 20 by default, adjustable with `-b`.
- The simulator converts Elo-based best-of-3 win probabilities to best-of-5 for Grand Slams.
- Players missing from the Elo table (e.g. wild cards) get a conservative ATP-rank-based
  estimate; the run logs the rating coverage and any unmatched players.
