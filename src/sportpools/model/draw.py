"""
Parse tennis tournament draws from Wikipedia or TennisTemple.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

LOGGER = logging.getLogger(__name__)

ENTRY_CODES = {"Q", "WC", "LL", "PR", "Alt", "SE", "ITF", "SR", "JE", "JR", "CO", "NG"}

SECTION_IDS = [f"Section_{i}" for i in range(1, 9)]

PLAYERS_PER_SECTION = 16
SECTION_COUNT = 8
DRAW_SIZE = PLAYERS_PER_SECTION * SECTION_COUNT


class DrawParser:
    """Parse a Grand Slam draw from Wikipedia HTML."""

    def __init__(self):
        self._sections: List[List[dict]] = []

    def parse_file(self, file_path: str) -> DrawParser:
        """
        Parse draw from a saved HTML file.
        :param file_path: Path to the HTML file.
        :return: Self.
        """
        LOGGER.info("Parsing draw from file %s", file_path)
        html = Path(file_path).read_text(encoding="utf-8")
        return self._parse_html(html)

    def fetch_and_parse(self, url: str) -> DrawParser:
        """
        Fetch draw from a URL and parse it.
        :param url: URL to the Wikipedia draw page.
        :return: Self.
        """
        LOGGER.info("Fetching draw from %s", url)
        response = requests.get(url, headers={"User-Agent": "SportpoolsTennis/1.0"}, timeout=30)
        response.raise_for_status()
        return self._parse_html(response.text)

    def _parse_html(self, html: str) -> DrawParser:
        """
        Parse draw from HTML content.
        :param html: HTML content.
        :return: Self.
        """
        soup = BeautifulSoup(html, "html.parser")

        for section_idx, section_id in enumerate(SECTION_IDS, start=1):
            heading = soup.find("h4", id=section_id) or soup.find("h3", id=section_id)
            if not heading:
                LOGGER.warning("Section %s not found in HTML", section_id)
                continue

            players = self._parse_section(heading, section_idx)
            self._sections.append(players)

        total = sum(len(s) for s in self._sections)
        LOGGER.info("Parsed %d sections with %d total players", len(self._sections), total)

        return self

    def _parse_section(self, heading: Tag, section_idx: int) -> List[dict]:
        """
        Parse a single bracket section.
        :param heading: The heading element for this section.
        :param section_idx: Section number (1-8).
        :return: List of player dicts.
        """
        table = self._find_bracket_table(heading)
        if not table:
            LOGGER.warning("No bracket table found for section %d", section_idx)
            return []

        players = []
        rows = table.find_all("tr")

        for row in rows:
            player_info = self._parse_player_row(row, section_idx)
            if player_info:
                position = len(players)
                player_info["position"] = position
                players.append(player_info)

        return players

    def _find_bracket_table(self, heading: Tag) -> Optional[Tag]:
        """
        Find the bracket table following a section heading.
        :param heading: The heading element.
        :return: The bracket table element, or None.
        """
        element = heading.parent if heading.parent else heading
        for _ in range(30):
            element = element.next_sibling
            if element is None:
                break
            if isinstance(element, Tag) and element.name == "table":
                return element
            if isinstance(element, Tag):
                inner_table = element.find("table")
                if inner_table:
                    return inner_table
        return None

    def _parse_player_row(self, row: Tag, section_idx: int) -> Optional[dict]:
        """
        Parse a player row from the bracket table.
        Only extracts data from the first round column.
        :param row: Table row element.
        :param section_idx: Section number.
        :return: Player dict or None if not a player row.
        """
        cells = row.find_all("td")
        if len(cells) < 3:
            return None

        seed_idx, name_idx = self._find_seed_name_cells(cells)
        if seed_idx is None:
            return None

        seed_cell = cells[seed_idx]
        name_cell = cells[name_idx]

        seed_text = seed_cell.get_text(strip=True)
        name_link = name_cell.find("a")

        player_name = ""
        if name_link:
            links = name_cell.find_all("a")
            for link in links:
                text = link.get_text(strip=True)
                if text and "/wiki/" in link.get("href", "") and "Flag" not in str(link.get("class", [])):
                    if not any(c in text for c in ["—", "–"]):
                        player_name = text
                        break

        if not player_name or len(player_name) < 2:
            return None

        seed, entry = self._parse_seed_cell(seed_text)

        return {
            "player": player_name,
            "seed": seed,
            "entry": entry,
            "section": section_idx,
        }

    @staticmethod
    def _find_seed_name_cells(cells: list) -> tuple:
        """
        Find the seed and name cell indices in a row.
        Looks for cells with grey background (seed and name cells).
        :param cells: List of td elements.
        :return: Tuple of (seed_index, name_index) or (None, None).
        """
        grey_cells = []
        for i, cell in enumerate(cells):
            style = str(cell.get("style", ""))
            if "background-color" in style and "neutral" in style:
                grey_cells.append(i)

        if len(grey_cells) < 2:
            return None, None

        return grey_cells[0], grey_cells[1]

    @staticmethod
    def _parse_seed_cell(text: str) -> Tuple[int, str]:
        """
        Parse the seed/entry cell text.
        :param text: Cell text content.
        :return: Tuple of (seed_number, entry_type).
        """
        text = text.strip()

        if not text:
            return 0, ""

        if text in ENTRY_CODES:
            return 0, text

        if text.isdigit():
            return int(text), ""

        match = re.match(r"(\d+)", text)
        if match:
            return int(match.group(1)), ""

        return 0, text

    def get_results(self) -> pd.DataFrame:
        """
        Return the parsed draw as a DataFrame.
        :return: DataFrame with player, seed, entry, section, position.
        """
        all_players = []
        for section in self._sections:
            all_players.extend(section)

        if not all_players:
            return pd.DataFrame(columns=["player", "seed", "entry", "section", "position"])

        df = pd.DataFrame(all_players)
        df = df[["player", "seed", "entry", "section", "position"]]

        return df


_TRAILING_INITIAL_RE = re.compile(r"^[A-Za-z](?:[-.][A-Za-z])?\.?$")


class TennisTempleDrawParser:
    """
    Parse a Grand Slam draw from a TennisTemple draw page.

    TennisTemple renders each first-round match as an ``a.tt-match`` element
    with ``data-round="1"``; the two players appear as
    ``div.competition-draw-player`` rows with a seed/entry cell
    (``div.competition-draw-seed``) and a name cell
    (``div.competition-draw-name``) in 'Last F.' format. Matches are ordered
    by their ``data-ordre`` attribute, which follows the bracket.

    The site sits behind Cloudflare, so live fetching usually fails; the
    intended input is an HTML file saved from a browser.
    """

    def __init__(self):
        self._players: List[dict] = []

    def parse_file(self, file_path: str) -> TennisTempleDrawParser:
        """
        Parse draw from a saved HTML file.
        :param file_path: Path to the HTML file.
        :return: Self.
        """
        LOGGER.info("Parsing TennisTemple draw from file %s", file_path)
        html = Path(file_path).read_text(encoding="utf-8")
        return self._parse_html(html)

    def fetch_and_parse(self, url: str) -> TennisTempleDrawParser:
        """
        Fetch draw from a URL and parse it.
        :param url: URL to the TennisTemple draw page.
        :return: Self.
        """
        LOGGER.info("Fetching TennisTemple draw from %s", url)
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            timeout=30,
        )
        response.raise_for_status()
        return self._parse_html(response.text)

    def _parse_html(self, html: str) -> TennisTempleDrawParser:
        """
        Parse draw from (rendered) HTML content.
        :param html: HTML content.
        :return: Self.
        """
        soup = BeautifulSoup(html, "html.parser")

        matches = [
            anchor
            for anchor in soup.find_all("a", class_="tt-match")
            if anchor.get("data-round") == "1"
        ]
        matches.sort(key=lambda a: int(a.get("data-ordre", 0) or 0))

        for match in matches:
            player_rows = match.find_all("div", class_="competition-draw-player")
            for row in player_rows:
                name_div = row.find("div", class_="competition-draw-name")
                if not name_div:
                    continue
                seed_div = row.find("div", class_="competition-draw-seed")
                seed_text = seed_div.get_text(strip=True) if seed_div else ""

                seed, entry = DrawParser._parse_seed_cell(seed_text)
                self._players.append(
                    {
                        "player": self._reorder_name(name_div.get_text(strip=True)),
                        "seed": seed,
                        "entry": entry if not seed else "",
                    }
                )

        LOGGER.info("Parsed TennisTemple draw with %d players", len(self._players))
        return self

    @staticmethod
    def _reorder_name(name: str) -> str:
        """
        Convert TennisTemple's 'Last F.' format to the 'F Last' format used
        by the Wikipedia parser and the ratings matcher.
        """
        tokens = name.replace("\xa0", " ").split()
        initials = []
        while len(tokens) > 1 and _TRAILING_INITIAL_RE.match(tokens[-1]):
            initials.append(tokens.pop().rstrip("."))
        if not initials:
            return name
        return f"{''.join(reversed(initials))} {' '.join(tokens)}"

    def get_results(self) -> pd.DataFrame:
        """
        Return the parsed draw as a DataFrame.
        :return: DataFrame with player, seed, entry, section, position.
        """
        if not self._players:
            return pd.DataFrame(columns=["player", "seed", "entry", "section", "position"])

        records = []
        for slot, info in enumerate(self._players):
            records.append(
                {
                    **info,
                    "section": slot // PLAYERS_PER_SECTION + 1,
                    "position": slot % PLAYERS_PER_SECTION,
                }
            )
        return pd.DataFrame(records)[["player", "seed", "entry", "section", "position"]]


def parse_draw(html: str):
    """
    Parse draw HTML, auto-detecting the source format.
    :param html: HTML content of a draw page.
    :return: A parser instance (DrawParser or TennisTempleDrawParser).
    """
    if "competition-draw-match" in html or "tennistemple" in html.lower():
        return TennisTempleDrawParser()._parse_html(html)
    return DrawParser()._parse_html(html)


def validate_draw(draw_df: pd.DataFrame) -> None:
    """
    Validate the structural integrity of a parsed draw.

    Raises ValueError on any violation, so a mis-parsed draw fails loudly
    instead of producing silently wrong simulations.
    """
    if draw_df.empty:
        raise ValueError("Draw is empty")

    if len(draw_df) != DRAW_SIZE:
        raise ValueError(f"Expected {DRAW_SIZE} players, found {len(draw_df)}")

    section_sizes = draw_df.groupby("section").size()
    if len(section_sizes) != SECTION_COUNT or not all(section_sizes == PLAYERS_PER_SECTION):
        raise ValueError(
            f"Expected {SECTION_COUNT} sections of {PLAYERS_PER_SECTION} players, "
            f"got {dict(section_sizes)}"
        )

    seeds = set(draw_df.loc[draw_df["seed"] > 0, "seed"].astype(int))
    if seeds != set(range(1, 33)):
        missing = sorted(set(range(1, 33)) - seeds)
        extra = sorted(seeds - set(range(1, 33)))
        raise ValueError(f"Seed set invalid (missing={missing}, unexpected={extra})")

    # Top-16 seeds must anchor each section (positions 0 and 15).
    for section, group in draw_df.groupby("section"):
        boundary_seeds = sorted(
            group.loc[group["position"].isin([0, PLAYERS_PER_SECTION - 1]), "seed"].astype(int)
        )
        if not set(boundary_seeds).issubset(set(range(1, 17))):
            LOGGER.warning(
                "Section %s boundary seeds %s are not all top-16 seeds; "
                "check the parsed positions",
                section,
                boundary_seeds,
            )

    LOGGER.info(
        "Draw validated: %d players, %d sections, seeds 1-32 present",
        len(draw_df),
        SECTION_COUNT,
    )
