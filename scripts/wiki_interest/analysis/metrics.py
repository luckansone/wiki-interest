"""Metrics, data-quality flags, verdict and confidence of one language series.

Deterministic: the same data always gives the same verdict. Thresholds live in
`config.Thresholds`; the rules are documented in references/METHODOLOGY.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from wiki_interest.analysis import stats
from wiki_interest.config import THRESHOLDS
from wiki_interest.enums import Confidence, Flag, Lang, Reason, Verdict
from wiki_interest.models import LangMetrics
from wiki_interest.text import FLAG_TEXT, REASON_TEXT


def _r(v, ndigits: int = 4) -> float | None:
    return None if v is None else round(float(v), ndigits)


def pct(v: float | None, na: str = "н/д") -> str:
    """0.2597 -> '+26%'; values that round to 0 -> '0%'."""
    if v is None:
        return na
    return "0%" if round(v * 100) == 0 else f"{v * 100:+.0f}%"


def fmt_int(v) -> str:
    """12345 -> '12 345' (narrow no-break space as the thousands separator)."""
    return f"{int(v):,}".replace(",", " ")


def verdict_of(ci: tuple[float, float] | None) -> Verdict:
    if ci is None:
        return Verdict.STABLE_OR_UNCLEAR
    if ci[0] > 0:
        return Verdict.GROWING
    if ci[1] < 0:
        return Verdict.DECLINING
    return Verdict.STABLE_OR_UNCLEAR


def confidence_of(verdict: Verdict, flags: list[Flag], significant: bool) -> tuple[Confidence, list[Reason | Flag]]:
    """Confidence in the verdict and the reasons it is not high (rule table in METHODOLOGY)."""
    codes: list[Reason | Flag] = []
    if verdict == Verdict.STABLE_OR_UNCLEAR:
        codes.append(Reason.CI_CROSSES_ZERO)
    if not significant:
        codes.append(Reason.NOT_SIGNIFICANT)
    elif verdict == Verdict.STABLE_OR_UNCLEAR:
        codes.append(Reason.TREND_VS_YEAR)
    codes += flags
    if len(flags) >= 2:
        return Confidence.LOW, codes
    if flags or not significant or verdict == Verdict.STABLE_OR_UNCLEAR:
        return Confidence.MEDIUM, codes
    return Confidence.HIGH, codes


def reason_text(code: Reason | Flag, r: LangMetrics, lang: Lang = Lang.UK) -> str:
    """Human text for a confidence reason code; flags reuse FLAG_TEXT."""
    if isinstance(code, Flag) or code in Flag.__members__:
        return FLAG_TEXT[lang][Flag(code)]
    return REASON_TEXT[lang][Reason(code)].format(p=r.trend_p_value, tr=pct(r.trend_pct_year))


def analyze_series(topic: pd.Series, project: pd.Series, missing: list[str] | None = None) -> LangMetrics:
    """Metrics for one language. `topic` and `project` are monthly views on the same index."""
    t = THRESHOLDS
    missing = missing or []
    x = topic.to_numpy(dtype=float)
    n = len(x)
    flags: list[Flag] = []

    # Normalized series: views per million views of the whole language edition.
    vpm = stats.per_million(x, project.to_numpy(dtype=float))

    h = 12 if n >= t.full_history_months else max(n // 2, 1)
    if n < t.full_history_months:
        flags.append(Flag.SHORT_HISTORY)

    last = x[-h:]
    median_level = float(np.median(last))
    yoy_raw = stats.yoy(x, h)
    yoy_norm = stats.yoy(vpm, h)
    ci = stats.bootstrap_ci(vpm, h)
    yoy_prev = stats.yoy(vpm[:-h], h) if n >= 3 * h else None  # previous year's growth, if data allows

    # Trend over the whole window on the normalized series (robust to outliers).
    slope_pct_year, p_value = stats.trend(np.log1p(vpm))

    # --- data-quality flags
    if median_level < t.low_volume_median:
        flags.append(Flag.LOW_VOLUME)
    if (
        yoy_raw is not None
        and yoy_norm is not None
        and np.sign(yoy_raw) != np.sign(yoy_norm)
        and max(abs(yoy_raw), abs(yoy_norm)) > t.project_shift_min
    ):
        flags.append(Flag.PROJECT_SHIFT)
    gain = last.sum() - x[-2 * h : -h].sum()
    spike_share = None
    if gain > 0:
        spike_share = float((last.max() - np.median(last)) / gain)
        if spike_share > t.spike_share_max:
            flags.append(Flag.SPIKE_DRIVEN)
    if missing:
        flags.append(Flag.MISSING_ARTICLE)

    verdict = verdict_of(ci)
    # A significant long-run trend in the opposite direction: last year is a rebound/reversal.
    significant = p_value < t.p_significant
    if significant and (
        (verdict == Verdict.GROWING and slope_pct_year < 0) or (verdict == Verdict.DECLINING and slope_pct_year > 0)
    ):
        flags.append(Flag.TREND_CONFLICT)
    confidence, codes = confidence_of(verdict, flags, significant)

    out = LangMetrics(
        months=n,
        yoy_window_months=h,
        median_views_month=round(median_level),
        views_per_million=round(float(np.median(vpm[-h:])), 2),
        yoy_raw=_r(yoy_raw),
        yoy_norm=_r(yoy_norm),
        yoy_norm_ci90=(_r(ci[0]), _r(ci[1])) if ci else None,
        yoy_norm_prev_year=_r(yoy_prev),
        trend_pct_year=_r(slope_pct_year),
        trend_p_value=round(p_value, 4),
        spike_share=_r(spike_share),
        verdict=verdict,
        confidence=confidence,
        flags=flags,
        confidence_reason_codes=codes,
        missing_articles=missing,
    )
    out.confidence_reasons = [reason_text(c, out, Lang.EN) for c in codes]
    return out
