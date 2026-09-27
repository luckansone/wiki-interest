"""Statistics on one monthly series: YoY, bootstrap CI, robust trend, share of attention."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from wiki_interest.config import THRESHOLDS


def yoy(x: np.ndarray, h: int) -> float | None:
    """Sum of the last h months / sum of the h months before - 1."""
    prev, last = x[-2 * h : -h].sum(), x[-h:].sum()
    return None if prev <= 0 else float(last / prev - 1)


def bootstrap_ci(x: np.ndarray, h: int) -> tuple[float, float] | None:
    """CI for YoY: resample month pairs (t, t-h) of the last 2h months. Deterministic (fixed seed)."""
    prev, last = x[-2 * h : -h], x[-h:]
    if prev.sum() <= 0:
        return None
    rng = np.random.default_rng(THRESHOLDS.seed)
    idx = rng.integers(0, h, size=(THRESHOLDS.bootstrap_iters, h))
    p, l = prev[idx].sum(axis=1), last[idx].sum(axis=1)
    ratios = np.where(p > 0, l / np.maximum(p, 1e-12) - 1, np.nan)
    a = (1 - THRESHOLDS.ci_level) / 2
    lo, hi = np.nanquantile(ratios, [a, 1 - a])
    return float(lo), float(hi)


def trend(y: np.ndarray) -> tuple[float, float]:
    """Theil–Sen slope of y per month as %/year (y is log1p of the series) and Mann–Kendall p-value."""
    n = len(y)
    if n < 6 or np.ptp(y) <= 0:
        return 0.0, 1.0
    t = np.arange(n)
    slope = stats.theilslopes(y, t)[0]
    _, p_value = stats.kendalltau(t, y)  # Mann-Kendall == Kendall tau vs time
    return float(math.expm1(slope * 12)), float(p_value)


def per_million(topic: np.ndarray, project: np.ndarray) -> np.ndarray:
    """Return views per million views of the whole edition; gaps are filled from the neighbors."""
    vpm = np.where(project > 0, topic / np.maximum(project, 1) * 1e6, np.nan)
    return pd.Series(vpm).ffill().bfill().fillna(0).to_numpy()


def per_million_series(topic: pd.Series, project: pd.Series) -> pd.Series:
    """Return the share of attention of `per_million` as a monthly Series (for charts)."""
    proj = project.replace(0, pd.NA).astype("float")
    return (topic / proj * 1e6).astype(float).ffill().bfill().fillna(0)
