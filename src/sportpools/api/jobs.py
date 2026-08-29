"""
In-memory prediction job registry with progress tracking and result reuse.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from sportpools.api.serialisers import serialise_result
from sportpools.model.pipeline import PredictionRequest, run_prediction

LOGGER = logging.getLogger(__name__)

MAX_JOBS = 10


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
        Start a prediction run in the background, or reuse a recently
        finished identical run while its sources are still fresh.
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

            job = Job(id=uuid.uuid4().hex[:12], request_key=key)
            self._jobs[job.id] = job
            self._prune()

        thread = threading.Thread(target=self._run, args=(job, request), daemon=True)
        thread.start()
        return job.id

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
        except Exception as error:  # noqa: BLE001 - surfaced to the client
            LOGGER.exception("Prediction job %s failed", job.id)
            with job.lock:
                job.status = "error"
                job.error = str(error)
                job.stage = "Failed"


JOBS = JobManager()
