"""Data layer: Wikidata sitelinks -> per-language article titles -> monthly pageviews.

All network access goes through `http_get_json`, so tests can replace it with a fake.
Responses are cached on disk: completed months never change, so pageview responses
are cached forever; Wikidata lookups are cached for 30 days.

Requests are shaped so follow-up runs hit the cache: Wikidata returns all sitelinks
(not only the requested languages), and pageviews are always fetched from
PAGEVIEWS_START to the last complete month, then sliced locally to --months.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests


PAGEVIEWS = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
WIKIDATA = "https://www.wikidata.org/w/api.php"
# Wikimedia asks every client to send a descriptive User-Agent with contact info.
USER_AGENT = "wiki-interest-skill/0.1 ({})".format(
    os.environ.get("WI_CONTACT", "https://github.com/ ; set WI_CONTACT env var")
)
CACHE_DIR = Path(os.environ.get("WI_CACHE", Path.home() / ".cache" / "wiki-interest"))
WIKIDATA_TTL_S = 30 * 24 * 3600
MAX_WORKERS = 8
MAX_ATTEMPTS = 5
MAX_RETRY_WAIT_S = 30
PAGEVIEWS_START = pd.Period("2015-07", "M")  # first month the Pageviews API has data for


class ApiError(RuntimeError):
    pass


# ---------------------------------------------------------------- languages
# alias -> Wikipedia language code. Codes themselves are always accepted.
_LANG_NAMES = {
    "en": ["english", "англійська"],
    "uk": ["ukrainian", "українська"],
    "pl": ["polish", "польська"],
    "cs": ["czech", "чеська"],
    "sk": ["slovak", "словацька"],
    "de": ["german", "німецька"],
    "fr": ["french", "французька"],
    "es": ["spanish", "іспанська"],
    "it": ["italian", "італійська"],
    "pt": ["portuguese", "португальська"],
    "ro": ["romanian", "румунська"],
    "hu": ["hungarian", "угорська"],
    "bg": ["bulgarian", "болгарська"],
    "hr": ["croatian", "хорватська"],
    "sr": ["serbian", "сербська"],
    "sl": ["slovenian", "словенська"],
    "lt": ["lithuanian", "литовська"],
    "lv": ["latvian", "латиська"],
    "et": ["estonian", "естонська"],
    "fi": ["finnish", "фінська"],
    "sv": ["swedish", "шведська"],
    "no": ["norwegian", "норвезька"],
    "da": ["danish", "данська"],
    "nl": ["dutch", "нідерландська"],
    "el": ["greek", "грецька"],
    "tr": ["turkish", "турецька"],
    "ru": ["russian", "російська"],
    "be": ["belarusian", "білоруська"],
    "kk": ["kazakh", "казахська"],
    "ka": ["georgian", "грузинська"],
    "hy": ["armenian", "вірменська"],
    "az": ["azerbaijani", "азербайджанська"],
    "ar": ["arabic", "арабська"],
    "he": ["hebrew", "іврит"],
    "fa": ["persian", "farsi", "перська"],
    "hi": ["hindi", "гінді"],
    "bn": ["bengali", "бенгальська"],
    "ur": ["urdu", "урду"],
    "id": ["indonesian", "індонезійська"],
    "ms": ["malay", "малайська"],
    "vi": ["vietnamese", "вʼєтнамська", "в'єтнамська"],
    "th": ["thai", "тайська"],
    "zh": ["chinese", "китайська"],
    "ja": ["japanese", "японська"],
    "ko": ["korean", "корейська"],
    "tl": ["tagalog", "filipino", "тагальська"],
    "sw": ["swahili", "суахілі"],
}
LANG_ALIASES = {a: code for code, names in _LANG_NAMES.items() for a in names}
LANG_ALIASES.update({c: c for c in _LANG_NAMES})


def normalize_lang(raw: str) -> str:
    """'pl', 'plwiki', 'pl.wikipedia', 'Polish', 'польська' -> 'pl'."""
    s = raw.strip().lower()
    s = re.sub(r"(\.wikipedia(\.org)?|wiki)$", "", s)
    if s in LANG_ALIASES:
        return LANG_ALIASES[s]
    if re.fullmatch(r"[a-z]{2,3}(-[a-z]+)*", s):  # any other valid-looking code (zh-yue, zh-min-nan)
        return s
    raise ApiError(f"unknown language '{raw}'")


# Wikidata site ids use '_' where the domain uses '-' (zh-yue.wikipedia -> zh_yuewiki);
# a few editions kept a legacy id.
_SITE_OVERRIDES = {"be-tarask": "be_x_old"}


def wikidata_site(lang: str) -> str:
    return _SITE_OVERRIDES.get(lang, lang.replace("-", "_")) + "wiki"


def edition_name(lang: str, out: str = "uk") -> str:
    """'pl' -> 'польська Вікіпедія' / 'Polish Wikipedia'. Names the edition, never a country."""
    names = _LANG_NAMES.get(lang)
    if not names:
        return f"{lang}.wikipedia"
    if out == "en":
        return names[0].capitalize() + " Wikipedia"
    uk = next((n for n in names if re.search("[а-яіїєґ]", n)), names[0])
    return f"{uk} Вікіпедія" if uk.endswith("ька") else f"Вікіпедія мовою {uk}"


# ---------------------------------------------------------------- http + cache
def _cache_path(url: str, params: dict | None) -> Path:
    key = url + "?" + json.dumps(params or {}, sort_keys=True)
    return CACHE_DIR / (hashlib.sha1(key.encode()).hexdigest() + ".json")


def http_get_json(url: str, params: dict | None = None, ttl_s: float | None = None):
    """GET JSON with disk cache and retry. Returns None on HTTP 404 (no data)."""
    path = _cache_path(url, params)
    if path.exists():
        try:
            cached = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):  # corrupt entry -> treat as a miss
            cached = None
        if cached and (ttl_s is None or time.time() - cached["fetched_at"] < ttl_s):
            return cached["body"]
    if os.environ.get("WI_OFFLINE") == "1":
        raise ApiError(f"offline mode and no cache for {url}")

    last_err = None
    for attempt in range(MAX_ATTEMPTS):
        wait_s = 2**attempt
        try:
            r = requests.get(
                url, params=params, timeout=30, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
            )
            if r.status_code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {r.status_code}"
                # Wikidata's anonymous limit answers 429 with Retry-After ~15 s; honor it.
                ra = r.headers.get("Retry-After", "")
                if ra.isdigit():
                    wait_s = min(max(int(ra), 1) + 1, MAX_RETRY_WAIT_S)
            else:
                if r.status_code == 404:
                    body = None
                else:
                    r.raise_for_status()
                    body = r.json()
                # write-then-rename, so a concurrent run never reads a half-written file
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
                tmp.write_text(json.dumps({"fetched_at": time.time(), "body": body}))
                os.replace(tmp, path)
                return body
        except requests.RequestException as e:  # network hiccup -> retry
            last_err = str(e)
        if attempt < MAX_ATTEMPTS - 1:
            time.sleep(wait_s)
    raise ApiError(f"request failed after retries: {url} ({last_err})")


# ---------------------------------------------------------------- periods
def month_window(months: int, today: dt.date | None = None) -> list[pd.Period]:
    """Last `months` COMPLETE calendar months, oldest first."""
    today = today or dt.date.today()
    last = pd.Period(today, "M") - 1
    return [last - i for i in range(months - 1, -1, -1)]


def _ts(p: pd.Period, end: bool = False) -> str:
    d = p.end_time.date() if end else p.start_time.date()
    return d.strftime("%Y%m%d") + "00"


# ---------------------------------------------------------------- wikidata
def resolve_topic(topic: str, langs: list[str], source_site: str = "enwiki") -> dict:
    """Topic (QID or article title in `source_site`) -> {qid, label, titles{lang: title}}."""
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
    body = http_get_json(WIKIDATA, params, ttl_s=WIKIDATA_TTL_S)
    entities = (body or {}).get("entities", {})
    ent = next((e for k, e in entities.items() if not k.startswith("-") and "missing" not in e), None)
    if ent is None:
        raise ApiError(f"topic '{topic}' not found in Wikidata via {source_site}")
    site_to_lang = {wikidata_site(l): l for l in langs}
    titles = {site_to_lang[s]: link["title"] for s, link in ent.get("sitelinks", {}).items() if s in site_to_lang}
    label = ent.get("labels", {}).get("en", {}).get("value", topic)
    return {"topic": topic, "qid": ent["id"], "label": label, "titles": titles}


# ---------------------------------------------------------------- pageviews
def _items_to_series(body, months: list[pd.Period]) -> pd.Series:
    s = pd.Series(0.0, index=pd.PeriodIndex(months, freq="M"))
    for it in (body or {}).get("items", []):
        p = pd.Period(dt.datetime.strptime(it["timestamp"][:8], "%Y%m%d"), "M")
        if p in s.index:
            s[p] = float(it["views"])
    return s


def _range(months: list[pd.Period]) -> str:
    # Always the full history up to the window end: one cached response serves any --months.
    return f"{_ts(min(PAGEVIEWS_START, months[0]))}/{_ts(months[-1], end=True)}"


def article_views(lang: str, title: str, months: list[pd.Period]) -> pd.Series:
    """Monthly user (non-bot) views of one article, all access methods."""
    art = quote(title.replace(" ", "_"), safe="")
    url = f"{PAGEVIEWS}/per-article/{lang}.wikipedia/all-access/user/{art}/monthly/{_range(months)}"
    return _items_to_series(http_get_json(url), months)


def project_views(lang: str, months: list[pd.Period]) -> pd.Series:
    """Monthly user views of the whole language edition (normalization denominator)."""
    url = f"{PAGEVIEWS}/aggregate/{lang}.wikipedia/all-access/user/monthly/{_range(months)}"
    return _items_to_series(http_get_json(url), months)


def collect(
    topics: list[str], langs: list[str], months: int, source_site: str = "enwiki", today: dt.date | None = None
) -> dict:
    """Fetch everything the analysis needs, in parallel. Returns plain data structures."""
    window = month_window(months, today)
    resolved = [resolve_topic(t, langs, source_site) for t in topics]

    jobs = {("project", l, None): (project_views, (l, window)) for l in langs}
    for r in resolved:
        for l, title in r["titles"].items():
            jobs[("article", l, title)] = (article_views, (l, title, window))
    with ThreadPoolExecutor(MAX_WORKERS) as ex:
        futures = {k: ex.submit(fn, *args) for k, (fn, args) in jobs.items()}
        results = {k: f.result() for k, f in futures.items()}

    per_lang = {}
    for l in langs:
        arts = {r["label"]: r["titles"].get(l) for r in resolved}
        found = {lab: t for lab, t in arts.items() if t}
        series = [results[("article", l, t)] for t in found.values()]
        per_lang[l] = {
            "articles": found,
            "missing": [lab for lab, t in arts.items() if not t],
            "topic_views": (sum(series) if series else None),
            "project_views": results[("project", l, None)],
        }
    return {
        "window": window,
        "resolved": resolved,
        "per_lang": per_lang,
        "fetched_on": (today or dt.date.today()).isoformat(),
    }
