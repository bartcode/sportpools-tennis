"""
Fetch and compute player ratings from Tennis Abstract match data.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from sportpools.webcache import fetch_cached, DEFAULT_TTL_HOURS

LOGGER = logging.getLogger(__name__)

MATCH_FIELDS = [
    "date", "tourn", "surf", "level", "wl", "player",
    "rank", "seed", "entry", "round",
    "score", "max", "opp", "orank", "oseed", "oentry", "ohand", "obh",
    "obday", "oht", "ocountry", "oactive",
    "tbw", "tbl", "setw", "setl",
    "time", "aces", "dfs", "pts", "firsts", "fwon",
    "swon", "games", "saved", "chances", "oaces", "odfs", "opts", "ofirsts",
    "ofwon", "oswon", "ogames", "osaved", "ochances",
]

SURFACE_MAP = {
    "clay": "Clay",
    "grass": "Grass",
    "hard": "Hard",
    "all": None,
}

ELO_SURFACE_COLUMNS = {
    "clay": "cElo",
    "hard": "hElo",
    "grass": "gElo",
    "all": "Elo",
}

TA_BASE_URL = "https://www.tennisabstract.com/jsmatches"
TA_LEADER_URLS = [
    f"{TA_BASE_URL}/leadersource.js",
    f"{TA_BASE_URL}/leadersource51.js",
]

TA_ELO_URL = "https://tennisabstract.com/reports/atp_elo_ratings.html"


class EloRatingsFetcher:
    """Fetch and parse Tennis Abstract Elo ratings."""

    def __init__(self, surface: str = "all"):
        self._surface = surface.lower()
        self._elo_col = ELO_SURFACE_COLUMNS.get(self._surface, "Elo")

    def fetch_from_web(
        self, url: Optional[str] = None, ttl_hours: float = DEFAULT_TTL_HOURS
    ) -> pd.DataFrame:
        LOGGER.info("Fetching Elo ratings from %s", url or TA_ELO_URL)
        try:
            html = fetch_cached(url or TA_ELO_URL, ttl_hours=ttl_hours)
            return self._parse_html(html)
        except requests.RequestException as e:
            LOGGER.warning("Failed to fetch Elo ratings: %s", e)
            return pd.DataFrame(columns=["player", "elo", "rank"])

    def load_from_file(self, file_path: str) -> pd.DataFrame:
        LOGGER.info("Loading Elo ratings from %s", file_path)
        content = Path(file_path).read_text(encoding="utf-8")
        return self.load_from_html(content)

    def load_from_html(self, html: str) -> pd.DataFrame:
        """
        Parse Elo ratings from HTML content.
        :param html: HTML of the Tennis Abstract Elo report page.
        :return: Ratings DataFrame.
        """
        return self._parse_html(html)

    def _parse_html(self, html: str) -> pd.DataFrame:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", id="reportable")
        if not table:
            LOGGER.warning("No Elo ratings table found in HTML")
            return pd.DataFrame(columns=["player", "elo", "rank"])

        rows = []
        for tr in table.find("tbody").find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 11:
                continue

            name_cell = cells[1]
            link = name_cell.find("a")
            if link:
                name = link.get_text().replace("\xa0", " ").strip()
            else:
                name = name_cell.get_text().replace("\xa0", " ").strip()

            try:
                elo = float(cells[3].get_text().strip())
            except (ValueError, IndexError):
                continue

            try:
                h_elo = float(cells[6].get_text().strip())
            except (ValueError, IndexError):
                h_elo = None

            try:
                c_elo = float(cells[8].get_text().strip())
            except (ValueError, IndexError):
                c_elo = None

            try:
                g_elo = float(cells[10].get_text().strip())
            except (ValueError, IndexError):
                g_elo = None

            atp_rank = None
            if len(cells) >= 16:
                try:
                    atp_rank = int(cells[15].get_text().strip())
                except (ValueError, IndexError):
                    pass

            elo_value = {"Elo": elo, "hElo": h_elo, "cElo": c_elo, "gElo": g_elo}

            row = {
                "player": name,
                "Elo": elo,
                "hElo": h_elo,
                "cElo": c_elo,
                "gElo": g_elo,
                "elo": elo_value.get(self._elo_col) or elo,
                "rank": atp_rank or 999,
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        LOGGER.info("Parsed Elo ratings for %d players (using %s)", len(df), self._elo_col)
        return df


class RatingsCalculator:
    """Compute player ratings from Tennis Abstract match data."""

    def __init__(self, surface: str = "all", span: str = "last52"):
        """
        :param surface: Surface filter (clay/grass/hard/all).
        :param span: Time span filter (last52/career).
        """
        self._surface = SURFACE_MAP.get(surface.lower(), None)
        self._span = span
        self._matches: List[dict] = []
        self._rankings: Dict[str, int] = {}

    def fetch_from_web(
        self, urls: Optional[List[str]] = None, ttl_hours: float = DEFAULT_TTL_HOURS
    ) -> RatingsCalculator:
        """
        Fetch match data from Tennis Abstract JS files.
        :param urls: List of JS file URLs to fetch. Defaults to standard leader source files.
        :param ttl_hours: Hours fetched files stay cached.
        :return: Self.
        """
        if urls is None:
            urls = TA_LEADER_URLS

        for url in urls:
            LOGGER.info("Fetching match data from %s", url)
            try:
                content = fetch_cached(url, ttl_hours=ttl_hours)
                matches, rankings = self._parse_js(content)
                self._matches.extend(matches)
                self._rankings.update(rankings)
                LOGGER.info("Parsed %d matches from %s", len(matches), url)
            except requests.RequestException as e:
                LOGGER.warning("Failed to fetch %s: %s", url, e)

        return self

    def load_from_files(self, file_paths: List[str]) -> RatingsCalculator:
        """
        Load match data from saved JS files.
        :param file_paths: Paths to JS files.
        :return: Self.
        """
        for file_path in file_paths:
            LOGGER.info("Loading match data from %s", file_path)
            content = Path(file_path).read_text(encoding="utf-8")
            matches, rankings = self._parse_js(content)
            self._matches.extend(matches)
            self._rankings.update(rankings)
            LOGGER.info("Parsed %d matches from %s", len(matches), file_path)

        return self

    def _parse_js(self, js_content: str) -> tuple:
        """
        Parse JavaScript source file to extract match data and rankings.
        :param js_content: JavaScript source content.
        :return: Tuple of (matches list, rankings dict).
        """
        rankings = self._parse_rankings(js_content)
        matches = []

        match_array_pattern = r'var\s+matchmx\s*=\s*\['
        array_start = re.search(match_array_pattern, js_content)

        if not array_start:
            LOGGER.warning("No matchmx array found in JS content")
            return matches, rankings

        pos = array_start.end()
        depth = 1
        array_start_pos = pos - 1

        while pos < len(js_content) and depth > 0:
            if js_content[pos] == '[':
                depth += 1
            elif js_content[pos] == ']':
                depth -= 1
            pos += 1

        array_text = js_content[array_start_pos:pos]

        inner_arrays = re.findall(r'\[([^\]]*(?:\[[^\]]*\][^\]]*)*)\]', array_text)

        for arr_text in inner_arrays:
            try:
                elements = json.loads(f"[{arr_text}]")
                if isinstance(elements, list) and len(elements) >= 44:
                    match_dict = {}
                    for i, field in enumerate(MATCH_FIELDS):
                        if i < len(elements):
                            match_dict[field] = elements[i]
                    matches.append(match_dict)
            except (json.JSONDecodeError, ValueError):
                continue

        return matches, rankings

    @staticmethod
    def _parse_rankings(js_content: str) -> Dict[str, int]:
        """
        Parse ATP rankings from JS content.
        :param js_content: JavaScript source content.
        :return: Dict mapping player name to ATP rank.
        """
        rankings = {}
        pattern = r"crank\s*=\s*\{([^}]+)\}"
        match = re.search(pattern, js_content)

        if not match:
            return rankings

        entries = match.group(1)
        for entry in entries.split(","):
            entry = entry.strip()
            if ":" not in entry:
                continue
            parts = entry.split(":")
            if len(parts) != 2:
                continue
            name = parts[0].strip().strip("'\"")
            rank_str = parts[1].strip().strip("'\"")
            try:
                rankings[name] = int(rank_str)
            except ValueError:
                continue

        return rankings

    def compute_ratings(self) -> pd.DataFrame:
        """
        Compute DR ratings from the loaded match data.
        :return: DataFrame with player, dr, spw, rpw, matches, rank.
        """
        LOGGER.info("Computing ratings from %d matches", len(self._matches))

        df = pd.DataFrame(self._matches)

        if df.empty:
            return pd.DataFrame(columns=["player", "dr", "spw", "rpw", "matches", "rank"])

        df = self._apply_filters(df)

        if df.empty:
            LOGGER.warning("No matches remaining after filtering")
            return pd.DataFrame(columns=["player", "dr", "spw", "rpw", "matches", "rank"])

        numeric_cols = {
            col: pd.to_numeric(df[col], errors="coerce")
            for col in ["pts", "fwon", "swon", "opts", "ofwon", "oswon"]
        }
        df = df.assign(**numeric_cols)

        df = df.dropna(subset=["pts", "opts"])

        df = df[(df["pts"] > 0) & (df["opts"] > 0)]

        df = df.assign(
            serve_won=df["fwon"] + df["swon"],
            return_won=df["opts"] - df["ofwon"] - df["oswon"],
        )

        orank_numeric = pd.to_numeric(df["orank"], errors="coerce")
        opp_weight = (1.0 / (1.0 + orank_numeric / 100.0)).fillna(0.5)
        df = df.assign(opp_weight=opp_weight)

        df = df.assign(
            w_pts=df["pts"] * df["opp_weight"],
            w_serve_won=df["serve_won"] * df["opp_weight"],
            w_opts=df["opts"] * df["opp_weight"],
            w_return_won=df["return_won"] * df["opp_weight"],
        )

        agg = df.groupby("player").agg(
            total_pts=("w_pts", "sum"),
            serve_won=("w_serve_won", "sum"),
            total_opts=("w_opts", "sum"),
            return_won=("w_return_won", "sum"),
            matches=("player", "count"),
        ).reset_index()

        agg = agg.assign(
            spw=agg["serve_won"] / agg["total_pts"],
            rpw=agg["return_won"] / agg["total_opts"],
        )
        agg = agg.assign(dr=agg["rpw"] / (1 - agg["spw"]))
        agg = agg.assign(rank=agg["player"].map(self._rankings))

        agg = agg.sort_values("dr", ascending=False).reset_index(drop=True)

        LOGGER.info("Computed ratings for %d players", len(agg))

        return agg[["player", "dr", "spw", "rpw", "matches", "rank"]]

    def _apply_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply surface and time span filters to match data.
        :param df: Match data DataFrame.
        :return: Filtered DataFrame.
        """
        if self._surface is not None:
            df = df[df["surf"] == self._surface]
            LOGGER.info("Filtered to %s surface: %d matches", self._surface, len(df))

        if self._span == "last52":
            today = datetime.now()
            cutoff = today - timedelta(weeks=52)
            cutoff_str = cutoff.strftime("%Y%m%d")
            df = df[df["date"] >= cutoff_str]
            LOGGER.info("Filtered to last 52 weeks: %d matches", len(df))

        return df

    def get_rankings(self) -> Dict[str, int]:
        """
        Return the parsed ATP rankings.
        :return: Dict mapping player name to rank.
        """
        return self._rankings
