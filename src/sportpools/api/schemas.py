"""
Pydantic schemas for the web API.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    tournament: str = "us-open"
    year: int = 2026
    surfaces: List[str] = Field(default_factory=lambda: ["hard", "all"])
    black_points: int = 20
    count: int = 15
    draw_url: Optional[str] = None
    ratings_file: Optional[str] = None
    cache_ttl: float = 6.0


class EvaluateRequest(BaseModel):
    job_id: str
    surface: str = "hard"
    players: List[str]
    joker: str
    kluns: str
    black_points: int = 20
    count: int = 15


class OptimizeRequest(BaseModel):
    job_id: str
    surface: str = "hard"
    locked: List[str] = Field(default_factory=list)
    joker: Optional[str] = None
    kluns: Optional[str] = None
    black_points: int = 20
    count: int = 15


class SavedTeamIn(BaseModel):
    name: str
    tournament: str
    year: int
    surface: str = "hard"
    players: List[str]
    joker: str
    kluns: str
