"""Metrics on synthetic series with a KNOWN ground truth."""

import numpy as np
import pandas as pd
import pytest

from wiki_interest.analysis.metrics import analyze_series
from wiki_interest.analysis.ranking import rank
from wiki_interest.analysis.summary import summary_text
from wiki_interest.data.languages import edition_name, normalize_lang, wikidata_site
from wiki_interest.data.wikimedia import month_window
from wiki_interest.enums import Lang
from wiki_interest.models import Weights


IDX = pd.period_range("2024-09", periods=24, freq="M")


def series(growth=0.0, base=5000, noise=0.03, seed=0, season=0.12, n=24):
    rng = np.random.default_rng(seed)
    idx = pd.period_range("2023-09", periods=n, freq="M")
    t = np.arange(n)
    s = 1 + season * np.cos(2 * np.pi * (idx.month.to_numpy() - 1) / 12)
    return pd.Series(base * (1 + growth) ** (t / 12) * s * rng.normal(1, noise, n), index=idx)


def flat_project(n=24):
    return series(0.0, base=5e8, noise=0.01, seed=99, season=0.0, n=n)


def test_clear_growth_is_growing_high_confidence():
    r = analyze_series(series(0.30), flat_project())
    assert r.verdict == "growing"
    assert r.confidence == "high"
    assert 0.2 < r.yoy_norm < 0.4
    assert r.yoy_norm_ci90[0] > 0 and r.flags == []


def test_flat_seasonal_is_not_called_growth():
    r = analyze_series(series(0.0, noise=0.06), flat_project())
    assert r.verdict == "stable_or_unclear"
    assert r.confidence != "high" or r.trend_p_value < 0.05


def test_decline():
    r = analyze_series(series(-0.25), flat_project())
    assert r.verdict == "declining"


def test_single_month_spike_is_flagged():
    s = series(0.0)
    s.iloc[-3] *= 5
    r = analyze_series(s, flat_project())
    assert "SPIKE_DRIVEN" in r.flags
    assert r.confidence != "high"


def test_project_shift_detected():
    # topic +10%/yr but the whole wiki +30%/yr -> share of interest actually falls
    r = analyze_series(series(0.10), series(0.30, base=5e8, noise=0.01, seed=7, season=0))
    assert "PROJECT_SHIFT" in r.flags
    assert r.yoy_raw > 0 > r.yoy_norm


def test_low_volume_flag():
    r = analyze_series(series(0.3, base=80), flat_project())
    assert "LOW_VOLUME" in r.flags


def test_short_history_flag():
    r = analyze_series(series(0.3, n=12), flat_project(12))
    assert "SHORT_HISTORY" in r.flags


def test_scale_invariance_of_verdict():
    a = analyze_series(series(0.2, seed=3), flat_project())
    b = analyze_series(series(0.2, seed=3) * 10, flat_project())
    assert a.verdict == b.verdict and a.yoy_norm == pytest.approx(b.yoy_norm, rel=1e-9)


def test_deterministic():
    s = series(0.1, seed=5)
    assert analyze_series(s, flat_project()) == analyze_series(s, flat_project())


def test_ranking_prefers_growth_and_explains():
    res = {
        "a": analyze_series(series(0.4, seed=1), flat_project()),
        "b": analyze_series(series(0.0, seed=2), flat_project()),
        "c": analyze_series(series(-0.2, seed=3), flat_project()),
    }
    rk = rank(res, Weights.parse(None))
    assert [r.lang for r in rk] == ["a", "b", "c"]
    assert "fastest_growth" in rk[0].why


def test_weights_change_ranking():
    res = {
        "big_flat": analyze_series(series(0.0, base=50000, seed=1), flat_project()),
        "small_growing": analyze_series(series(0.3, base=2000, seed=2), flat_project()),
    }
    by_level = rank(res, Weights.parse("growth=0,level=1,confidence=0"))
    by_growth = rank(res, Weights.parse("growth=1,level=0,confidence=0"))
    assert by_level[0].lang == "big_flat" and by_growth[0].lang == "small_growing"


