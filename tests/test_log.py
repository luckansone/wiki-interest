"""Logging: quiet for agents (piped stderr), btop-like widgets in rich mode."""

import pandas as pd
from rich.console import Console

from test_models import RUN
from wiki_interest import log
from wiki_interest.enums import LogMode
from wiki_interest.models import RunRecord


def test_auto_mode_is_quiet_when_stderr_is_piped():
    assert log.setup(LogMode.AUTO) == LogMode.QUIET  # pytest captures stderr, like an agent's tool does
    assert not log.is_rich()


def test_quiet_mode_shows_warnings_only(capsys):
    log.setup(LogMode.QUIET)
    log.logger.info("hidden")
    log.logger.warning("shown")
    assert capsys.readouterr().err == "wi: warning: shown\n"


def test_meter_is_centered_and_clipped():
    assert log._meter(0.0).plain == "··········┊··········"
    assert log._meter(0.25).plain == "··········┊■■■■■·····"
    assert log._meter(-9.0).plain == "■■■■■■■■■■┊··········"  # clipped at full scale
    assert log._meter(None).plain.count("■") == 0


def test_sparkline_uses_the_full_range():
    s = log._spark(pd.Series([1.0, 2.0, 3.0, 4.0]))
    assert s.plain[0] == "▁" and s.plain[-1] == "█"


def test_dashboard_renders_in_rich_mode(monkeypatch):
    rec = Console(record=True, width=120, force_terminal=True)
    monkeypatch.setattr(log, "console", rec)
    log.setup(LogMode.RICH)
    log.telemetry.stages["fetch"] = 0.5
    run = RunRecord.model_validate(RUN)
    log.dashboard(run, {"cs": pd.Series([1.0, 2.0, 3.0])}, {"pdf": "/tmp/out/run/report.pdf", "chart_png": None})
    text = rec.export_text()
    for needle in (
        "wiki-interest",
        "synthetic data",
        "fetch 0.50s",
        "cs",
        "stable_or_unclear",
        "SPIKE_DRIVEN",
        "no article",
        "report.pdf",
    ):
        assert needle in text, needle
    log.setup(LogMode.QUIET)
