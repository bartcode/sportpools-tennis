"""
In-memory prediction job registry with progress tracking, result reuse and
disk-backed prediction caching that survives server restarts.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Dict, Optional

import pandas as pd

from sportpools.api.serialisers import serialise_result
from sportpools.model.pipeline import (
    PredictionRequest,
    ROUNDS,
    run_prediction,
)

LOGGER = logging.getLogger(__name__)

MAX_JOBS = 10


def _store():
    """
    The SQLite store, resolved lazily so tests can swap it out.
    """
    from sportpools.api import db

    return db.STORE


def _request_key(request: PredictionRequest) -> str:
    """Stable fingerprint of a prediction request."""
    return json.dumps(
        {
            "tournament": request.tournament,
            "year": request.year,
            "surfaces": list(request.surfaces),
            "black_points": request.black_points,
            "count": request.count,
            "draw_url": request.draw_url,
            "ratings_file": request.ratings_file,
        },
        sort_keys=True,
    )


def pool_from_records(records: list) -> pd.DataFrame:
    """
    Rebuild a pool DataFrame from serialised pool records, with the round
    probability columns the evaluator and optimiser expect.
    """
    rows = []
    for record in records:
        row = {
            "player": record["player"],
            "seed": record["seed"],
            "black": record["black"],
            "section": record.get("section", 0),
            "position": record.get("position", -1),
            "potency": record["potency"],
            "joker_bonus": record["joker_bonus"],
            "kluns_penalty": record["kluns_penalty"],
        }
        for index, column in enumerate(ROUNDS):
            row[column] = record["probs"][index]
        rows.append(row)
    return pd.DataFrame(rows)


def result_from_payload(payload: dict, request: PredictionRequest) -> SimpleNamespace:
    """
    A lightweight PredictionResult stand-in from a cached payload: enough for
    the evaluate and re-optimise endpoints (they only read per-model pools).
    """
    models = {}
    for surface, model in payload["models"].items():
        models[surface] = SimpleNamespace(
            pool=pool_from_records(model["pool"]),
        )
    return SimpleNamespace(request=request, models=models)


@dataclass
class Job:
    """One prediction run."""

    id: str
    status: str = "pending"  # pending | running | done | error
    progress: float = 0.0
    stage: str = "Queued"
    error: Optional[str] = None
    result_payload: Optional[dict] = None
    result_object: Optional[object] = None
    request_key: str = ""
    finished_at: Optional[float] = None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def public(self) -> dict:
        """JSON-safe status view for polling clients."""
        return {
            "id": self.id,
            "status": self.status,
            "progress": round(self.progress, 4),
            "stage": self.stage,
            "error": self.error,
        }


class JobManager:
    """Runs predictions in background threads and tracks their progress."""

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._registry_lock = threading.Lock()

    def start(self, request: PredictionRequest) -> str:
        """
        Start a prediction run in the background, or reuse an existing
        result: first from memory, then from the on-disk prediction cache
        (which survives restarts) while its age is within the cache TTL.
        :param request: Prediction options.
        :return: Job id.
        """
        key = _request_key(request)

        with self._registry_lock:
            for job in self._jobs.values():
                fresh_enough = (
                    job.finished_at is not None
                    and request.cache_ttl > 0
                    and (time.time() - job.finished_at) < request.cache_ttl * 3600
                )
                if job.request_key == key and job.status == "done" and fresh_enough:
                    LOGGER.info("Reusing finished job %s for identical request", job.id)
                    return job.id

            cached = None
            if request.cache_ttl > 0:
                try:
                    cached = _store().get_prediction(key)
                except Exception as error:  # noqa: BLE001 - cache is optional
                    LOGGER.warning("Prediction cache read failed: %s", error)
            if cached and cached["age_hours"] < request.cache_ttl:
                job = self._register_done_job(key, cached["payload"], request)
                LOGGER.info(
                    "Restored prediction from cache (%.1fh old) as job %s",
                    cached["age_hours"],
                    job.id,
                )
                return job.id

            job = Job(id=uuid.uuid4().hex[:12], request_key=key)
            self._jobs[job.id] = job
            self._prune()

        thread = threading.Thread(target=self._run, args=(job, request), daemon=True)
        thread.start()
        return job.id

    def _register_done_job(
        self, key: str, payload: dict, request: PredictionRequest
    ) -> Job:
        """Create an already-finished job from a cached payload."""
        job = Job(
            id=uuid.uuid4().hex[:12],
            status="done",
            progress=1.0,
            stage="Restored from cache",
            result_payload=payload,
            result_object=result_from_payload(payload, request),
            request_key=key,
            finished_at=time.time(),
        )
        self._jobs[job.id] = job
        self._prune()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        """Fetch a job by id."""
        return self._jobs.get(job_id)

    def latest_done(self) -> Optional[Job]:
        """The most recently finished job, if any."""
        done = [job for job in self._jobs.values() if job.status == "done"]
        return done[-1] if done else None

    def _prune(self) -> None:
        """Keep only the most recent jobs."""
        if len(self._jobs) <= MAX_JOBS:
            return
        for job_id in sorted(self._jobs)[:-MAX_JOBS]:
            self._jobs.pop(job_id, None)

    def _run(self, job: Job, request: PredictionRequest) -> None:
        def progress(fraction: float, stage: str) -> None:
            with job.lock:
                job.progress = fraction
                job.stage = stage

        with job.lock:
            job.status = "running"
        try:
            result = run_prediction(request, progress=progress)
            with job.lock:
                job.result_payload = serialise_result(result)
                job.result_object = result
                job.status = "done"
                job.progress = 1.0
                job.stage = "Done"
                job.finished_at = time.time()
            try:
                _store().save_prediction(job.request_key, job.result_payload)
            except Exception as error:  # noqa: BLE001 - cache is optional
                LOGGER.warning("Prediction cache write failed: %s", error)
        except Exception as error:  # noqa: BLE001 - surfaced to the client
            LOGGER.exception("Prediction job %s failed", job.id)
            with job.lock:
                job.status = "error"
                job.error = str(error)
                job.stage = "Failed"


JOBS = JobManager()
