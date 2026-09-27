"""Pydantic models: input parsing, and that saved runs (run.json) load back into the right types."""

import json

import pytest

from wiki_interest.config import Settings
from wiki_interest.enums import Confidence, Flag, Lang, LogMode, Reason, Verdict
from wiki_interest.models import LangMetrics, NoData, RunRecord, Weights


METRICS = {
    "months": 24,
    "yoy_window_months": 12,
    "median_views_month": 2500,
    "views_per_million": 4.98,
    "yoy_raw": 0.0086,
    "yoy_norm": -0.0061,
    "yoy_norm_ci90": [-0.0332, 0.0217],
    "yoy_norm_prev_year": None,
    "trend_pct_year": -0.0006,
    "trend_p_value": 0.9413,
    "spike_share": 0.5,
    "verdict": "stable_or_unclear",
    "confidence": "medium",
    "flags": ["SPIKE_DRIVEN"],
    "confidence_reason_codes": ["CI_CROSSES_ZERO", "NOT_SIGNIFICANT", "SPIKE_DRIVEN"],
    "missing_articles": [],
    "confidence_reasons": [],
}
RUN = {
    "run_id": "20260927-000000-abcdef",
    "question": None,
    "langs": ["cs", "tr"],
    "months": 24,
    "period": ["2024-09", "2026-08"],
    "fetched_on": "2026-09-27",
    "topics": [{"input": "Intermittent fasting", "label": "Intermittent fasting", "qid": "Q1"}],
    "articles": {"cs": {"Intermittent fasting": "Přerušovaný půst"}, "tr": {}},
    "weights": {"growth": 0.5, "level": 0.3, "confidence": 0.2},
    "results": {
        "cs": METRICS,
        "tr": {"status": "no_data", "missing_articles": ["Intermittent fasting"], "flags": ["MISSING_ARTICLE"]},
    },
    "ranking": [{"lang": "cs", "score": 0.1, "position": 1, "why": ["spike_driven"]}],
    "summary_text": "…",
    "synthetic": True,
    "command": "wi analyze",
}


def test_old_run_json_loads_with_the_right_result_types():
    """run.json files written before the refactor (no out_lang, no conclusion) must still re-render."""
    run = RunRecord.model_validate_json(json.dumps(RUN))
    cs, tr = run.results["cs"], run.results["tr"]
    assert isinstance(cs, LangMetrics) and isinstance(tr, NoData)
    assert cs.verdict is Verdict.STABLE_OR_UNCLEAR and cs.confidence is Confidence.MEDIUM
    assert cs.confidence_reason_codes == [Reason.CI_CROSSES_ZERO, Reason.NOT_SIGNIFICANT, Flag.SPIKE_DRIVEN]
    assert run.out_lang is Lang.UK and run.conclusion is None
    assert list(run.measured) == ["cs"] and run.no_data == ["tr"] and run.yoy_window == 12


def test_run_json_round_trip_is_lossless():
    run = RunRecord.model_validate(RUN)
    again = RunRecord.model_validate_json(json.dumps(run.model_dump(mode="json")))
    assert again == run


def test_metrics_dict_with_missing_articles_is_not_mistaken_for_no_data():
    """Both shapes have missing_articles and flags; only `status` may decide."""
    run = RunRecord.model_validate({**RUN, "results": {"cs": {**METRICS, "missing_articles": ["x"]}}})
    assert isinstance(run.results["cs"], LangMetrics)


def test_enums_serialize_as_plain_strings():
    assert json.dumps({"v": Verdict.GROWING}) == '{"v": "growing"}'
    assert Confidence.HIGH.score == 1.0 and Confidence.LOW.score == 0.0


def test_weights_parse_defaults_and_overrides():
    assert Weights.parse(None) == Weights(growth=0.5, level=0.3, confidence=0.2)
    assert Weights.parse("level=0.6, growth=0.2").model_dump() == {"growth": 0.2, "level": 0.6, "confidence": 0.2}


@pytest.mark.parametrize(
    "env,field,value",
    [
        ({"WI_OUT": "/tmp/x"}, "out_dir", "/tmp/x"),
        ({"WI_FAKE_API": "1"}, "fake_api", True),
        ({"WI_OFFLINE": "1"}, "offline", True),
        ({"WI_LOG": "PLAIN"}, "log_mode", LogMode.PLAIN),
        ({"WI_LOG_LEVEL": "debug"}, "log_level", "DEBUG"),
    ],
)
def test_settings_from_env(monkeypatch, env, field, value):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    got = getattr(Settings.from_env(), field)
    assert str(got) == str(value) if field == "out_dir" else got == value


def test_user_agent_carries_the_contact(monkeypatch):
    monkeypatch.setenv("WI_CONTACT", "team@example.com")
    assert Settings.from_env().user_agent.endswith("(team@example.com)")
