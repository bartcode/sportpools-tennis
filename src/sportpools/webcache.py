"""
Cached HTTP fetching for slowly-changing pages (draws, rating reports).
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests

LOGGER = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path(os.environ.get("SPORTPOOLS_CACHE_DIR", ".cache"))
DEFAULT_TTL_HOURS = 6.0
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) SportpoolsTennis/1.0"


def cache_age_hours(url: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> Optional[float]:
    """
    Age in hours of the cached copy for a URL, if one exists.
    """
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    cache_file = Path(cache_dir) / f"{digest}.html"
    if not cache_file.exists():
        return None
    return round((time.time() - cache_file.stat().st_mtime) / 3600, 2)


def fetch_cached(
    url: str,
    ttl_hours: float = DEFAULT_TTL_HOURS,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> str:
    """
    Fetch a URL through a file cache.

    Within the TTL the cached copy is used without a network round trip.
    On a fetch failure a stale cached copy is served if available, so a
    flaky connection does not break a run.

    :param url: URL to fetch.
    :param ttl_hours: Hours a cached copy stays fresh; 0 disables the cache.
    :param cache_dir: Directory for cached pages.
    :return: Response text.
    """
    cache_dir = Path(cache_dir)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    cache_file = cache_dir / f"{digest}.html"
    url_file = cache_dir / f"{digest}.url"

    fresh = (
        cache_file.exists()
        and ttl_hours > 0
        and (time.time() - cache_file.stat().st_mtime) < ttl_hours * 3600
    )

    if fresh:
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        LOGGER.info("Using cached page for %s (age %.1fh)", url, age_hours)
        return cache_file.read_text(encoding="utf-8")

    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()
    except requests.RequestException as error:
        if cache_file.exists():
            LOGGER.warning(
                "Fetching %s failed (%s); using stale cached copy from %s",
                url,
                error,
                time.strftime("%Y-%m-%d %H:%M", time.localtime(cache_file.stat().st_mtime)),
            )
            return cache_file.read_text(encoding="utf-8")
        raise

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(response.text, encoding="utf-8")
    url_file.write_text(url, encoding="utf-8")
    LOGGER.info("Fetched and cached %s -> %s", url, cache_file)

    return response.text
