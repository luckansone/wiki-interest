"""Trend metrics, data-quality flags, verdict, confidence and ranking.

Everything here is deterministic (fixed RNG seed), so the same data always gives the
same verdict. Thresholds are constants at the top so they are easy to audit.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats


LOW_VOLUME_MEDIAN = 300  # median views/month below this -> percentages are noisy
SPIKE_SHARE_MAX = 0.40  # one month contributing >40% of the YoY gain -> spike-driven
PROJECT_SHIFT_MIN = 0.05  # raw vs normalized YoY disagree in sign and one is >5%
P_SIGNIFICANT = 0.05
BOOTSTRAP_ITERS = 1000
CI_LEVEL = 0.90
SEED = 42

VERDICTS = ("growing", "declining", "stable_or_unclear")
CONF_SCORE = {"high": 1.0, "medium": 0.5, "low": 0.0}


def _yoy(x: np.ndarray, h: int) -> float | None:
    prev, last = x[-2 * h : -h].sum(), x[-h:].sum()
    return None if prev <= 0 else float(last / prev - 1)


def _bootstrap_ci(x: np.ndarray, h: int) -> tuple[float, float] | None:
    """CI for YoY: resample month pairs (t, t-h) of the last 2h months."""
    prev, last = x[-2 * h : -h], x[-h:]
    if prev.sum() <= 0:
        return None
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, h, size=(BOOTSTRAP_ITERS, h))
    p, l = prev[idx].sum(axis=1), last[idx].sum(axis=1)
    ratios = np.where(p > 0, l / np.maximum(p, 1e-12) - 1, np.nan)
    a = (1 - CI_LEVEL) / 2
    lo, hi = np.nanquantile(ratios, [a, 1 - a])
    return float(lo), float(hi)


def analyze_series(topic: pd.Series, project: pd.Series, missing: list[str] | None = None) -> dict:
    """Metrics for one language. `topic` and `project` are monthly views on the same index."""
    missing = missing or []
    x = topic.to_numpy(dtype=float)
    proj = project.to_numpy(dtype=float)
    n = len(x)
    flags: list[str] = []

    # Normalized series: views per million views of the whole language edition.
    vpm = np.where(proj > 0, x / np.maximum(proj, 1) * 1e6, np.nan)
    vpm = pd.Series(vpm).ffill().bfill().fillna(0).to_numpy()

    h = 12 if n >= 24 else max(n // 2, 1)
    if n < 24:
        flags.append("SHORT_HISTORY")

    last = x[-h:]
    median_level = float(np.median(last))
    yoy_raw = _yoy(x, h)
    yoy_norm = _yoy(vpm, h)
    ci = _bootstrap_ci(vpm, h)
    yoy_prev = _yoy(vpm[:-h], h) if n >= 3 * h else None  # previous year's growth, if data allows

    # Trend over the whole window on the normalized series (robust to outliers).
    t = np.arange(n)
    y = np.log1p(vpm)
    if n >= 6 and np.ptp(y) > 0:
        slope = stats.theilslopes(y, t)[0]
        tau, p_value = stats.kendalltau(t, y)  # Mann-Kendall == Kendall tau vs time
        slope_pct_year = float(math.expm1(slope * 12))
        p_value = float(p_value)
    else:
        slope_pct_year, p_value = 0.0, 1.0

    # --- data-quality flags
    if median_level < LOW_VOLUME_MEDIAN:
        flags.append("LOW_VOLUME")
    if (
        yoy_raw is not None
        and yoy_norm is not None
        and np.sign(yoy_raw) != np.sign(yoy_norm)
        and max(abs(yoy_raw), abs(yoy_norm)) > PROJECT_SHIFT_MIN
    ):
        flags.append("PROJECT_SHIFT")
    gain = last.sum() - x[-2 * h : -h].sum()
    spike_share = None
    if gain > 0:
        spike_share = float((last.max() - np.median(last)) / gain)
        if spike_share > SPIKE_SHARE_MAX:
            flags.append("SPIKE_DRIVEN")
    if missing:
        flags.append("MISSING_ARTICLE")

    # --- verdict from the CI of normalized YoY
    if ci is None:
        verdict = "stable_or_unclear"
    elif ci[0] > 0:
        verdict = "growing"
    elif ci[1] < 0:
        verdict = "declining"
    else:
        verdict = "stable_or_unclear"

    # A significant long-run trend in the opposite direction: last year is a rebound/reversal.
    trend_significant = p_value < P_SIGNIFICANT
    if trend_significant and (
        (verdict == "growing" and slope_pct_year < 0) or (verdict == "declining" and slope_pct_year > 0)
    ):
        flags.append("TREND_CONFLICT")

    # --- confidence in the verdict (rule table in METHODOLOGY)
    codes = []
    if verdict == "stable_or_unclear":
        codes.append("CI_CROSSES_ZERO")
    if not trend_significant:
        codes.append("NOT_SIGNIFICANT")
    elif verdict == "stable_or_unclear":
        codes.append("TREND_VS_YEAR")
    codes += flags
    if len(flags) >= 2:
        confidence = "low"
    elif flags or not trend_significant or verdict == "stable_or_unclear":
        confidence = "medium"
    else:
        confidence = "high"

    out = {
        "months": n,
        "yoy_window_months": h,
        "median_views_month": round(median_level),
        "views_per_million": round(float(np.median(vpm[-h:])), 2),
        "yoy_raw": _r(yoy_raw),
        "yoy_norm": _r(yoy_norm),
        "yoy_norm_ci90": [_r(ci[0]), _r(ci[1])] if ci else None,
        "yoy_norm_prev_year": _r(yoy_prev),
        "trend_pct_year": _r(slope_pct_year),
        "trend_p_value": round(p_value, 4),
        "spike_share": _r(spike_share),
        "verdict": verdict,
        "confidence": confidence,
        "flags": flags,
        "confidence_reason_codes": codes,
        "missing_articles": missing,
    }
    out["confidence_reasons"] = [reason_text(c, out, "en") for c in codes]
    return out


def _r(v, ndigits=4):
    return None if v is None else round(float(v), ndigits)


FLAG_TEXT_EN = {
    "SHORT_HISTORY": "less than 24 months of data: seasonality not controlled",
    "LOW_VOLUME": f"low volume (median < {LOW_VOLUME_MEDIAN} views/month)",
    "PROJECT_SHIFT": "raw and traffic-adjusted growth disagree: whole-wiki traffic shift",
    "SPIKE_DRIVEN": "growth driven by a single-month spike",
    "MISSING_ARTICLE": "some topic articles do not exist in this language",
    "TREND_CONFLICT": "last-year change contradicts the significant long-run trend (rebound or reversal)",
}
FLAG_TEXT_UK = {
    "SHORT_HISTORY": "менше 24 міс. даних: сезонність не врахована",
    "LOW_VOLUME": f"малий обсяг (медіана < {LOW_VOLUME_MEDIAN} переглядів/міс.)",
    "PROJECT_SHIFT": "сирий і нормалізований ріст розходяться: зсув трафіку всього розділу",
    "SPIKE_DRIVEN": "ріст дає один місяць-сплеск",
    "MISSING_ARTICLE": "частини статей теми немає в цьому розділі",
    "TREND_CONFLICT": "зміна за останній рік суперечить значущому довгостроковому тренду (відскок або розворот)",
}


def reason_text(code: str, r: dict, lang: str = "uk") -> str:
    """Human text for a confidence reason code; flags reuse FLAG_TEXT_*."""
    if code in FLAG_TEXT_EN:
        return (FLAG_TEXT_UK if lang == "uk" else FLAG_TEXT_EN)[code]
    p, tr = r["trend_p_value"], pct(r["trend_pct_year"])
    return {
        ("CI_CROSSES_ZERO", "en"): "90% CI of the adjusted change includes 0",
        ("CI_CROSSES_ZERO", "uk"): "90% ДІ зміни з поправкою містить 0",
        ("NOT_SIGNIFICANT", "en"): f"long-run trend not statistically significant (p={p:.2f})",
        ("NOT_SIGNIFICANT", "uk"): f"довгостроковий тренд статистично незначущий (p={p:.2f})",
        ("TREND_VS_YEAR", "en"): f"long-run trend {tr}/year is significant, but the last-year change is not confirmed",
        ("TREND_VS_YEAR", "uk"): f"довгостроковий тренд {tr}/рік значущий, але зміну за останній рік не підтверджено",
    }[(code, lang)]


# ---------------------------------------------------------------- ranking
def parse_weights(s: str | None) -> dict:
    w = {"growth": 0.5, "level": 0.3, "confidence": 0.2}
    for part in (s or "").split(","):
        if not part.strip():
            continue
        k, sep, v = part.partition("=")
        k = k.strip()
        if not sep:
            raise ValueError(f"bad weight '{part.strip()}': expected name=value")
        if k not in w:
            raise ValueError(f"unknown weight '{k}', use growth/level/confidence")
        try:
            w[k] = float(v)
        except ValueError:
            raise ValueError(f"weight '{k}' must be a number, got '{v.strip()}'") from None
        if w[k] < 0:
            raise ValueError(f"weight '{k}' must be >= 0")
    return w


def _z(vals: list[float]) -> list[float]:
    a = np.array(vals, dtype=float)
    sd = a.std()
    return [0.0] * len(a) if len(a) < 2 or sd == 0 else list((a - a.mean()) / sd)


def rank(results: dict[str, dict], weights: dict) -> list[dict]:
    """Score languages: normalized growth, share of interest, confidence."""
    langs = [l for l, r in results.items() if r.get("yoy_norm") is not None]
    if not langs:
        return []
    zg = _z([results[l]["yoy_norm"] for l in langs])
    zl = _z([math.log1p(results[l]["views_per_million"]) for l in langs])
    rows = []
    for i, l in enumerate(langs):
        r = results[l]
        score = (
            weights["growth"] * zg[i] + weights["level"] * zl[i] + weights["confidence"] * CONF_SCORE[r["confidence"]]
        )
        rows.append({"lang": l, "score": round(score, 3), "_zg": zg[i], "_zl": zl[i]})
    rows.sort(key=lambda d: d["score"], reverse=True)
    best_g = max(rows, key=lambda d: d["_zg"])["lang"]
    best_l = max(rows, key=lambda d: d["_zl"])["lang"]
    for pos, row in enumerate(rows, 1):
        r = results[row["lang"]]
        why = []
        if row["lang"] == best_g and len(rows) > 1:
            # "fastest growth" only for a confirmed rise; otherwise it is merely the least bad
            why.append("fastest_growth" if r["verdict"] == "growing" else "best_trend_in_set")
        if row["lang"] == best_l and len(rows) > 1:
            why.append("highest_share_of_interest")
        if r["verdict"] == "growing":
            why.append("growing")
        elif r["verdict"] == "declining":
            why.append("declining")
        why += [f.lower() for f in r["flags"]]
        row.update({"position": pos, "why": why})
        del row["_zg"], row["_zl"]
    return rows


# ---------------------------------------------------------------- summary text
VERDICT_UK = {"growing": "зростає", "declining": "спадає", "stable_or_unclear": "без чіткої зміни"}
CONF_UK = {"high": "висока", "medium": "середня", "low": "низька"}
WHY_UK = {
    "fastest_growth": "найшвидший ріст",
    "highest_share_of_interest": "найвища частка інтересу",
    "best_trend_in_set": "найкраща динаміка серед обраних, але ріст не підтверджено",
    "growing": "зростає",
    "declining": "спадає",
    "spike_driven": "але ріст через сплеск",
    "project_shift": "зсув трафіку розділу",
    "low_volume": "малий обсяг",
    "missing_article": "не всі статті теми є",
    "short_history": "коротка історія",
    "trend_conflict": "суперечить довгостроковому тренду",
}
DISCLAIMER_UK = (
    "Перегляди Wikipedia — сигнал інтересу, а не готовності платити; мовний розділ ≠ країна. "
    "Використовуйте як підказку, що перевіряти далі."
)
DISCLAIMER_EN = (
    "Wikipedia pageviews signal interest, not willingness to pay; a language edition is not "
    "a country. Use this to pick what to validate next."
)


def fmt_int(v) -> str:
    return f"{int(v):,}".replace(",", "\u202f")


def pct(v) -> str:
    if v is None:
        return "н/д"
    return "0%" if round(v * 100) == 0 else f"{v * 100:+.0f}%"


def summary_text(results: dict, ranking: list[dict], lang_out: str = "uk") -> str:
    from wiki_api import edition_name  # local import keeps metrics free of network deps at import

    lines = []
    for l, r in results.items():
        ed = f"{l} ({edition_name(l, lang_out)})"
        if r.get("status") == "no_data":
            lines.append(
                f"{ed}: статті на цю тему немає — інтерес не виміряно (це не означає нульовий "
                f"інтерес; можна спробувати ширшу тему)."
                if lang_out == "uk"
                else f"{ed}: no article on this topic — interest not measured (not the same as zero "
                f"interest; a broader topic may exist)."
            )
            continue
        ci, h = r["yoy_norm_ci90"], r["yoy_window_months"]
        reasons = [reason_text(c, r, lang_out) for c in r["confidence_reason_codes"]]
        if lang_out == "uk":
            s = (
                f"{ed}: {VERDICT_UK[r['verdict']]} — {pct(r['yoy_norm'])} за останні {h} міс. проти попередніх {h} "
                f"з поправкою на трафік розділу (90% ДІ {pct(ci[0]) if ci else 'н/д'}…{pct(ci[1]) if ci else 'н/д'}; "
                f"сирі перегляди {pct(r['yoy_raw'])}), медіана {fmt_int(r['median_views_month'])} переглядів/міс.; "
                f"довіра {CONF_UK[r['confidence']]}"
            )
            if r.get("yoy_norm_prev_year") is not None:
                s += f"; та сама зміна роком раніше {pct(r['yoy_norm_prev_year'])}"
        else:
            s = (
                f"{ed}: {r['verdict']} — {pct(r['yoy_norm'])} last {h} months vs previous {h}, traffic-adjusted "
                f"(90% CI {pct(ci[0]) if ci else 'n/a'}..{pct(ci[1]) if ci else 'n/a'}; raw {pct(r['yoy_raw'])}), "
                f"median {r['median_views_month']:,} views/month; confidence {r['confidence']}"
            )
            if r.get("yoy_norm_prev_year") is not None:
                s += f"; same change a year earlier {pct(r['yoy_norm_prev_year'])}"
        if reasons:
            s += " (" + "; ".join(reasons) + ")"
        lines.append(s + ".")
    if len(ranking) > 1:
        top = ranking[:3]
        if lang_out == "uk":
            parts = []
            for row in top:
                why = ", ".join(WHY_UK[w] for w in row["why"] if w in WHY_UK) or "збалансований профіль"
                parts.append(f"{row['lang']} ({why})")
            lines.append("Рейтинг для подальшого дослідження: " + "; ".join(parts) + ".")
        else:
            lines.append(
                "Ranking to investigate next: "
                + "; ".join(f"{row['lang']} ({', '.join(row['why']) or 'balanced'})" for row in top)
                + "."
            )
    lines.append(DISCLAIMER_UK if lang_out == "uk" else DISCLAIMER_EN)
    return "\n".join(lines)