@pytest.mark.parametrize(
    "raw,code",
    [
        ("pl", "pl"),
        ("plwiki", "pl"),
        ("pl.wikipedia", "pl"),
        ("Polish", "pl"),
        ("польська", "pl"),
        ("Czech", "cs"),
        ("UK", "uk"),
    ],
)
def test_lang_aliases(raw, code):
    assert normalize_lang(raw) == code


def test_month_window_excludes_current_month():
    import datetime as dt

    w = month_window(24, dt.date(2026, 9, 26))
    assert str(w[-1]) == "2026-08" and str(w[0]) == "2024-09" and len(w) == 24


# ---- confidence must describe the verdict (review fixes)
def _idx_series(values, start="2022-09"):
    return pd.Series(values, index=pd.period_range(start, periods=len(values), freq="M"))


def test_stable_verdict_is_never_high_confidence():
    # long decline, then a partial recovery: last year vs previous year is unclear
    v = np.r_[np.linspace(10000, 3000, 24), np.linspace(3000, 6000, 12)] * np.random.default_rng(1).normal(1, 0.03, 36)
    r = analyze_series(_idx_series(v), _idx_series(np.full(36, 5e8)))
    assert r.verdict == "stable_or_unclear" and r.trend_p_value < 0.05
    assert r.confidence == "medium"
    assert r.confidence_reason_codes == ["CI_CROSSES_ZERO", "TREND_VS_YEAR"]


def test_rebound_against_long_trend_is_flagged():
    v = np.r_[np.linspace(20000, 3000, 24), np.full(12, 3000), np.linspace(4000, 7000, 12)]
    v = v * np.random.default_rng(0).normal(1, 0.03, 48)
    r = analyze_series(_idx_series(v), _idx_series(np.full(48, 5e8)))
    assert r.verdict == "growing" and r.trend_pct_year < 0
    assert "TREND_CONFLICT" in r.flags and r.confidence != "high"


def test_best_trend_label_is_not_called_growth_when_nothing_grows():
    res = {
        "falling": analyze_series(series(-0.25, seed=1), flat_project()),
        "flat": analyze_series(series(0.0, seed=2, noise=0.06), flat_project()),
    }
    rk = rank(res, Weights.parse(None))
    flat = next(r for r in rk if r.lang == "flat")
    assert "best_trend_in_set" in flat.why and "fastest_growth" not in flat.why


def test_summary_names_editions_and_the_comparison_window():
    r = analyze_series(series(0.30), flat_project())
    text = summary_text({"pt": r}, [], Lang.UK)
    assert "pt (португальська Вікіпедія)" in text and "за останні 12 міс. проти попередніх 12" in text
    assert "Portuguese Wikipedia" in summary_text({"pt": r}, [], Lang.EN)


@pytest.mark.parametrize(
    "raw,needle",
    [
        ("growth:0.5", "expected name=value"),
        ("growth=abc", "must be a number"),
        ("size=1", "unknown weight"),
        ("growth=-1", ">= 0"),
    ],
)
def test_bad_weights_give_readable_errors(raw, needle):
    with pytest.raises(ValueError, match=needle):
        Weights.parse(raw)


@pytest.mark.parametrize(
    "code,site",
    [("pl", "plwiki"), ("zh-yue", "zh_yuewiki"), ("zh-min-nan", "zh_min_nanwiki"), ("be-tarask", "be_x_oldwiki")],
)
def test_wikidata_site_ids(code, site):
    assert normalize_lang(code) == code
    assert wikidata_site(code) == site


@pytest.mark.parametrize(
    "code,name",
    [
        ("pl", "польська Вікіпедія"),
        ("he", "Вікіпедія мовою іврит"),
        ("fa", "перська Вікіпедія"),
        ("zh-yue", "zh-yue.wikipedia"),
    ],
)
def test_edition_names(code, name):
    assert edition_name(code) == name
