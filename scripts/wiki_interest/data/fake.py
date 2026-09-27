"""Offline stand-in for Wikimedia/Wikidata that returns responses in the real JSON format.

Values are SYNTHETIC (deterministic formulas + seeded noise). They exist for the demo mode
(WI_FAKE_API=1), tests and evals, not to say anything about real interest. Reports made
from them carry a red "DEMO" banner.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from urllib.parse import unquote

import numpy as np

from wiki_interest.config import WIKIDATA_URL
from wiki_interest.data.languages import wikidata_site


# title -> (qid, {lang: localized title}); only a few langs lack an article on purpose.
TOPICS = {
    "Intermittent fasting": (
        "Q_FAKE_IF",
        {"pl": "Post przerywany", "cs": "Přerušovaný půst", "uk": "Інтервальне голодування"},
    ),
    "Astronomy": ("Q_FAKE_ASTRO", {"uk": "Астрономія", "pl": "Astronomia", "zh-yue": "天文學"}),
    "Solar System": ("Q_FAKE_SOLAR", {"uk": "Сонячна система", "pl": "Układ Słoneczny"}),
    "Telescope": ("Q_FAKE_TEL", {"uk": "Телескоп", "pl": "Teleskop"}),
    "English language": ("Q_FAKE_EN", {l: f"English-{l}" for l in ["uk", "pl", "tr", "vi", "id", "pt"]}),
    "International English Language Testing System": (
        "Q_FAKE_IELTS",
        {l: f"IELTS-{l}" for l in ["uk", "pl", "tr", "vi", "pt"]},
    ),  # no 'id'
    "Test of English as a Foreign Language": (
        "Q_FAKE_TOEFL",
        {l: f"TOEFL-{l}" for l in ["uk", "pl", "tr", "vi", "id", "pt"]},
    ),
}

# Yearly growth of topic views and of the whole wiki per language (synthetic scenarios).
TOPIC_GROWTH = {"pl": 0.30, "cs": 0.0, "uk": 0.12, "tr": 0.25, "vi": 0.05, "id": 0.15, "pt": -0.10}
PROJECT_GROWTH = {"uk": 0.20}  # uk wiki traffic grows faster than astronomy -> PROJECT_SHIFT
BASE = {"pl": 9000, "cs": 2500, "uk": 4000, "tr": 6000, "vi": 3000, "id": 5000, "pt": 7000}
SPIKE = {"vi"}  # one viral month in the last year


def _months(start: str, end: str):
    s = dt.datetime.strptime(start[:8], "%Y%m%d")
    e = dt.datetime.strptime(end[:8], "%Y%m%d")
    out, cur = [], dt.date(s.year, s.month, 1)
    while cur <= e.date():
        out.append(cur)
        cur = dt.date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
    return out


def _series(lang: str, key: str, months, growth: float, base: float, spike: bool):
    rng = np.random.default_rng(int(hashlib.md5(f"{lang}|{key}".encode()).hexdigest()[:8], 16))
    n = len(months)
    t = np.arange(n)
    season = 1 + 0.12 * np.cos(2 * np.pi * (np.array([m.month for m in months]) - 1) / 12)
    y = base * (1 + growth) ** (t / 12) * season * rng.normal(1, 0.04, n)
    if spike:
        y[n - 4] *= 4.0
    return np.maximum(y, 0).round()


def get_json(url: str, params: dict | None = None, ttl_s: float | None = None):
    if url == WIKIDATA_URL:
        title = params.get("titles")
        if title not in TOPICS:
            return {"entities": {"-1": {"site": "enwiki", "title": title, "missing": ""}}}
        qid, links = TOPICS[title]
        sites = params["sitefilter"].split("|") if "sitefilter" in params else None
        return {
            "entities": {
                qid: {
                    "id": qid,
                    "labels": {"en": {"language": "en", "value": title}},
                    "sitelinks": {
                        wikidata_site(l): {"site": wikidata_site(l), "title": t}
                        for l, t in links.items()
                        if sites is None or wikidata_site(l) in sites
                    },
                }
            }
        }
    m = re.search(r"/per-article/([\w-]+)\.wikipedia/[^/]+/[^/]+/([^/]+)/monthly/(\d+)/(\d+)", url)
    if m:
        lang, art, start, end = m.group(1), unquote(m.group(2)), m.group(3), m.group(4)
        months = _months(start, end)
        share = 1.0 if not any(k in art for k in ("IELTS", "TOEFL")) else 0.15
        y = _series(
            lang,
            art,
            months,
            TOPIC_GROWTH.get(lang, 0.0),
            BASE.get(lang, 3000) * share,
            lang in SPIKE and "English" in art,
        )
        return {
            "items": [
                {
                    "project": f"{lang}.wikipedia",
                    "article": art,
                    "granularity": "monthly",
                    "timestamp": d.strftime("%Y%m%d00"),
                    "access": "all-access",
                    "agent": "user",
                    "views": int(v),
                }
                for d, v in zip(months, y)
            ]
        }
    m = re.search(r"/aggregate/([\w-]+)\.wikipedia/[^/]+/[^/]+/monthly/(\d+)/(\d+)", url)
    if m:
        lang, start, end = m.groups()
        months = _months(start, end)
        y = _series(lang, "__project__", months, PROJECT_GROWTH.get(lang, 0.0), 5e8, False)
        return {
            "items": [
                {
                    "project": f"{lang}.wikipedia",
                    "access": "all-access",
                    "agent": "user",
                    "granularity": "monthly",
                    "timestamp": d.strftime("%Y%m%d00"),
                    "views": int(v),
                }
                for d, v in zip(months, y)
            ]
        }
    raise AssertionError(f"unexpected URL in fake: {url}")
