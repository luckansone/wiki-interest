"""GET JSON with a disk cache and retry. All network access of the skill goes through `get_json`.

Completed months never change, so pageview responses are cached forever; Wikidata lookups
carry a TTL. With WI_FAKE_API=1 the synthetic responses of `data.fake` are returned instead,
without cache and without network.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from loguru import logger

from wiki_interest.config import MAX_ATTEMPTS, MAX_RETRY_WAIT_S, Settings
from wiki_interest.errors import ApiError
from wiki_interest.log import telemetry


log = logger.bind(scope="http")
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


def cache_path(url: str, params: dict | None, cache_dir: Path) -> Path:
    """Cache file of one request. The key format must stay stable, or every cache entry is lost."""
    key = url + "?" + json.dumps(params or {}, sort_keys=True)
    return cache_dir / (hashlib.sha1(key.encode()).hexdigest() + ".json")


def _read_cache(path: Path, ttl_s: float | None):
    """Return (hit, body)."""
    if not path.exists():
        return False, None
    try:
        cached = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):  # corrupt entry -> treat as a miss
        return False, None
    if cached and (ttl_s is None or time.time() - cached["fetched_at"] < ttl_s):
        return True, cached["body"]
    return False, None


def _write_cache(path: Path, body) -> None:
    # write-then-rename, so a concurrent run never reads a half-written file
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps({"fetched_at": time.time(), "body": body}))
    os.replace(tmp, path)


def get_json(url: str, params: dict | None = None, ttl_s: float | None = None):
    """GET JSON with disk cache and retry. Returns None on HTTP 404 (no data)."""
    settings = Settings.from_env()
    if settings.fake_api:
        from wiki_interest.data import fake  # imported lazily: demo/test mode only

        return fake.get_json(url, params, ttl_s)

    path = cache_path(url, params, settings.cache_dir)
    hit, body = _read_cache(path, ttl_s)
    if hit:
        telemetry.count("cache_hit")
        log.debug(f"cache hit  {_short(url)}")
        return body
    telemetry.count("cache_miss")
    if settings.offline:
        raise ApiError(f"offline mode and no cache for {url}", "unset WI_OFFLINE or run once with network access")

    last_err = None
    for attempt in range(MAX_ATTEMPTS):
        wait_s = 2**attempt
        try:
            telemetry.count("http_request")
            log.debug(f"GET        {_short(url)}")
            r = requests.get(
                url,
                params=params,
                timeout=30,
                headers={"User-Agent": settings.user_agent, "Accept": "application/json"},
            )
            if r.status_code in RETRY_STATUS:
                last_err = f"HTTP {r.status_code}"
                # Wikidata's anonymous limit answers 429 with Retry-After ~15 s; honor it.
                retry_after = r.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    wait_s = min(max(int(retry_after), 1) + 1, MAX_RETRY_WAIT_S)
            else:
                if r.status_code == 404:
                    body = None
                else:
                    r.raise_for_status()
                    body = r.json()
                _write_cache(path, body)
                return body
        except requests.RequestException as e:  # network hiccup -> retry
            last_err = str(e)
        if attempt < MAX_ATTEMPTS - 1:
            telemetry.count("http_retry")
            log.warning(f"{last_err} from {urlsplit(url).netloc}, retry {attempt + 2}/{MAX_ATTEMPTS} in {wait_s} s")
            time.sleep(wait_s)
    raise ApiError(f"request failed after retries: {url} ({last_err})")


def _short(url: str, width: int = 90) -> str:
    """Host + path, shortened for one log line."""
    parts = urlsplit(url)
    s = parts.netloc + parts.path
    return s if len(s) <= width else s[: width - 1] + "…"
