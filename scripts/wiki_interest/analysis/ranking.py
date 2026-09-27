"""Rank languages by growth, share of interest and confidence, and explain each position."""

from __future__ import annotations

import math

import numpy as np

from wiki_interest.enums import Verdict, Why
from wiki_interest.models import LangResult, RankRow, Weights


def _z(vals: list[float]) -> list[float]:
    a = np.array(vals, dtype=float)
    sd = a.std()
    return [0.0] * len(a) if len(a) < 2 or sd == 0 else list((a - a.mean()) / sd)


def rank(results: dict[str, LangResult], weights: Weights) -> list[RankRow]:
    """Score = w_growth·z(yoy_norm) + w_level·z(log1p(vpm)) + w_conf·confidence score, across the run."""
    langs = [l for l, r in results.items() if r.has_data and r.yoy_norm is not None]
    if not langs:
        return []
    zg = _z([results[l].yoy_norm for l in langs])
    zl = _z([math.log1p(results[l].views_per_million) for l in langs])
    scored = []
    for i, l in enumerate(langs):
        score = weights.growth * zg[i] + weights.level * zl[i] + weights.confidence * results[l].confidence.score
        scored.append((l, round(score, 3), zg[i], zl[i]))
    scored.sort(key=lambda row: row[1], reverse=True)
    best_g = max(scored, key=lambda row: row[2])[0]
    best_l = max(scored, key=lambda row: row[3])[0]

    rows = []
    for pos, (l, score, _, _) in enumerate(scored, 1):
        r = results[l]
        why: list[Why] = []
        if l == best_g and len(scored) > 1:
            # "fastest growth" only for a confirmed rise; otherwise it is merely the least bad
            why.append(Why.FASTEST_GROWTH if r.verdict == Verdict.GROWING else Why.BEST_TREND_IN_SET)
        if l == best_l and len(scored) > 1:
            why.append(Why.HIGHEST_SHARE_OF_INTEREST)
        if r.verdict == Verdict.GROWING:
            why.append(Why.GROWING)
        elif r.verdict == Verdict.DECLINING:
            why.append(Why.DECLINING)
        why += [Why(f.lower()) for f in r.flags]
        rows.append(RankRow(lang=l, score=score, position=pos, why=why))
    return rows
