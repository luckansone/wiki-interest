"""Wikidata sitelinks -> per-language article titles -> monthly pageviews.

Requests are shaped so follow-up runs hit the cache: Wikidata returns all sitelinks
(not only the requested languages), and pageviews are always fetched from
PAGEVIEWS_START to the last complete month, then sliced locally to --months.
"""

from __future__ import annotations

import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import pandas as pd
from loguru import logger

from wiki_interest import log as wlog
from wiki_interest.config import MAX_WORKERS, PAGEVIEWS_START, PAGEVIEWS_URL, WIKIDATA_TTL_S, WIKIDATA_URL
from wiki_interest.data import http
from wiki_interest.data.languages import wikidata_site
from wiki_interest.errors import TopicNotFoundError
from wiki_interest.models import Collected, LangData, ResolvedTopic


log = logger.bind(scope="fetch")


# ---------------------------------------------------------------- periods
def month_window(months: int, today: dt.date | None = None) -> list[pd.Period]:
    """Last `months` COMPLETE calendar months, oldest first."""
    today = today or dt.date.today()
    last = pd.Period(today, "M") - 1
    return [last - i for i in range(months - 1, -1, -1)]


def _ts(p: pd.Period, end: bool = False) -> str:
    d = p.end_time.date() if end else p.start_time.date()
    return d.strftime("%Y%m%d") + "00"


def _range(months: list[pd.Period]) -> str:
    # Always the full history up to the window end: one cached response serves any --months.
    start = min(pd.Period(PAGEVIEWS_START, "M"), months[0])
    return f"{_ts(start)}/{_ts(months[-1], end=True)}"


# ---------------------------------------------------------------- wikidata
def resolve_topic(topic: str, langs: list[str], source_site: str = "enwiki") -> ResolvedTopic:
    """Topic (QID or article title in `source_site`) -> QID, English label, titles per language."""
    # No sitefilter: the cached answer then serves any later set of languages.
    params = {
        "action": "wbgetentities",
        "props": "sitelinks|labels",
        "languages": "en",
        "format": "json",
        "redirects": "yes",
    }
    if re.fullmatch(r"[Qq]\d+", topic.strip()):
        params["ids"] = topic.strip().upper()
    else:
        params.update({"sites": source_site, "titles": topic.strip(), "normalize": "1"})
    body = http.get_json(WIKIDATA_URL, params, ttl_s=WIKIDATA_TTL_S)
    entities = (body or {}).get("entities", {})
    ent = next((e for k, e in entities.items() if not k.startswith("-") and "missing" not in e), None)
    if ent is None:
        raise TopicNotFoundError(f"topic '{topic}' not found in Wikidata via {source_site}")
    site_to_lang = {wikidata_site(l): l for l in langs}
    titles = {site_to_lang[s]: link["title"] for s, link in ent.get("sitelinks", {}).items() if s in site_to_lang}
    label = ent.get("labels", {}).get("en", {}).get("value", topic)
    log.info(f"{topic!r} → {ent['id']}, articles in {len(titles)}/{len(langs)} editions")
    return ResolvedTopic(topic=topic, qid=ent["id"], label=label, titles=titles)


# ---------------------------------------------------------------- pageviews
def _items_to_series(body, months: list[pd.Period]) -> pd.Series:
    s = pd.Series(0.0, index=pd.PeriodIndex(months, freq="M"))
    for it in (body or {}).get("items", []):
        p = pd.Period(dt.datetime.strptime(it["timestamp"][:8], "%Y%m%d"), "M")
        if p in s.index:
            s[p] = float(it["views"])
    return s


def article_views(lang: str, title: str, months: list[pd.Period]) -> pd.Series:
    """Monthly user (non-bot) views of one article, all access methods."""
    art = quote(title.replace(" ", "_"), safe="")
    url = f"{PAGEVIEWS_URL}/per-article/{lang}.wikipedia/all-access/user/{art}/monthly/{_range(months)}"
    return _items_to_series(http.get_json(url), months)


def project_views(lang: str, months: list[pd.Period]) -> pd.Series:
    """Monthly user views of the whole language edition (normalization denominator)."""
    url = f"{PAGEVIEWS_URL}/aggregate/{lang}.wikipedia/all-access/user/monthly/{_range(months)}"
    return _items_to_series(http.get_json(url), months)


# ---------------------------------------------------------------- everything for one run
def collect(
    topics: list[str], langs: list[str], months: int, source_site: str = "enwiki", today: dt.date | None = None
) -> Collected:
    """Fetch everything the analysis needs, pageviews in parallel."""
    window = month_window(months, today)
    resolved = [resolve_topic(t, langs, source_site) for t in topics]

    jobs = {("project", l, None): (project_views, (l, window)) for l in langs}
    for r in resolved:
        for l, title in r.titles.items():
            jobs[("article", l, title)] = (article_views, (l, title, window))
    log.info(f"{len(jobs)} pageview series for {len(langs)} editions, {window[0]} – {window[-1]}")
    results = {}
    with ThreadPoolExecutor(MAX_WORKERS) as ex, wlog.progress(len(jobs), "fetch") as advance:
        futures = {ex.submit(fn, *args): key for key, (fn, args) in jobs.items()}
        for f in as_completed(futures):
            results[futures[f]] = f.result()
            advance()

    per_lang = {}
    for l in langs:
        arts = {r.label: r.titles.get(l) for r in resolved}
        found = {lab: t for lab, t in arts.items() if t}
        series = [results[("article", l, t)] for t in found.values()]
        per_lang[l] = LangData(
            articles=found,
            missing=[lab for lab, t in arts.items() if not t],
            topic_views=sum(series) if series else None,
            project_views=results[("project", l, None)],
        )
    return Collected(
        window=window, resolved=resolved, per_lang=per_lang, fetched_on=(today or dt.date.today()).isoformat()
    )
