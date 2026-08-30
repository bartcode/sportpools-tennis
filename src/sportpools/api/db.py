"""
SQLite-backed storage for saved teams and cached predictions.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Optional

LOGGER = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data") / "sportpools.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    tournament TEXT NOT NULL,
    year INTEGER NOT NULL,
    surface TEXT NOT NULL DEFAULT 'hard',
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS predictions (
    key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


class TeamStore:
    """Saved-team persistence on SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = Path(
            db_path or os.environ.get("SPORTPOOLS_DB", DEFAULT_DB_PATH)
        )
        self._lock = threading.Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def list_teams(self) -> List[dict]:
        """All saved teams, newest first."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, name, tournament, year, surface, created_at FROM teams"
                " ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def save_team(
        self, name: str, tournament: str, year: int, surface: str, payload: dict
    ) -> dict:
        """
        Save a team; replaces an earlier team with the same name.
        :return: The stored row.
        """
        with self._lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM teams WHERE name = ? AND tournament = ? AND year = ?",
                (name, tournament, year),
            )
            cursor = connection.execute(
                "INSERT INTO teams (name, tournament, year, surface, payload)"
                " VALUES (?, ?, ?, ?, ?)",
                (name, tournament, year, surface, json.dumps(payload)),
            )
            team_id = cursor.lastrowid
        return self.get_team(team_id)

    def get_team(self, team_id: int) -> Optional[dict]:
        """Fetch one saved team with its payload."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM teams WHERE id = ?", (team_id,)
            ).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["payload"] = json.loads(record["payload"])
        return record

    def delete_team(self, team_id: int) -> bool:
        """Delete a saved team; returns whether it existed."""
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM teams WHERE id = ?", (team_id,))
        return cursor.rowcount > 0

    def save_prediction(self, key: str, payload: dict) -> None:
        """Persist a prediction result under its request fingerprint."""
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO predictions (key, payload, created_at) VALUES (?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET payload = excluded.payload,"
                " created_at = excluded.created_at",
                (key, json.dumps(payload), time.time()),
            )

    def get_prediction(self, key: str) -> Optional[dict]:
        """
        Fetch a cached prediction by fingerprint.
        :return: {"payload": dict, "age_hours": float} or None.
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload, created_at FROM predictions WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return {
            "payload": json.loads(row["payload"]),
            "age_hours": (time.time() - row["created_at"]) / 3600,
        }

    def latest_prediction(self) -> Optional[dict]:
        """
        The most recently persisted prediction across all request variants.
        :return: {"key", "payload", "age_hours"} or None when nothing cached.
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT key, payload, created_at FROM predictions"
                " ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return {
            "key": row["key"],
            "payload": json.loads(row["payload"]),
            "age_hours": (time.time() - row["created_at"]) / 3600,
        }


STORE = TeamStore()
